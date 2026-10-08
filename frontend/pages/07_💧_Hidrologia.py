import os
import sys
import streamlit as st
import requests
import geopandas as gpd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import unicodedata
import re
import pandas as pd
import numpy as np

from modules.etp_extractor import extraer_etp_mensual
from modules.hydrological_balance import calcular_balance_mensual

from sqlalchemy import text
from modules.db_manager import get_engine
from modules.utils import normalizar_texto

st.set_page_config(page_title="Modelo Hidrológico", page_icon="💧", layout="wide")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules import selectors
from modules.data_processor import load_and_process_all_data

selectors.renderizar_menu_navegacion("Hidrología")

# =========================================================================
# 🧠 1. EXTRACCIÓN DEL SELECTOR ESPACIAL (EL ALEPH) Y CEREBRO ESTRUCTURAL
# =========================================================================
territorio_str = st.session_state.get('aleph_lugar', 'COLOMBIA')
nivel_jerarquico = st.session_state.get('aleph_escala', 'NACIONAL')

if not territorio_str or str(territorio_str).strip() in ["", "None", "-- Seleccione --"]:
    st.info("👈 Seleccione un Territorio (Cuenca, Municipio o Región) en el menú lateral para iniciar.")
    st.stop()

# --- INICIALIZACIÓN ESTRUCTURAL DE ESCALAS ---
nivel_norm = str(st.session_state.get('aleph_escala', '')).upper().strip()
es_nacional = "NACION" in nivel_norm
es_departamento = "DEPARTAMENTO" in nivel_norm or "DEPARTAMENTAL" in nivel_norm
es_municipio = "MUNICIPAL" in nivel_norm or "MUNICIPIO" in nivel_norm
es_region = "REGION" in nivel_norm or "SUBREGION" in nivel_norm
es_car = "CAR" in nivel_norm or "AUTORIDAD" in nivel_norm
es_cuenca = "CUENCA" in nivel_norm or "NSS" in nivel_norm or "SZH" in nivel_norm
# ---------------------------------------------    

# =========================================================================
# 2. CONTROLES TEMPORALES
# =========================================================================
st.sidebar.subheader("⏳ Horizonte Temporal")
anio_analisis = st.sidebar.slider(
    "Año de Análisis (Demografía y WEAP):", 
    min_value=1985, max_value=2050, value=2026, step=1
)

if nivel_jerarquico != "Estaciones":
    st.success(f"Analizando Hidrología para el territorio: **{territorio_str}** (Nivel: {nivel_jerarquico}) | **Año de Análisis: {anio_analisis}**")

buffer_km = st.sidebar.slider("🎯 Radio de Búsqueda (Buffer en km):", min_value=0.0, max_value=50.0, value=15.0, step=1.0)

# 🪂 FUNCIÓN CACHEADA GLOBALMENTE
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_territorio_maestro():
    import geopandas as gpd
    import requests, io
    url = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson"
    try:
        res = requests.get(url, timeout=60) 
        if res.status_code == 200:
            gdf = gpd.read_file(io.BytesIO(res.content))
            gdf.columns = [c.lower().strip() for c in gdf.columns]
            return gdf
    except Exception as e:
        print(f"Error descargando TerritorioMaestro: {e}")
    return gpd.GeoDataFrame()

# =========================================================================
# 🌍 RADAR ESPACIAL Y EXTRACCIÓN SATELITAL
# =========================================================================
with st.spinner("🌍 Ejecutando radar espacial avanzado y extrayendo datos satelitales..."):
    (gdf_stations, gdf_municipios, _, _, gdf_subcuencas, _) = load_and_process_all_data()
    ids_estaciones = []
    
    # 🚀 RESCATE ESTRUCTURAL: Usar el caché de memoria viva (Si existe)
    gdf_zona = None
    if 'aleph_poligono' in st.session_state and st.session_state['aleph_poligono'] is not None and not st.session_state['aleph_poligono'].empty:
        gdf_zona = st.session_state['aleph_poligono']

    # 🪂 PARACAÍDAS CARTOGRÁFICO ESTRUCTURAL
    if gdf_zona is None or gdf_zona.empty:
        import unicodedata
        import re
        
        def norm_text(t):
            if not isinstance(t, str) or pd.isna(t): return ""
            return unicodedata.normalize('NFKD', t.lower().strip()).encode('ascii', 'ignore').decode('utf-8')

        ALIASES_MUNICIPIOS = {
            "el carmen de viboral": "EL CARMEN DE VIBORAL",
            "carmen de viboral": "EL CARMEN DE VIBORAL",
            "el penol": "PEÑOL",
            "penol": "PEÑOL",
            "el retiro": "RETIRO",
            "retiro": "RETIRO",
            "carolina del principe": "CAROLINA",
            "carolina": "CAROLINA",
            "santa fe de antioquia": "Santa Fe De Antioquia",
            "santafe de antioquia": "Santa Fe De Antioquia",
            "pueblo rico": "PUEBLORRICO",
            "pueblorrico": "PUEBLORRICO",
            "san jose de la montana": "SAN JOSE DE LA MONTAÑA",
            "san andres de cuerquia": "SAN ANDRES DE CUERQUIA",
            "san vicente": "SAN VICENTE FERRER",
            "san vicente ferrer": "SAN VICENTE FERRER",
            "ciudad bolivar": "CIUDAD BOLIVAR",
            "bolivar": "CIUDAD BOLIVAR",
            "canasgordas": "CAÑASGORDAS"
        }

        lugar_crudo = str(territorio_str).replace("CAR: ", "").strip()
        lugar_norm_inicial = norm_text(lugar_crudo)
        
        if lugar_norm_inicial in ALIASES_MUNICIPIOS:
            terr_norm = norm_text(ALIASES_MUNICIPIOS[lugar_norm_inicial])
            lugar_limpio_exacto = ALIASES_MUNICIPIOS[lugar_norm_inicial] 
        else:
            terr_norm = norm_text(lugar_crudo)
            lugar_limpio_exacto = lugar_crudo

        encontrado = False

        if es_nacional:
            gdf_tm = fetch_territorio_maestro()
            if not gdf_tm.empty:
                gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm.unary_union], crs=gdf_tm.crs)
                encontrado = True

        elif es_cuenca:
            if gdf_subcuencas is not None and not gdf_subcuencas.empty:
                # 🔥 FIX REGEX: Extraer el ÚLTIMO contenido entre paréntesis para evitar 
                # caer en trampas de texto como "(md)" o "(mi)" en el nombre de la cuenca.
                todos_parentesis = re.findall(r'\((.*?)\)', str(territorio_str))
                cod_ideam = todos_parentesis[-1].strip() if todos_parentesis else None
                
                if cod_ideam:
                    cols_cod = [c for c in gdf_subcuencas.columns if c.lower() in ['nss1', 'nss2', 'nss3', 'szh', 'zh', 'ah']]
                    for col in cols_cod:
                        mask_ideam = gdf_subcuencas[col].astype(str).str.strip() == cod_ideam
                        if mask_ideam.any():
                            gdf_zona_tmp = gdf_subcuencas[mask_ideam]
                            gdf_zona = gpd.GeoDataFrame(geometry=[gdf_zona_tmp.unary_union], crs=gdf_subcuencas.crs)
                            encontrado = True
                            break
                if not encontrado:
                    def limpiar_texto(t):
                        if not isinstance(t, str): return ""
                        return re.sub(r'[^A-Z0-9]', '', ''.join(c for c in unicodedata.normalize('NFD', t.upper()) if unicodedata.category(c) != 'Mn'))
                    
                    mask_c = gdf_subcuencas.apply(lambda row: limpiar_texto(lugar_crudo) in limpiar_texto(str(row.to_dict().values())), axis=1)
                    
                    if mask_c.any():
                        gdf_zona_tmp = gdf_subcuencas[mask_c]
                        
                        # =========================================================================
                        # 🛡️ INTERCEPTOR ESPACIAL Y AGREGADOR MULTIESCALA (V3 - Búsqueda Total)
                        # =========================================================================
                        codigo_unico = st.session_state.get('aleph_codigo_cuenca', 'N/A')
                        
                        if codigo_unico != 'N/A':
                            # 1. Diccionario de columnas en mayúsculas para evitar errores
                            cols_upper = {c.upper(): c for c in gdf_subcuencas.columns}
                            
                            # 2. Máscara inicial (Falso para todos)
                            mask_estricta = (gdf_subcuencas.index == -1) 
                            
                            # 3. Lista exhaustiva de columnas de códigos Y NOMBRES en Supabase
                            columnas_busqueda = [
                                'NSS3', 'NSS2', 'NSS1', 'SZH', 'ZH', 'AH',
                                'NOM_SZH', 'NOMZH', 'NOMAH', 'NOM_ZH', 'NOM_AH',
                                'NOM_NSS1', 'NOM_NSS2', 'NOM_NSS3'
                            ]
                            
                            # Normalizamos lo que estamos buscando a texto en mayúsculas
                            codigo_str = str(codigo_unico).strip().upper()
                            
                            # 4. Sumar coincidencias donde sea que esté (Código o Nombre)
                            for jerarquia in columnas_busqueda:
                                if jerarquia in cols_upper:
                                    col_real = cols_upper[jerarquia]
                                    # Convertimos la columna a texto y mayúsculas para un match perfecto
                                    mask_estricta = mask_estricta | (gdf_subcuencas[col_real].astype(str).str.strip().str.upper() == codigo_str)
                            
                            if mask_estricta.any():
                                gdf_zona_tmp = gdf_subcuencas[mask_estricta]
                                
                                # 🔥 AGREGADOR LIBERADO: Fusiona todas las subcuencas en el macropolígono
                                gdf_zona = gpd.GeoDataFrame(geometry=[gdf_zona_tmp.unary_union], crs=gdf_subcuencas.crs)
                                encontrado = True
                        # =========================================================================

        if not encontrado and not es_cuenca and not es_nacional:
            gdf_tm = fetch_territorio_maestro() 
            if not gdf_tm.empty:
                if es_departamento and ("ANTIOQUIA" in terr_norm or "COLOMBIA" in terr_norm):
                    col_depto = 'dpto_cnmbr' if 'dpto_cnmbr' in gdf_tm.columns else 'departamento'
                    if col_depto in gdf_tm.columns:
                        mask = gdf_tm[col_depto].apply(norm_text).isin(['antioquia'])
                        if mask.any():
                            gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm[mask].unary_union], crs=gdf_tm.crs)
                            encontrado = True
                elif es_region:
                    col_sub = 'subregion'
                    if col_sub in gdf_tm.columns:
                        mask = gdf_tm[col_sub].apply(norm_text) == terr_norm
                        if mask.any():
                            gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm[mask].unary_union], crs=gdf_tm.crs)
                            encontrado = True
                elif es_car:
                    col_car = 'car'
                    if col_car in gdf_tm.columns:
                        if terr_norm == "amva":
                            mask = gdf_tm[col_car].apply(norm_text).str.contains("amva|aburra", na=False)
                        elif terr_norm == "corantioquia":
                            mask_corantioquia = gdf_tm[col_car].apply(norm_text).str.contains("corantioquia", na=False)
                            mask_no_amva = ~gdf_tm['mpio_cnmbr'].apply(norm_text).isin(['medellin', 'bello', 'itagui', 'envigado', 'sabaneta', 'copacabana', 'la estrella', 'girardota', 'caldas', 'barbosa'])
                            mask = mask_corantioquia & mask_no_amva
                        else:
                            mask = gdf_tm[col_car].apply(norm_text).str.contains(terr_norm, na=False)
                        if mask.any():
                            gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm[mask].unary_union], crs=gdf_tm.crs)
                            encontrado = True
                elif es_municipio:
                    col_mpio = 'mpio_cnmbr' if 'mpio_cnmbr' in gdf_tm.columns else 'municipio'
                    if col_mpio in gdf_tm.columns:
                        mask_norm = gdf_tm[col_mpio].apply(norm_text) == terr_norm
                        mask_exacta = gdf_tm[col_mpio] == lugar_limpio_exacto
                        mask = mask_norm | mask_exacta
                        if mask.any():
                            gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm[mask].unary_union], crs=gdf_tm.crs)
                            encontrado = True

    # ⚔️ CRUCE GEOGRÁFICO FINAL (Limpiando indices residuales)
    if gdf_zona is not None and not gdf_zona.empty and gdf_stations is not None and not gdf_stations.empty:
        gdf_zona_proj = gdf_zona.to_crs(epsg=3116)
        gdf_stations_proj = gdf_stations.to_crs(epsg=3116)
        
        # 🧹 BARRIDO FORENSE: Eliminar basura espacial
        cols_drop = [c for c in gdf_stations_proj.columns if c in ['index_right', 'index_left']]
        if cols_drop: gdf_stations_proj = gdf_stations_proj.drop(columns=cols_drop)

        if buffer_km > 0: 
            gdf_zona_proj['geometry'] = gdf_zona_proj.geometry.buffer(buffer_km * 1000)
            
        estaciones_dentro = gpd.sjoin(gdf_stations_proj, gdf_zona_proj, predicate='intersects')
        ids_estaciones = [str(x).strip() for x in estaciones_dentro['id_estacion'].unique().tolist()]

    # 🚀 INTEGRACIÓN SATELITAL ETP
    etp_real = [100.0] * 12 
    if gdf_zona is not None and not gdf_zona.empty:
        try: etp_real = extraer_etp_mensual(gdf_zona)
        except: pass

# =========================================================================
# 🚨 MANEJO DE FLUJO SEGURO (SIN st.stop)
# =========================================================================
if not ids_estaciones:
    st.warning(f"⚠️ No se encontraron estaciones meteorológicas a menos de {buffer_km} km de {territorio_str}.")
    st.info("💡 Sugerencia: Selecciona otro territorio o aumenta el 'Radio de Búsqueda' en el panel lateral.")
else:
    st.markdown("---")
    st.subheader(f"📊 Perfil Hidro-Climático: {territorio_str}")

    # ==========================================
    # 🗺️ MINI-MAPA SATELITAL DE CONTEXTO
    # ==========================================
    if gdf_zona is not None and not gdf_zona.empty:
        with st.expander("📍 Ver Contexto Geográfico Satelital", expanded=False):
            try:
                import folium
                import streamlit.components.v1 as components
                
                # Obtenemos el centroide para centrar la cámara
                centroide = gdf_zona.to_crs(epsg=4326).geometry.centroid.iloc[0]
                m = folium.Map(location=[centroide.y, centroide.x], zoom_start=11)
                
                # Capa Satelital Esri
                tile_url = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                folium.TileLayer(
                    tiles=tile_url, attr='Esri', name='Satélite', overlay=False, control=False
                ).add_to(m)
                
                # Proyectar el polígono de la cuenca sobre el mapa
                folium.GeoJson(
                    gdf_zona.to_crs(epsg=4326),
                    style_function=lambda x: {
                        'fillColor': '#f1c40f', # Amarillo resaltado
                        'color': '#e67e22',
                        'weight': 3,
                        'fillOpacity': 0.3
                    },
                    tooltip=territorio_str
                ).add_to(m)
                
                components.html(m._repr_html_(), height=350)
            except Exception as e:
                st.caption(f"Error cargando el mapa de contexto: {e}")
    # ==========================================

    with st.spinner(f"📡 Procesando {len(ids_estaciones)} estaciones vía FastAPI..."):
        payload = {"territorio": territorio_str, "ids_estaciones": ids_estaciones}
        try:
            response = requests.post("http://127.0.0.1:8000/api/hidrologia/perfil_base", json=payload, timeout=20)
            response.raise_for_status()
            datos = response.json()
            
            if "error" in datos:
                st.warning(datos["error"])
            else:
                from modules.analysis import calculate_morphometry, calculate_hypsometric_curve

                ruta_dem_nube = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/rasters/DemAntioquia_EPSG3116.tif"
                ruta_cobertura = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/rasters/Cob2026_Actualizada.tif"

                es_escala_masiva = es_nacional or es_departamento or es_region or es_car

                area_km2, alt_min, alt_max, alt_promedio, indice_forma, perimetro = 1.0, 0, 4000, 2000, 0, 0

                if gdf_zona is not None and not gdf_zona.empty:
                    try: area_km2 = gdf_zona.to_crs(epsg=3116).geometry.area.sum() / 1e6
                    except: pass 
                    
                    # =========================================================================
                    # 🚀 NUEVO MOTOR PURE-SQL: CONSULTA ESTRICTA A LA MATRIZ MAESTRA
                    # =========================================================================
                    try:
                        from sqlalchemy import text
                        from modules.db_manager import get_engine
                        engine = get_engine()
                        
                        nombre_puro = str(territorio_str).split(" - (")[0].strip()
                        nombre_limpio = normalizar_texto(nombre_puro).upper().replace(" ", "_")
                        
                        if es_municipio: prefijo_nivel = "MUNICIPAL"
                        elif es_departamento: prefijo_nivel = "DEPARTAMENTAL"
                        elif es_region: prefijo_nivel = "REGIONAL"
                        elif es_car: prefijo_nivel = "CAR"
                        else: prefijo_nivel = "%" # Búsqueda general para cuencas

                        # Excepciones sintácticas de la base de datos forjada
                        if prefijo_nivel == "CAR" and "VALLE_DE_ABURRA" in nombre_limpio: nombre_limpio = "AMVA"

                        # Generamos la llave maestra. Si no es cuenca, obligamos a que coincida exactamente
                        llave_exacta = f"{prefijo_nivel}_{nombre_limpio}_TOTAL"
                        
                        with engine.connect() as conn:
                            if prefijo_nivel != "%":
                                # Búsqueda 100% estricta para divisiones político-administrativas
                                query = text('''
                                    SELECT "H_Minima", "H_Maxima", "H_Media", "Coef_C3", "Coef_C2", "Coef_C1", "Coef_C0"
                                    FROM matriz_hidrogeomorfologica_maestra 
                                    WHERE "LLAVE_UNIVERSAL" = :llave_exacta
                                ''')
                                result = conn.execute(query, {"llave_exacta": llave_exacta}).fetchone()
                            else:
                                # Búsqueda amplia para cuencas (NSS1, NSS2, NSS3, SZH, etc.)
                                llave_busqueda = f"%_{nombre_limpio}_TOTAL"
                                query = text('''
                                    SELECT "H_Minima", "H_Maxima", "H_Media", "Coef_C3", "Coef_C2", "Coef_C1", "Coef_C0"
                                    FROM matriz_hidrogeomorfologica_maestra 
                                    WHERE "LLAVE_UNIVERSAL" LIKE :llave_busqueda 
                                    OR "Territorio" ILIKE :nombre_puro
                                    ORDER BY 
                                        CASE WHEN "LLAVE_UNIVERSAL" LIKE :llave_busqueda THEN 1 ELSE 2 END
                                    LIMIT 1
                                ''')
                                result = conn.execute(query, {"llave_busqueda": llave_busqueda, "nombre_puro": nombre_puro}).fetchone()
                            
                            if result:
                                # Solo aplicamos validación de bordes nulos o negativos que vengan del DEM
                                alt_min = result[0] if result[0] is not None and result[0] >= 0 else 0
                                alt_max = result[1] if result[1] is not None else 4000
                                alt_promedio = result[2] if result[2] is not None else 2000
                                
                                st.session_state['coefs_hipso'] = {
                                    'C3': result[3], 'C2': result[4], 'C1': result[5], 'C0': result[6]
                                }
                            else:
                                alt_min, alt_max, alt_promedio = 0, 4000, 2000
                                st.sidebar.caption("⚠️ Entidad no hallada en Matriz. Extrayendo estimación.")
                                
                    except Exception as e:
                        alt_min, alt_max, alt_promedio = 0, 4000, 2000
                        st.sidebar.caption(f"⚠️ Error conectando a Matriz: {e}")
                    # =========================================================================

                if alt_max <= alt_min: alt_max = alt_min + 100

                st.sidebar.subheader("⛰️ Gestión 3D (Hipsometría)")
                
                # 🚀 FIX LLAVE DE ESTADO: Creamos una clave alfanumérica pura para evitar cualquier cruce en la memoria caché
                import re
                clave_slider = re.sub(r'[^a-zA-Z0-9]', '_', str(territorio_str))
                
                cota_gestion = st.sidebar.slider(
                    "Cota de Gestión (msnm):", 
                    min_value=int(alt_min), 
                    max_value=int(alt_max), 
                    value=int(alt_min), 
                    step=50,
                    key=f"sl_hipso_{clave_slider}",
                    help="Desliza para simular restricciones operativas o cotas de inundación."
                )

                area_cota_km2 = area_km2
                etp_cota = etp_real.copy()
                area_porcentaje = 100.0

                if cota_gestion > alt_min and gdf_zona is not None:
                    if not es_escala_masiva:
                        try:
                            # 🔥 FIX: La curva hipsométrica también debe recibir el polígono reproyectado en metros
                            hypso_data = calculate_hypsometric_curve(gdf_zona.to_crs(epsg=3116), dem_path=ruta_dem_nube)
                            if hypso_data and len(hypso_data.get("elevations", [])) > 0:
                                elevs = hypso_data["elevations"]
                                areas = hypso_data["area_percent"]
                                valid_areas = areas[elevs >= cota_gestion]
                                area_porcentaje = valid_areas.max() if len(valid_areas) > 0 else 0.0
                        except:
                            area_porcentaje = max(0.0, 100.0 * (1.0 - ((cota_gestion - alt_min) / (alt_max - alt_min))))
                    else:
                        # Estimación lineal rápida para escalas gigantes
                        area_porcentaje = max(0.0, 100.0 * (1.0 - ((cota_gestion - alt_min) / (alt_max - alt_min))))
                        
                    area_cota_km2 = area_km2 * (area_porcentaje / 100.0)
                    diferencia_alt = cota_gestion - alt_promedio
                    if diferencia_alt > 0:
                        etp_cota = [e * max(0.2, 1.0 - (0.04 * (diferencia_alt / 100.0))) for e in etp_real]

                    st.sidebar.success(f"🏔️ Activa: > {cota_gestion} msnm. ({area_porcentaje:.1f}%)")

                from modules.land_cover import calcular_estadisticas_zona, get_infiltration_suggestion
                
                if not es_escala_masiva:
                    stats_cobertura = calcular_estadisticas_zona(gdf_zona, ruta_cobertura)
                    factor_infiltracion, info_cobertura = get_infiltration_suggestion(stats_cobertura)
                else:
                    factor_infiltracion, info_cobertura = 0.25, "Promedio Regional Andino"

                st.sidebar.subheader("🌍 Escenarios Climáticos")
                escenario_climatico = st.sidebar.selectbox(
                    "Simulación Prospectiva:",
                    ["🟢 Condición Actual (Línea Base)", "🔴 Fenómeno de El Niño", "🔵 Fenómeno de La Niña", "🟡 SSP2-4.5 (2050)", "🔥 SSP5-8.5 (2050)"]
                )

                factor_ppt, factor_etp = 1.0, 1.0
                if "Niño" in escenario_climatico: factor_ppt, factor_etp = 0.65, 1.15
                elif "Niña" in escenario_climatico: factor_ppt, factor_etp = 1.40, 0.90
                elif "SSP2" in escenario_climatico: factor_ppt, factor_etp = 0.95, 1.10
                elif "SSP5" in escenario_climatico: factor_ppt, factor_etp = 0.85, 1.25

                precip_base = datos["precipitacion"]
                precip_media = [p * factor_ppt for p in precip_base]
                etp_cota = [e * factor_etp for e in etp_cota]

                if factor_ppt != 1.0:
                    st.warning(f"⚠️ **Proyección Climática Activa:** {escenario_climatico}. \n\n☔ Lluvia forzada al **{factor_ppt*100:.0f}%** y ☀️ Evapotranspiración al **{factor_etp*100:.0f}%**.")

                precip_max = [p * 1.30 for p in precip_media]
                precip_min = [p * 0.70 for p in precip_media]

                balance_medio = calcular_balance_mensual(precip_media, etp_cota, area_cota_km2, factor_recarga_base=factor_infiltracion)
                balance_humedo = calcular_balance_mensual(precip_max, etp_cota, area_cota_km2, factor_recarga_base=factor_infiltracion)
                balance_seco = calcular_balance_mensual(precip_min, etp_cota, area_cota_km2, factor_recarga_base=factor_infiltracion)

                fig = make_subplots(specs=[[{"secondary_y": True}]])
                
                fig.add_trace(go.Bar(x=datos["meses"], y=precip_media, name="Precipitación (mm)", marker_color='#3498db', opacity=0.6), secondary_y=False)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_medio["exceso_total"], name="Agua Excedente / Escorrentía", fill='tozeroy', mode='none', fillcolor='rgba(41, 128, 185, 0.4)'), secondary_y=False)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_medio["etr"], name="ETR Real (mm)", mode='lines+markers', line=dict(color='#27ae60', width=3)), secondary_y=False)
                fig.add_trace(go.Scatter(x=datos["meses"], y=etp_cota, name="ETP Potencial (mm)", mode='lines', line=dict(color='#e74c3c', width=2, dash='dot')), secondary_y=False)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_humedo["caudal_m3s"], name="Max", mode='lines', line=dict(color='rgba(142, 68, 173, 0)'), showlegend=False), secondary_y=True)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_seco["caudal_m3s"], name="Rango Histórico", mode='lines', line=dict(color='rgba(142, 68, 173, 0)'), fill='tonexty', fillcolor='rgba(142, 68, 173, 0.15)'), secondary_y=True)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_medio["caudal_m3s"], name="Caudal Medio (m³/s)", mode='lines', line=dict(color='#8e44ad', width=4)), secondary_y=True)

                # ==========================================
                # 💉 CIRUGÍA: INYECCIÓN DE CAUDAL BASE
                # ==========================================
                # Calculamos el caudal base como el 35% del caudal medio mensual
                caudal_base_mensual = [c * 0.35 for c in balance_medio["caudal_m3s"]]
                
                fig.add_trace(go.Scatter(
                    x=datos["meses"], 
                    y=caudal_base_mensual, 
                    name="Caudal Base (Aporte Subterráneo)", 
                    mode='lines', 
                    line=dict(color='saddlebrown', width=2, dash='dash'), 
                    showlegend=True
                ), secondary_y=True)
                # ==========================================

                # 🚀 FIX: Leyenda centrada en la parte superior (x=0.5) para que el gráfico use todo el ancho
                fig.update_layout(
                    hovermode="x unified", 
                    template="plotly_white", 
                    margin=dict(l=20, r=50, t=80, b=20), 
                    height=500, 
                    legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
                )
                
                fig.update_yaxes(title_text="Lámina de Agua (mm)", secondary_y=False)
                fig.update_yaxes(title_text="Caudal (m³/s)", secondary_y=True, showgrid=False)
                
                with st.expander(f"📊 Ver Gráfico Hidro-Climático", expanded=True):
                    st.plotly_chart(fig, use_container_width=True)

                lluvia_total = sum(precip_media)
                etp_total = sum(etp_cota)
                etr_total = sum(balance_medio["etr"])
                recarga_total = sum(balance_medio["recarga"])
                caudal_medio = sum(balance_medio["caudal_m3s"]) / 12

                st.markdown("---")
                with st.expander("📑 Síntesis Paramétrica Territorial", expanded=True):
                    tc1, tc2, tc3 = st.columns(3)
                    with tc1:
                        st.markdown("##### 🏔️ Morfometría (Satélite)")
                        st.write(f"- **Área Total:** {area_km2:,.1f} km²")
                        st.write(f"- **Altitud Promedio:** {alt_promedio:,.0f} msnm")
                    with tc2:
                        st.markdown("##### 🌦️ Climatología Base")
                        st.write(f"- **Lluvia Anual:** {lluvia_total:,.0f} mm")
                        st.write(f"- **ETP Anual:** {etp_total:,.0f} mm")
                    with tc3:
                        st.markdown("##### 🌊 Hidrología (Balance)")
                        st.write(f"- **Caudal Medio:** {caudal_medio:,.2f} m³/s")
                        st.write(f"- **Recarga Acuíferos:** {recarga_total:,.0f} mm")
                        st.markdown("##### 🌱 Suelo")
                        st.write(f"- **Estado:** {info_cobertura}")

                st.markdown("---")
                rendimiento_lsk = (caudal_medio * 1000) / area_cota_km2 if area_cota_km2 > 0 else 0
                
                with st.expander("🤖 Ver Diagnóstico Hidro-Climático Automático", expanded=True):
                    st.markdown("### Análisis del Sistema")
                    
                    # 1. Cálculos de Oferta Neta
                    oferta_bruta = lluvia_total - etp_total
                    
                    # Extraemos recarga (si no existe en memoria, asumimos un 15% por defecto)
                    recarga_acuifero = st.session_state.get('recarga_acuifero_mm', oferta_bruta * 0.15) 
                    
                    # Caudal ecológico (25% de la oferta bruta según normativas estándar)
                    caudal_ecologico = oferta_bruta * 0.25 
                    
                    # La verdadera Oferta Neta
                    oferta_neta = oferta_bruta - recarga_acuifero - caudal_ecologico
                    
                    # 2. Renderizado del Mensaje
                    if oferta_neta > 0:
                        st.success(f"💧 **Estado Estructural:** Superávit hídrico natural. La lluvia supera la evapotranspiración, dejando una **Oferta Neta de {oferta_neta:,.0f} mm/año** (descontando {recarga_acuifero:,.0f} mm de recarga de acuíferos y {caudal_ecologico:,.0f} mm de caudal ecológico).")
                    elif oferta_bruta > 0:
                        st.warning(f"⚠️ **Estado Estructural:** Tensión hídrica. Hay excedente bruto, pero al descontar acuíferos y caudal ecológico, la Oferta Neta es deficitaria ({oferta_neta:,.0f} mm/año).")
                    else:
                        st.error(f"🏜️ **Estado Estructural:** Déficit crónico. La evapotranspiración potencial supera la lluvia.")
                        
                    st.markdown(f"🌊 **Productividad Hídrica:** La cuenca produce **{rendimiento_lsk:.1f} Litros/segundo por cada km²**.")

                st.markdown("---")
                st.subheader("⚖️ Balance Oferta-Demanda (Modelo WEAP Integrado)")
                
                pob_bd = 50000.0
                rurh_bd_m3s = 0.0
                
                try:
                    # =================================================================
                    # 1. 🧠 CONEXIÓN AL CEREBRO DEMOGRÁFICO CENTRALIZADO (DRY)
                    # =================================================================
                    try:
                        from modules.demografia_tools import cargar_datos_dane_crudos, calcular_poblacion_al_vuelo
                        # El motor hace todo: ruteo de escalas, sumas, y cruce de cuencas
                        df_pob = calcular_poblacion_al_vuelo(territorio_str, nivel_jerarquico, "Total", anio_especifico=anio_analisis)
                        if df_pob is not None and not df_pob.empty:
                            pob_bd = float(df_pob['Total'].iloc[0])
                    except Exception as e:
                        st.warning(f"⚠️ Error en módulo demográfico: {e}")

                    # =================================================================
                    # 2. 🏭 CONCESIONES RURH (Consulta SQL a la matriz de presiones)
                    # =================================================================
                    from sqlalchemy import text
                    from modules.db_manager import get_engine
                    import pandas as pd
                    
                    engine = get_engine()
                    nombre_puro = territorio_str.split(" - (")[0].strip() if " - (" in territorio_str else territorio_str.strip()
                    n_upper = nombre_puro.upper().replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
                    
                    # Diccionarios Base para la extracción RURH
                    M_SUB = {
                        "VALLE DE ABURRA": ["MEDELLIN", "BELLO", "ITAGUI", "ENVIGADO", "SABANETA", "COPACABANA", "LA ESTRELLA", "GIRARDOTA", "CALDAS", "BARBOSA"],
                        "BAJO CAUCA": ["CAUCASIA", "CACERES", "EL BAGRE", "NECHI", "TARAZA", "ZARAGOZA"],
                        "NORDESTE": ["AMALFI", "ANORI", "CISNEROS", "REMEDIOS", "SAN ROQUE", "SANTO DOMINGO", "SEGOVIA", "VEGACHI", "YALI", "YOLOMBO"],
                        "ORIENTE": ["ABEJORRAL", "ALEJANDRIA", "ARGELIA", "EL CARMEN DE VIBORAL", "COCORNA", "CONCEPCION", "EL PENOL", "EL RETIRO", "EL SANTUARIO", "GUARNE", "GUATAPE", "LA CEJA", "LA UNION", "MARINILLA", "NARINO", "RIONEGRO", "SAN CARLOS", "SAN FRANCISCO", "SAN LUIS", "SAN RAFAEL", "SAN VICENTE", "SONSON", "GRANADA"],
                        "URABA": ["APARTADO", "ARBOLETES", "CAREPA", "CHIGORODO", "MURINDO", "MUTATA", "NECOCLI", "SAN JUAN DE URABA", "SAN PEDRO DE URABA", "TURBO", "VIGIA DEL FUERTE"]
                    }
                    M_CAR = {"AMVA": M_SUB.get("VALLE DE ABURRA", [])}
                    
                    es_region = "REGION" in str(nivel_jerarquico).upper()
                    mpios_a_sumar = M_SUB.get(n_upper, []) if es_region else M_CAR.get(n_upper, [])
                    if n_upper == "CORANTIOQUIA": 
                        todos = [m for sublist in M_SUB.values() for m in sublist]
                        mpios_a_sumar = list(set(todos) - set(M_CAR.get("AMVA", [])))

                    with engine.connect() as conn:
                        df_rurh = pd.read_sql(text('SELECT * FROM matriz_presiones_rurh'), conn)
                        if not df_rurh.empty:
                            col_terr_r = next((c for c in df_rurh.columns if 'TERR' in c.upper()), 'Territorio')
                            col_val_r = next((c for c in df_rurh.columns if 'RURH' in c.upper() or 'PRESION' in c.upper()), 'Presion_Total_RURH_m3s')
                            
                            df_rurh['terr_clean'] = df_rurh[col_terr_r].astype(str).str.upper().str.replace('Á','A').str.replace('É','E').str.replace('Í','I').str.replace('Ó','O').str.replace('Ú','U').str.strip()
                            lista_rurh = mpios_a_sumar if mpios_a_sumar else [n_upper]
                            df_rurh_f = df_rurh[df_rurh['terr_clean'].isin(lista_rurh)]
                            
                            if not df_rurh_f.empty: 
                                rurh_bd_m3s = float(df_rurh_f[col_val_r].sum())
                            elif not es_cuenca: # Solo aplica comodín si NO es cuenca, para evitar arrastrar todo Antioquia
                                clave = n_upper.split()[0] if len(n_upper.split()) > 1 else n_upper
                                mask_f = df_rurh['terr_clean'].str.contains(clave, na=False)
                                if mask_f.any(): 
                                    rurh_bd_m3s = float(df_rurh[mask_f][col_val_r].sum())
                            else:
                                rurh_bd_m3s = 0.0 # Si es cuenca y no se encontró, inicia en 0 para no distorsionar

                except Exception as e:
                    st.warning(f"⚠️ Estimaciones locales. Detalle BD: {e}")

                col_D1, col_D2, col_D3, col_D4 = st.columns(4)
                with col_D1:
                    pob_weap = st.number_input("👥 Población a Abastecer:", min_value=0, value=int(pob_bd), step=1000, help="Extraído automáticamente de la Matriz Demográfica.")
                with col_D2:
                    dotacion_weap = st.number_input("🚰 Dotación (L/hab/día):", min_value=50, max_value=400, value=150)
                with col_D3:
                    # RURH ahora es editable por el usuario
                    presion_rurh_input = st.number_input("🏭 Presión RURH (m³/s):", min_value=0.0, value=float(rurh_bd_m3s), format="%.4f", help="Extraído del RURH. Puede editarse si posee un aforo más preciso.")
                with col_D4:
                    retorno_weap = st.slider("♻️ Retorno al Río (%):", min_value=0, max_value=100, value=80)

                demanda_humana_m3s = (pob_weap * dotacion_weap) / (1000 * 86400)
                consumo_neto_humano_m3s = demanda_humana_m3s * (1.0 - (retorno_weap / 100.0))
                demanda_total_m3s = demanda_humana_m3s + presion_rurh_input
                consumo_neto_total = consumo_neto_humano_m3s + presion_rurh_input
                
                oferta_m3s = caudal_medio
                iua = (demanda_total_m3s / oferta_m3s) * 100 if oferta_m3s > 0 else 100.0
                
                if iua <= 10: est_iua, col_iua = "Bajo (Sin Estrés)", "🟢"
                elif iua <= 20: est_iua, col_iua = "Moderado", "🟡"
                elif iua <= 50: est_iua, col_iua = "Alto (Presión Hídrica)", "🟠"
                else: est_iua, col_iua = "Crítico (Escasez)", "🔴"

                st.markdown(f"#### {col_iua} Índice de Uso de Agua (IUA): **{iua:.1f}%** - Estado: **{est_iua}**")
                st.progress(min(iua / 100.0, 1.0))
                
                cm1, cm2, cm3, cm4 = st.columns(4)
                cm1.metric("🌊 Oferta Física Dinámica", f"{oferta_m3s:.3f} m³/s", "De la cuenca activa")
                cm2.metric("👥 Demanda Humana", f"{demanda_humana_m3s:.3f} m³/s", f"{int(pob_weap)} habs", delta_color="inverse")
                cm3.metric("🏭 Presión RURH", f"{presion_rurh_input:.3f} m³/s", "Concesiones CAR", delta_color="inverse")
                
                caudal_restante = oferta_m3s - consumo_neto_total
                cm4.metric("🏞️ Caudal Libre", f"{caudal_restante:.3f} m³/s", "Volumen residual")

                if iua > 50:
                    st.error(f"⚠️ **Alerta WEAP:** La demanda total ({demanda_total_m3s:.2f} m³/s) extrae una porción crítica de la oferta.")

                df_balance = pd.DataFrame({
                    "Mes": datos["meses"],
                    "Precipitación_Media (mm)": [round(x, 1) for x in precip_media],
                    "ETP_Potencial_Ajustada (mm)": [round(x, 1) for x in etp_cota],
                    "ETR_Real (mm)": balance_medio["etr"],
                    "Infiltración_Recarga (mm)": balance_medio["recarga"],
                    "Escorrentía_Superficial (mm)": balance_medio["escorrentia"],
                    "Caudal_Estimado (m³/s)": balance_medio["caudal_m3s"]
                })

                st.markdown("---")
                colA, colB = st.columns([3, 1])
                with colA:
                    st.subheader("📋 Matriz de Balance Hídrico Mensual")
                with colB:
                    csv = df_balance.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Matriz (CSV)",
                        data=csv,
                        file_name=f"Balance_Hidrico_{territorio_str.replace(' ', '_')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                st.dataframe(df_balance.style.format(precision=1), use_container_width=True)

        except Exception as e:
            st.error(f"🔌 Error de procesamiento: {e}")