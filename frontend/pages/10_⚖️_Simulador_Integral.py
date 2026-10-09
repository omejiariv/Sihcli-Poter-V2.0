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

selectors.renderizar_menu_navegacion("Simulador Integral")

# =========================================================================
# 🧠 1. EXTRACCIÓN DEL SELECTOR ESPACIAL (EL ALEPH) Y CEREBRO ESTRUCTURAL
# =========================================================================
territorio_str = st.session_state.get('aleph_lugar', 'COLOMBIA')
nivel_jerarquico = st.session_state.get('aleph_escala', 'NACIONAL')

# --- INICIALIZACIÓN ESTRUCTURAL DE ESCALAS ---
nivel_norm = str(st.session_state.get('aleph_escala', '')).upper().strip()
es_nacional = "NACION" in nivel_norm
es_departamento = "DEPARTAMENTO" in nivel_norm or "DEPARTAMENTAL" in nivel_norm
es_municipio = "MUNICIPAL" in nivel_norm or "MUNICIPIO" in nivel_norm
es_region = "REGION" in nivel_norm or "SUBREGION" in nivel_norm
es_car = "CAR" in nivel_norm or "AUTORIDAD" in nivel_norm
es_cuenca = "CUENCA" in nivel_norm or "NSS" in nivel_norm or "SZH" in nivel_norm
# ---------------------------------------------

if not territorio_str or str(territorio_str).strip() in ["", "None", "-- Seleccione --"]:
    st.info("👈 Seleccione un Territorio (Cuenca, Municipio o Región) en el menú lateral para iniciar.")
    st.stop()

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

        nivel_norm = str(nivel_jerarquico).upper().strip()
        es_nacional = "NACION" in nivel_norm
        es_departamento = "DEPARTAMENTO" in nivel_norm or "DEPARTAMENTAL" in nivel_norm or "COLOMBIA" in terr_norm
        es_municipio = "MUNICIPAL" in nivel_norm or "MUNICIPIO" in nivel_norm
        es_region = "REGION" in nivel_norm or "SUBREGION" in nivel_norm
        es_car = "CAR" in nivel_norm or "AUTORIDAD" in nivel_norm
        es_cuenca = "CUENCA" in nivel_norm or "NSS" in nivel_norm or "SZH" in nivel_norm
        
        encontrado = False

        if es_nacional:
            gdf_tm = fetch_territorio_maestro()
            if not gdf_tm.empty:
                gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm.unary_union], crs=gdf_tm.crs)
                encontrado = True

        elif es_cuenca:
            if gdf_subcuencas is not None and not gdf_subcuencas.empty:
                codigo_match = re.search(r'\((.*?)\)', str(territorio_str))
                cod_ideam = codigo_match.group(1).strip() if codigo_match else None
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
                        # 🛡️ INTERCEPTOR ESPACIAL ESTRICTO (MATA CLONES)
                        # =========================================================================
                        codigo_unico = st.session_state.get('aleph_codigo_cuenca', 'N/A')
                        
                        if codigo_unico != 'N/A':
                            import pandas as pd
                            mask_estricta = pd.Series(False, index=gdf_subcuencas.index)
                            
                            # 🚀 FIX: Buscar si la columna existe antes de filtrarla evita que 
                            # el sistema explote (KeyError) al cargar escalas mayores como SZH o AH.
                            cols_a_buscar = ['NSS3', 'NSS2', 'NSS1', 'nss3', 'nss2', 'nss1']
                            
                            for col in cols_a_buscar:
                                if col in gdf_subcuencas.columns:
                                    mask_estricta = mask_estricta | (gdf_subcuencas[col] == codigo_unico)
                            
                            if mask_estricta.any():
                                gdf_zona_tmp = gdf_subcuencas[mask_estricta]
                                
                            # 🔪 SEGURO ANTI-FRANKENSTEIN
                            if 'gdf_zona_tmp' in locals() and len(gdf_zona_tmp) > 1:
                                gdf_zona_tmp = gdf_zona_tmp.iloc[[0]]
                        # =========================================================================
                        
                        gdf_zona = gpd.GeoDataFrame(geometry=[gdf_zona_tmp.unary_union], crs=gdf_subcuencas.crs)
                        encontrado = True

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
    if gdf_zona is not None and not gdf_zona.empty and gdf_stations is not None:
        # 1. Asignar explícitamente el sistema base (WGS84) a ambos mapas
        gdf_zona.set_crs(epsg=4326, inplace=True, allow_override=True)
        gdf_stations.set_crs(epsg=4326, inplace=True, allow_override=True)
    
        # 2. Ahora sí podemos proyectar a MAGNA-SIRGAS origen nacional
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
    st.warning(f"⚠️ No se encontraron estaciones de monitoreo dentro del territorio seleccionado: **{territorio_str}**. \n\nIntente ampliar el radio de búsqueda o seleccione otro territorio.")
else:
    st.subheader(f"📊 Perfil Hidro-Climático: {territorio_str}")

    with st.spinner(f"📡 Procesando {len(ids_estaciones)} estaciones vía FastAPI..."):
        payload = {"territorio": territorio_str, "ids_estaciones": ids_estaciones}
        try:
            response = requests.post("https://sihcli-poter-v2-0.onrender.com/api/hidrologia/perfil_base", json=payload, timeout=90)
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
                    
                    # ---------------------------------------------------------
                    # 🛡️ MATRIZ MAESTRA DE COTAS (Rescate Estructural)
                    # ---------------------------------------------------------
                    matriz_cotas = {
                        "VALLE DE ABURRA": {"min": 1300, "max": 3100, "prom": 1800},
                        "MEDELLIN": {"min": 1450, "max": 3100, "prom": 1700},
                        "ANTIOQUIA": {"min": 0, "max": 4080, "prom": 1500}
                    }
                    
                    n_puro = str(territorio_str).split(" - (")[0].strip().upper()
                    n_puro = n_puro.replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')

                    if n_puro in matriz_cotas:
                        alt_min = matriz_cotas[n_puro]["min"]
                        alt_max = matriz_cotas[n_puro]["max"]
                        alt_promedio = matriz_cotas[n_puro]["prom"]
                        indice_forma = 0
                        perimetro = 0
                        
                        cache_key = f"morph_{territorio_str}"
                        st.session_state[cache_key] = {
                            "alt_min_m": alt_min, 
                            "alt_max_m": alt_max, 
                            "alt_prom_m": alt_promedio,
                            "indice_forma": indice_forma,
                            "perimetro_km": perimetro
                        }
                        st.info(f"⚡ **Optimización:** Usando cotas maestras fijadas para {n_puro}.")
                        
                    elif not es_escala_masiva:
                        # 🛡️ CIRUGÍA: Memoria Caché para que el Slider no borre las alturas
                        cache_key = f"morph_{territorio_str}"
                        if cache_key in st.session_state:
                            morph = st.session_state[cache_key]
                            alt_promedio = morph.get("alt_prom_m", 2000)
                            alt_min = morph.get("alt_min_m", 0)
                            alt_max = morph.get("alt_max_m", 4000)
                            indice_forma = morph.get("indice_forma", 0)
                            perimetro = morph.get("perimetro_km", 0)
                        else:
                            # 1. Intentar Base de Datos (Instantáneo y Seguro)
                            exito_bd = False
                            try:
                                with get_engine().connect() as conn:
                                    q_m = text('SELECT * FROM matriz_hidrogeomorfologica_maestra WHERE "Territorio" ILIKE :t LIMIT 1')
                                    df_m = pd.read_sql(q_m, conn, params={"t": f"%{n_puro}%"})
                                    if not df_m.empty:
                                        col_min = next((c for c in df_m.columns if 'min' in c.lower()), None)
                                        col_max = next((c for c in df_m.columns if 'max' in c.lower()), None)
                                        col_prom = next((c for c in df_m.columns if 'media' in c.lower() or 'prom' in c.lower()), None)
                                        if col_min and pd.notna(df_m.iloc[0][col_min]): alt_min = int(df_m.iloc[0][col_min])
                                        if col_max and pd.notna(df_m.iloc[0][col_max]): alt_max = int(df_m.iloc[0][col_max])
                                        if col_prom and pd.notna(df_m.iloc[0][col_prom]): alt_promedio = int(df_m.iloc[0][col_prom])
                                        exito_bd = True
                                        st.session_state[cache_key] = {"alt_min_m": alt_min, "alt_max_m": alt_max, "alt_prom_m": alt_promedio, "indice_forma": 0, "perimetro_km": 0}
                            except: pass
                            
                            # 2. Si no está en BD, usar el Raster UNA SOLA VEZ y guardarlo en memoria
                            if not exito_bd:
                                morph = calculate_morphometry(gdf_zona, dem_path=ruta_dem_nube)
                                alt_promedio = morph.get("alt_prom_m", 2000)
                                alt_min = morph.get("alt_min_m", 0)
                                alt_max = morph.get("alt_max_m", 4000)
                                indice_forma = morph.get("indice_forma", 0)
                                perimetro = morph.get("perimetro_km", 0)
                                st.session_state[cache_key] = morph
                    else:
                        st.info("⚡ **Optimización de Rendimiento:** Procesamiento raster 3D detallado desactivado para escalas mayores. Usando estimación genérica.")
                        alt_min, alt_max, alt_promedio = 0, 4000, 1500

                if alt_max <= alt_min: alt_max = alt_min + 100
                # 🛡️ FIX: Paso dinámico para evitar que Streamlit se congele en cuencas planas
                paso_slider = max(1, int((alt_max - alt_min) / 20))

                st.sidebar.subheader("⛰️ Gestión 3D (Hipsometría)")
                
                import re
                clave_slider = re.sub(r'[^a-zA-Z0-9]', '_', str(territorio_str))
                cota_gestion = st.sidebar.slider("Cota de Gestión (msnm):", int(alt_min), int(alt_max), int(alt_min), step=paso_slider, key=f"sl_hipso_{clave_slider}")

                area_cota_km2 = area_km2
                etp_cota = etp_real.copy()
                area_porcentaje = 100.0

                if cota_gestion > alt_min:
                    coefs = st.session_state.get('coefs_hipso', None)
                    if coefs and coefs.get('C3') is not None:
                        # Extraemos coeficientes de la sesión (guardados por la nueva matriz)
                        a_relativa = (coefs['C3']*(cota_gestion**3)) + (coefs['C2']*(cota_gestion**2)) + (coefs['C1']*cota_gestion) + coefs['C0']
                        area_porcentaje = max(0.0, min(100.0, float(a_relativa)))
                    else:
                        area_porcentaje = max(0.0, 100.0 * (1.0 - ((cota_gestion - alt_min) / (alt_max - alt_min))))
                        
                    # 3. APLICACIÓN DE LA REDUCCIÓN AL BALANCE
                    area_cota_km2 = area_km2 * (area_porcentaje / 100.0)
                    
                    # Castigo a la ETP por altitud térmica
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
                    ["🟢 Condición Hidrológica Normal (Línea Base)", "🔴 Fenómeno de El Niño", "🔵 Fenómeno de La Niña", "🟡 SSP2-4.5 (2050)", "🔥 SSP5-8.5 (2050)"]
                )

                factor_ppt, factor_etp = 1.0, 1.0
                if "Niño" in escenario_climatico: factor_ppt, factor_etp = 0.65, 1.15
                elif "Niña" in escenario_climatico: factor_ppt, factor_etp = 1.40, 0.90
                elif "SSP2" in escenario_climatico: factor_ppt, factor_etp = 0.95, 1.10
                elif "SSP5" in escenario_climatico: factor_ppt, factor_etp = 0.85, 1.25

                # =================================================================
                # 🧠 NEXO CLIMÁTICO MAESTRO: Extracción Geoespacial Pura (IDEAM)
                # =================================================================
                precip_base = datos.get("precipitacion", [])
                if not precip_base or len(precip_base) < 12:
                    precip_base = [0.0] * 12 # 🛡️ Paracaídas anti-colapsos
                fuente_clima = "Modelo Espacial Integrado (Estaciones IDEAM)"
                # =================================================================

                precip_media = [p * factor_ppt for p in precip_base]
                etp_cota = [e * factor_etp for e in etp_cota]

                if factor_ppt != 1.0:
                    st.warning(f"⚠️ **Proyección Climática Activa:** {escenario_climatico}. \n\n☔ Lluvia al **{factor_ppt*100:.0f}%** y ☀️ Evapotranspiración al **{factor_etp*100:.0f}%**.")

                precip_max = [p * 1.30 for p in precip_media]
                precip_min = [p * 0.70 for p in precip_media]

                balance_medio = calcular_balance_mensual(precip_media, etp_cota, area_cota_km2, factor_recarga_base=factor_infiltracion)
                balance_humedo = calcular_balance_mensual(precip_max, etp_cota, area_cota_km2, factor_recarga_base=factor_infiltracion)
                balance_seco = calcular_balance_mensual(precip_min, etp_cota, area_cota_km2, factor_recarga_base=factor_infiltracion)

                # =========================================================================
                # 🧽 FILTRO DE RECESIÓN: EFECTO ESPONJA (REZAGO SUBTERRÁNEO)
                # =========================================================================
                def aplicar_efecto_esponja(caudales_crudos, factor_retencion=0.45):
                    # 🛡️ Blindaje contra Numpy arrays o listas vacías
                    if type(caudales_crudos).__name__ == 'ndarray' and caudales_crudos.size < 12: return [0.0]*12, [0.0]*12
                    elif type(caudales_crudos).__name__ != 'ndarray' and not caudales_crudos: return [0.0]*12, [0.0]*12
                    
                    caudales_suavizados, caudal_base = [], []
                    memoria_acuifero = (sum(caudales_crudos) / 12) * factor_retencion
                    
                    # 🚀 FIX: range(24) garantiza que 'i' llegue hasta 23 y se guarden los datos.
                    for i in range(24):
                        q_in = caudales_crudos[i % 12]
                        aporte_subterraneo = memoria_acuifero * 0.35 
                        q_out = (q_in * (1 - factor_retencion)) + aporte_subterraneo
                        memoria_acuifero = (memoria_acuifero * 0.65) + (q_in * factor_retencion)
                        
                        if i >= 12: 
                            caudales_suavizados.append(max(0.02, q_out)) 
                            caudal_base.append(max(0.01, aporte_subterraneo))
                            
                    return caudales_suavizados, caudal_base

                q_medio_suavizado, q_base_real = aplicar_efecto_esponja(balance_medio.get("caudal_m3s", [0.0]*12))
                q_humedo_suavizado, _ = aplicar_efecto_esponja(balance_humedo.get("caudal_m3s", [0.0]*12))
                q_seco_suavizado, _ = aplicar_efecto_esponja(balance_seco.get("caudal_m3s", [0.0]*12))

                balance_medio["caudal_m3s"] = q_medio_suavizado
                balance_humedo["caudal_m3s"] = q_humedo_suavizado
                balance_seco["caudal_m3s"] = q_seco_suavizado

                # =========================================================================
                # 📈 RENDERIZADO VISUAL: GRÁFICO HIDRO-CLIMÁTICO (LAS 7 VARIABLES)
                # =========================================================================
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                
                # Y1 (Láminas)
                fig.add_trace(go.Bar(x=datos["meses"], y=precip_media, name="Precipitación (mm)", marker_color='#3498db', opacity=0.6), secondary_y=False)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_medio.get("exceso_total", [0]*12), name="Agua Excedente / Escorrentía", fill='tozeroy', mode='none', fillcolor='rgba(41, 128, 185, 0.4)'), secondary_y=False)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_medio.get("etr", [0]*12), name="ETR Real (mm)", mode='lines+markers', line=dict(color='#27ae60', width=3)), secondary_y=False)
                fig.add_trace(go.Scatter(x=datos["meses"], y=etp_cota, name="ETP Potencial (mm)", mode='lines', line=dict(color='#e74c3c', width=2, dash='dot')), secondary_y=False)
                
                # Y2 (Caudales)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_humedo.get("caudal_m3s", [0]*12), name="Max", mode='lines', line=dict(color='rgba(142, 68, 173, 0)'), showlegend=False), secondary_y=True)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_seco.get("caudal_m3s", [0]*12), name="Rango Histórico", mode='lines', line=dict(color='rgba(142, 68, 173, 0)'), fill='tonexty', fillcolor='rgba(142, 68, 173, 0.15)'), secondary_y=True)
                fig.add_trace(go.Scatter(x=datos["meses"], y=balance_medio.get("caudal_m3s", [0]*12), name="Caudal Medio (m³/s)", mode='lines', line=dict(color='#8e44ad', width=4)), secondary_y=True)
                fig.add_trace(go.Scatter(x=datos["meses"], y=q_base_real, name="Caudal Base (Aporte Subterráneo)", mode='lines', line=dict(color='saddlebrown', width=2, dash='dash'), showlegend=True), secondary_y=True)

                fig.update_layout(
                    hovermode="x unified", template="plotly_white", margin=dict(l=20, r=50, t=80, b=20), height=500, 
                    legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
                )
                fig.update_yaxes(title_text="Lámina de Agua (mm)", secondary_y=False)
                fig.update_yaxes(title_text="Caudal (m³/s)", secondary_y=True, showgrid=False)
                
                with st.expander(f"📊 Ver Gráfico Hidro-Climático", expanded=True):
                    st.plotly_chart(fig, use_container_width=True)

                lluvia_total = sum(precip_media)
                etp_total = sum(etp_cota)
                etr_total = sum(balance_medio.get("etr", [0]*12))
                recarga_total = sum(balance_medio.get("recarga", [0]*12))
                caudal_medio = sum(balance_medio.get("caudal_m3s", [0]*12)) / 12

                # ---------------------------------------------------------
                # 📑 SÍNTESIS PARAMÉTRICA TERRITORIAL Y DIAGNÓSTICO
                # ---------------------------------------------------------
                # 🛡️ FIX: Aseguramos que las variables recojan la matemática fresca de la esponja
                lluvia_total = sum(precip_media)
                etp_total = sum(etp_cota)
                caudal_medio = sum(balance_medio.get("caudal_m3s", [0.0]*12)) / 12
                recarga_total = sum(balance_medio.get("recarga", [0.0]*12))
                
                st.markdown("---")
                with st.expander("📑 Síntesis Paramétrica Territorial", expanded=True):
                    tc1, tc2, tc3 = st.columns(3)
                    with tc1:
                        st.markdown("##### 🏔️ Morfometría (Satélite)")
                        st.write(f"- **Área Total:** {area_km2:,.1f} km²")
                        st.write(f"- **Área Activa:** {area_cota_km2:,.1f} km² ({area_porcentaje:.1f}%)")
                        st.write(f"- **Altitud Promedio:** {alt_promedio:,.0f} msnm")
                        st.write(f"- **Rango Altimétrico:** {alt_min:,.0f} - {alt_max:,.0f} msnm")
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

                rendimiento_lsk = (caudal_medio * 1000) / area_cota_km2 if area_cota_km2 > 0 else 0
                
                with st.expander("🤖 Ver Diagnóstico Hidro-Climático Automático", expanded=True):
                    oferta_bruta = lluvia_total - etp_total
                    recarga_acuifero = st.session_state.get('recarga_acuifero_mm', oferta_bruta * 0.15) 
                    caudal_ecologico_mm = oferta_bruta * 0.25 
                    oferta_neta = oferta_bruta - recarga_acuifero - caudal_ecologico_mm
                    
                    st.markdown("### Análisis del Sistema")
                    if oferta_neta > 0:
                        st.success(f"💧 **Estado Estructural:** Superávit hídrico natural. La lluvia supera la evapotranspiración, dejando una **Oferta Neta de {oferta_neta:,.0f} mm/año** (descontando {recarga_acuifero:,.0f} mm de recarga de acuíferos y {caudal_ecologico_mm:,.0f} mm de caudal ecológico).")
                    elif oferta_bruta > 0:
                        st.warning(f"⚠️ **Estado Estructural:** Tensión hídrica. Hay excedente bruto, pero al descontar acuíferos y caudal ecológico, la Oferta Neta es deficitaria ({oferta_neta:,.0f} mm/año).")
                    else:
                        st.error(f"🏜️ **Estado Estructural:** Déficit crónico. La evapotranspiración potencial supera la lluvia.")
                    st.markdown(f"🌊 **Productividad Hídrica:** La cuenca produce **{rendimiento_lsk:.1f} Litros/segundo por cada km²**.")

                # =========================================================================
                # 8. LABORATORIO HIDROSOCIAL WEAP (AVANZADO E INTEGRADO)
                # =========================================================================
                st.markdown("---")
                st.subheader(f"⚖️ Simulador Hidrosocial WEAP: {territorio_str}")

                # 🛡️ 1. Extracción Dinámica de Presiones RURH y Población (Memoria Aleph)
                pob_bd = 50000.0
                try:
                    from modules.demografia_tools import calcular_poblacion_al_vuelo
                    df_pob = calcular_poblacion_al_vuelo(territorio_str, nivel_jerarquico, "Total", anio_especifico=anio_analisis)
                    if df_pob is not None and not df_pob.empty: pob_bd = float(df_pob['Total'].iloc[0])
                except Exception: pass
                
                rurh_bd_m3s = float(st.session_state.get('aleph_concesiones_m3s', 0.0))

                # 🛡️ 2. Paneles de Control WEAP (4 Columnas - Sincronizados)
                wc1, wc2, wc3, wc4 = st.columns(4)
                
                with wc1:
                    st.markdown("##### ⛰️ Física y Oferta")
                    # El Hipsómetro asume el control de la bocatoma
                    st.info(f"📍 **Captación:** {cota_gestion} msnm *(Controlada por el Hipsómetro izquierdo)*")
                    
                    var_clima_weap = st.slider("Variación Oferta Hídrica %", -50, 50, 0, 5, key="var_clima_weap", help="Ajuste fino de disponibilidad de caudal. Ideal para simular escenarios combinados (Ej: Escenario SSP5 en el panel maestro + Sequía extrema temporal en este panel).")
                    if var_clima_weap != 0:
                        st.warning(f"⚠️ **Efecto Combinado Activado:** Se está alterando la oferta hídrica simulada en {var_clima_weap:+}%. Esto se suma al escenario climático seleccionado en el panel lateral.")
                        
                    castigo_calidad = st.slider("Castigo Calidad %", 0, 100, 0, 5, help="Fracción del río no apta por contaminación.")
                    
                with wc2:
                    st.markdown("##### 👥 Presiones Humanas")
                    pob_weap = st.number_input("Población Base (hab):", min_value=0.0, value=float(pob_bd), step=1000.0)
                    dotacion_weap = st.number_input("Dotación (L/hab/día):", min_value=50, max_value=400, value=150)
                    var_pob = st.slider("Crecimiento Flotante %", 0, 100, 0, 5)

                with wc3:
                    st.markdown("##### 🏭 RURH y Retornos")
                    tope_rurh = max(caudal_medio * 2, rurh_bd_m3s * 1.5, 0.1)
                    var_rurh = st.slider("Concesiones RURH (m³/s)", 0.0, float(tope_rurh), float(rurh_bd_m3s), 0.01)
                    var_retorno = st.slider("Retorno de Aguas %", 0, 100, 80, 5)
                    var_reuso = st.slider("Reuso Industrial %", 0, 100, 0, 5)

                with wc4:
                    st.markdown("##### 🛡️ Regulación y Mitigación")
                    caudal_eco_pct = st.slider("Q. Ecológico Exigido %", 10, 50, 25, 5)
                    var_eficiencia = st.slider("Eficiencia Acueducto %", 0, 50, 0, 5)
                    capacidad_tanque_hm3 = st.number_input("Embalse / Tanque (Hm³):", 0.0, 100.0, 0.0, 0.1)

                # 🛡️ 3. Matemática WEAP Integrada y Corregida (Lógica de Extracción Total)
                def pad_12(arr): return list(arr)[:12] + [0.0] * max(0, 12 - len(arr))
                
                # Sincronía 1:1 con el Caudal maestro + Modificador de Efectos Combinados
                caudal_bruto_base = np.array(pad_12(balance_medio.get("caudal_m3s", [])))
                caudal_bruto_mensual = caudal_bruto_base * (1.0 + (var_clima_weap / 100.0)) * (1.0 - (castigo_calidad / 100.0))
                
                q_ecologico = caudal_bruto_mensual * (caudal_eco_pct / 100.0)
                oferta_neta_mensual = np.maximum(0, caudal_bruto_mensual - q_ecologico)

                demanda_humana_bruta = ((pob_weap * (1 + var_pob/100.0)) * dotacion_weap) / (1000 * 86400)
                demanda_humana_neta = demanda_humana_bruta * (1 - (var_eficiencia / 100.0))
                retorno_humano = demanda_humana_neta * (var_retorno / 100.0)

                demanda_rurh_neta = var_rurh * (1 - (var_reuso / 100.0))
                retorno_rurh = demanda_rurh_neta * (var_retorno / 100.0) 

                demanda_extractiva_total = demanda_humana_neta + demanda_rurh_neta
                retorno_total = retorno_humano + retorno_rurh
                consumo_consuntivo_total = demanda_extractiva_total - retorno_total

                y_demanda_visual = np.full(12, demanda_extractiva_total)
                y_consumo_real = np.full(12, consumo_consuntivo_total)

                volumen_embalse_actual_hm3 = capacidad_tanque_hm3 * 0.5 
                deficit_array = np.zeros(12)
                volumen_historico = np.zeros(12)

                for i in range(12):
                    # 💡 EL BUG DEL DÉFICIT OCULTO ESTABA AQUÍ:
                    # El déficit debe detonar contra lo que físicamente intentamos extraer del río (Extracción Total)
                    intento_extraccion = demanda_extractiva_total
                    
                    if oferta_neta_mensual[i] >= intento_extraccion:
                        sobrante = oferta_neta_mensual[i] - intento_extraccion
                        volumen_embalse_actual_hm3 += (sobrante * 3600 * 24 * 30 / 1e6)
                        deficit_array[i] = 0.0
                    else:
                        falta_m3s = intento_extraccion - oferta_neta_mensual[i]
                        falta_hm3 = falta_m3s * 3600 * 24 * 30 / 1e6
                        if volumen_embalse_actual_hm3 >= falta_hm3:
                            volumen_embalse_actual_hm3 -= falta_hm3
                            deficit_array[i] = 0.0
                        else:
                            deficit_hm3 = falta_hm3 - volumen_embalse_actual_hm3
                            deficit_array[i] = deficit_hm3 * 1e6 / (3600 * 24 * 30)
                            volumen_embalse_actual_hm3 = 0.0
                            
                    if volumen_embalse_actual_hm3 > capacidad_tanque_hm3:
                        volumen_embalse_actual_hm3 = capacidad_tanque_hm3 
                        
                    volumen_historico[i] = volumen_embalse_actual_hm3

                # 🛡️ 4. Gráfica Espectacular (Manchas Café Detonadas por Extracción)
                st.markdown("##### Dinámica Hidrosocial Completa (Clima, Oferta y Demanda)")
                fig_w = make_subplots(specs=[[{"secondary_y": True}]])
                meses_str = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
                
                fig_w.add_trace(go.Bar(x=meses_str, y=pad_12(precip_media), name="Precipitación (mm)", marker_color='rgba(52, 152, 219, 0.3)'), secondary_y=True)
                fig_w.add_trace(go.Bar(x=meses_str, y=pad_12(balance_medio.get("recarga", [])), name="Recarga Acuíferos (mm)", marker_color='rgba(46, 204, 113, 0.4)'), secondary_y=True)
                fig_w.add_trace(go.Scatter(x=meses_str, y=pad_12(balance_medio.get("etr", [])), name="ETR Real (mm)", mode='lines+markers', line=dict(color='#27ae60', width=1, dash='dot')), secondary_y=True)
                fig_w.add_trace(go.Scatter(x=meses_str, y=pad_12(etp_cota), name="ETP Potencial (mm)", mode='lines', line=dict(color='#e74c3c', width=1, dash='dot')), secondary_y=True)
                
                caudal_maximo = caudal_bruto_mensual * 1.30
                caudal_minimo = caudal_bruto_mensual * 0.70

                fig_w.add_trace(go.Scatter(x=meses_str, y=caudal_maximo, name="Max", mode='lines', line=dict(width=0), showlegend=False), secondary_y=False)
                fig_w.add_trace(go.Scatter(x=meses_str, y=caudal_minimo, name="Rango Histórico de Oferta", mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(41, 128, 185, 0.1)'), secondary_y=False)

                fig_w.add_trace(go.Scatter(x=meses_str, y=caudal_bruto_mensual, name='Oferta Bruta', hovertemplate="<b>Oferta Bruta</b><br>%{y:.3f} m³/s<extra></extra>", line=dict(color='#95a5a6', width=2, dash='dot')), secondary_y=False)
                fig_w.add_trace(go.Scatter(x=meses_str, y=oferta_neta_mensual, name='Oferta Neta', hovertemplate="<b>Oferta Neta</b><br>%{y:.3f} m³/s<extra></extra>", line=dict(color='#2980b9', width=4)), secondary_y=False)
                fig_w.add_trace(go.Scatter(x=meses_str, y=y_demanda_visual, name='Extracción Total', hovertemplate="<b>Extracción Total</b><br>%{y:.3f} m³/s<extra></extra>", line=dict(color='#e74c3c', width=2)), secondary_y=False)
                fig_w.add_trace(go.Scatter(x=meses_str, y=y_consumo_real, name='Consumo Consuntivo', hovertemplate="<b>Consumo Consuntivo</b><br>%{y:.3f} m³/s<extra></extra>", line=dict(color='black', width=2, dash='dash')), secondary_y=False)
                
                if capacidad_tanque_hm3 > 0:
                    fig_w.add_trace(go.Bar(x=meses_str, y=volumen_historico, name='Volumen Embalse (Hm³)', marker_color='rgba(241, 196, 15, 0.6)'), secondary_y=False)

                if np.sum(deficit_array) > 0:
                    fig_w.add_trace(go.Scatter(x=meses_str, y=oferta_neta_mensual, showlegend=False, hoverinfo='skip', line=dict(width=0)), secondary_y=False)
                    # 💡 FIX VISUAL: La mancha café se dibuja exactamente entre la Oferta Neta y la Extracción Total
                    fig_w.add_trace(go.Scatter(x=meses_str, y=np.maximum(oferta_neta_mensual, y_demanda_visual), name='⚠️ DÉFICIT CRÍTICO', fill='tonexty', fillcolor='rgba(0, 0, 0, 0.6)', line=dict(width=0)), secondary_y=False)

                techo_y = max(np.max(caudal_maximo), np.max(y_demanda_visual)) * 1.1
                fig_w.update_yaxes(range=[0, techo_y if techo_y > 0 else 1.0], title_text="Caudal Extraíble (m³/s)", secondary_y=False)
                fig_w.update_yaxes(title_text="Lámina Climática (mm)", secondary_y=True, showgrid=False)
                fig_w.update_layout(hovermode="x unified", template="plotly_white", margin=dict(l=20, r=50, t=20, b=20), height=500, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5))
                st.plotly_chart(fig_w, use_container_width=True)

                # 🛡️ 5. Diagnóstico Clínico, Oráculo y Matriz Expandida
                df_weap = pd.DataFrame({
                    "Mes": meses_str,
                    "Area_Aportante_km2": [round(x, 2) for x in pad_12([area_cota_km2]*12)],
                    "Precipitacion_mm": [round(x, 1) for x in pad_12(precip_media)],
                    "ETP_Potencial_mm": [round(x, 1) for x in pad_12(etp_cota)],
                    "ETR_Real_mm": [round(x, 1) for x in pad_12(balance_medio.get("etr", []))],
                    "Recarga_Acuifero_mm": [round(x, 1) for x in pad_12(balance_medio.get("recarga", []))],
                    "Oferta_Bruta_m3s": [round(x, 3) for x in pad_12(caudal_bruto_mensual)],
                    "Caudal_Ecologico_m3s": [round(x, 3) for x in pad_12(q_ecologico)],
                    "Oferta_Neta_Libre_m3s": [round(x, 3) for x in pad_12(oferta_neta_mensual)],
                    "Extraccion_Total_m3s": [round(x, 3) for x in pad_12(y_demanda_visual)],
                    "Consumo_Consuntivo_m3s": [round(x, 3) for x in pad_12(y_consumo_real)],
                    "Vol_Embalse_Hm3": [round(x, 3) for x in pad_12(volumen_historico)],
                    "Deficit_m3s": [round(x, 3) for x in pad_12(deficit_array)]
                })

                st.markdown("---")
                wc_diag, wc_matriz = st.columns([1, 1])

                with wc_diag:
                    with st.expander("🩺 Diagnóstico Clínico Integral", expanded=True):
                        st.markdown("##### 🔬 Síntesis Física Activa")
                        st.write(f"- **Área Aportante Real:** {area_cota_km2:,.1f} km² ({area_porcentaje:.1f}% calculada de la cuenca original).")
                        st.write(f"- **Clima Base:** Integración Geoespacial IDEAM")
                        st.write(f"- **Oferta Bruta Promedio:** {caudal_bruto_mensual.mean():.3f} m³/s")
                        st.write(f"- **Caudal Ecológico Retenido:** {q_ecologico.mean():.3f} m³/s")
                        st.write(f"- **Dinámica Subterránea:** {sum(pad_12(balance_medio.get('recarga', []))):.1f} mm/año.")

                        meses_criticos = df_weap[df_weap['Deficit_m3s'] > 0]
                        if meses_criticos.empty:
                            st.success("✅ **Sistema en Equilibrio:** La Oferta Neta y reservas soportan el consumo actual.")
                            if demanda_extractiva_total < 0.05:
                                st.warning("⚠️ **Nota Analítica:** Extracción microscópica frente al río. Para estresar el sistema, eleva concesiones RURH.")
                        else:
                            st.error(f"⚠️ **Colapso Hídrico Detectado:** Déficit durante {len(meses_criticos)} meses.")
                            peor = meses_criticos.loc[meses_criticos['Deficit_m3s'].idxmax()]
                            st.markdown(f"**Pico de Crisis:** {peor['Mes']}, con un faltante de {peor['Deficit_m3s']} m³/s.")
                            st.markdown("##### 💡 Prescripción de Mitigación:")
                            if consumo_consuntivo_total > oferta_neta_mensual.mean() and capacidad_tanque_hm3 == 0:
                                st.write("- 🏗️ **Falta Regulación:** Necesitas aumentar la capacidad del embalse para guardar agua del invierno.")
                            if var_eficiencia < 20:
                                st.write("- 🚰 **Ineficiencia Urbana:** Aumenta la eficiencia del acueducto para reducir pérdidas.")

                        st.markdown("##### 🔮 Oráculo Prospectivo (Proyección de Crisis)")
                        litros_disponibles_dia = max(0, (oferta_neta_mensual.mean() - demanda_rurh_neta)) * 86400 * 1000
                        pob_maxima = litros_disponibles_dia / dotacion_weap if dotacion_weap > 0 else 0
                        
                        oferta_nino = oferta_neta_mensual.mean() * 0.70 
                        litros_nino_dia = max(0, (oferta_nino - demanda_rurh_neta)) * 86400 * 1000
                        pob_maxima_nino = litros_nino_dia / dotacion_weap if dotacion_weap > 0 else 0

                        anio_crisis = "Estable hasta 2050+"
                        anio_crisis_nino = "Estable hasta 2050+"
                        
                        try:
                            n_puro = territorio_str.split(" - (")[0].strip()
                            df_evo = pd.read_sql(text('SELECT "año", "Pob_Base" FROM matriz_maestra_demografica WHERE "LLAVE_UNIVERSAL" ILIKE :t'), get_engine(), params={"t": f"%{n_puro}%"})
                            if not df_evo.empty:
                                df_c = df_evo[(df_evo['año'] >= anio_analisis) & (df_evo['Pob_Base'] > pob_maxima)]
                                if not df_c.empty: anio_crisis = str(df_c.iloc[0]['año'])
                                df_cn = df_evo[(df_evo['año'] >= anio_analisis) & (df_evo['Pob_Base'] > pob_maxima_nino)]
                                if not df_cn.empty: anio_crisis_nino = str(df_cn.iloc[0]['año'])
                        except: pass

                        st.write(f"- 👥 **Población Límite (Sostenible):** {pob_maxima:,.0f} habs.")
                        st.write(f"- 📅 **Año de colapso demográfico natural:** {anio_crisis}.")
                        st.write(f"- 🔥 **Año de colapso bajo El Niño (-30% Oferta):** {anio_crisis_nino}.")

                        st.info("💡 **Glosario Hidrosocial:**  \n* **Oferta Bruta:** Caudal natural del río provisto por la lluvia. \n* **Oferta Neta:** Agua disponible en el río *descontando* el caudal ecológico. \n* **Extracción:** Agua total que entra a los tubos. \n* **Consumo Consuntivo:** Agua que no retorna al cauce.")

                with wc_matriz:
                    st.markdown("##### 📋 Matriz de Balances Total")
                    csv_weap = df_weap.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Descargar Matriz Expandida (CSV)", data=csv_weap, file_name=f"Matriz_WEAP_{territorio_str}.csv", mime="text/csv", use_container_width=True)
                    st.dataframe(df_weap.style.format(precision=2), use_container_width=True, height=550)

        except Exception as e:
            st.error(f"🔌 Error de procesamiento: {e}")