# pages/03_🗺️_Isoyetas_HD.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sqlalchemy import text
import geopandas as gpd
import os
import sys

# --- IMPORTACIÓN ROBUSTA DE MÓDULOS ---
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules.config import Config
    from modules import db_manager, selectors
    from modules.interpolation import interpolador_maestro 
    try:
        from modules.data_processor import complete_series
    except ImportError:
        complete_series = None
except:
    from modules import db_manager, selectors
    from modules.config import Config
    from modules.interpolation import interpolador_maestro
    complete_series = None

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Isoyetas HD", page_icon="🗺️", layout="wide")
st.title("🗺️ Generador Avanzado de Isoyetas (Escenarios & Pronósticos)")

# ==========================================
# 📂 NUEVO: MENÚ DE NAVEGACIÓN PERSONALIZADO
# ==========================================
# Llama al menú expandible y resalta la página actual
selectors.renderizar_menu_navegacion("Isoyetas HD")

# ==========================================
# SECCIÓN DE UI: SELECTORES DE INTERPOLACIÓN
# ==========================================
st.sidebar.markdown("### ⚙️ Configuración del Modelo")

opciones_metodo = {
    "Kriging Ordinario": "kriging",
    "Kriging con Deriva Externa (KED)": "ked",
    "Spline (Thin Plate)": "spline",
    "Distancia Inversa (IDW)": "idw",
    "Tendencia Lineal": "trend"
}

metodo_seleccionado = st.sidebar.selectbox("Método de Interpolación:", options=list(opciones_metodo.keys()), index=0)
metodo_codigo = opciones_metodo[metodo_seleccionado]

modelo_var_codigo = 'spherical'
if "Kriging" in metodo_seleccionado:
    modelo_var_seleccionado = st.sidebar.selectbox("Modelo de Variograma:", options=["Esférico", "Exponencial", "Gaussiano"], index=0)
    mapa_variogramas = {"Esférico": "spherical", "Exponencial": "exponential", "Gaussiano": "gaussian"}
    modelo_var_codigo = mapa_variogramas[modelo_var_seleccionado]

# ==============================================================================
# 🧠 3. SELECTOR ESPACIAL GLOBAL Y CONEXIÓN ALEPH (Topología Estricta)
# ==============================================================================
try:
    ids_sel_dummy, nombre_zona_raw, alt_ref, gdf_zona_dummy, nivel_jerarquico_raw = selectors.render_selector_espacial()
except Exception as e:
    st.error(f"Error en selector: {e}")
    st.stop()

# 🚀 CONEXIÓN ALEPH
nombre_zona = st.session_state.get('aleph_lugar', nombre_zona_raw)
nivel_jerarquico = st.session_state.get('aleph_escala', nivel_jerarquico_raw)

# 🚀 FIX: Suavizamos la barrera
if not nombre_zona or str(nombre_zona).strip() in ["", "None", "-- Seleccione --"]:
    st.info("👈 Seleccione un Territorio (Cuenca, Municipio o Región) en el menú lateral para iniciar.")
    st.stop()

# 🪂 FUNCIÓN CACHEADA GLOBALMENTE (Fuera de los bloques if para evitar fallos de Streamlit)
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_territorio_maestro():
    import geopandas as gpd
    import requests, io
    url = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson"
    try:
        # 🚀 FIX: Timeout de 60s para asegurar la descarga de archivos grandes
        res = requests.get(url, timeout=60) 
        if res.status_code == 200:
            gdf = gpd.read_file(io.BytesIO(res.content))
            gdf.columns = [c.lower().strip() for c in gdf.columns]
            return gdf
    except Exception as e:
        print(f"Error descargando TerritorioMaestro: {e}")
    return gpd.GeoDataFrame()

# 🚀 RESCATE ESTRUCTURAL: Usar el caché de memoria viva (Si existe)
gdf_zona = None
if 'aleph_poligono' in st.session_state and st.session_state['aleph_poligono'] is not None and not st.session_state['aleph_poligono'].empty:
    gdf_zona = st.session_state['aleph_poligono']

# 🪂 PARACAÍDAS CARTOGRÁFICO ESTRUCTURAL
if gdf_zona is None or gdf_zona.empty:
    with st.spinner("🪂 Sincronizando topología estricta desde la matriz maestra..."):
        try:
            import geopandas as gpd
            import unicodedata
            import re
            import pandas as pd
            
            def norm_text(t):
                if not isinstance(t, str) or pd.isna(t): return ""
                return unicodedata.normalize('NFKD', t.lower().strip()).encode('ascii', 'ignore').decode('utf-8')

            # 🗺️ DICCIONARIO DE TRADUCCIÓN
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
                "bolivar": "CIUDAD BOLIVAR"
            }

            lugar_crudo = str(nombre_zona).replace("CAR: ", "").strip()
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

            # --- 1. BÚSQUEDA DE CUENCAS ---
            if es_cuenca:
                from modules.data_processor import load_and_process_all_data
                _, _, _, _, gdf_subcuencas, _ = load_and_process_all_data()
                
                if gdf_subcuencas is not None and not gdf_subcuencas.empty:
                    codigo_match = re.search(r'\((.*?)\)', str(nombre_zona))
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
                        terr_limpio = limpiar_texto(lugar_crudo)
                        mask_c = gdf_subcuencas.apply(lambda row: terr_limpio in limpiar_texto(str(row.to_dict().values())), axis=1)
                        if mask_c.any():
                            gdf_zona_tmp = gdf_subcuencas[mask_c]
                            gdf_zona = gpd.GeoDataFrame(geometry=[gdf_zona_tmp.unary_union], crs=gdf_subcuencas.crs)
                            encontrado = True

            # --- 2. BÚSQUEDA TERRITORIAL ESTRUCTURAL ---
            if not encontrado and not es_cuenca:
                gdf_tm = fetch_territorio_maestro() # Llamada segura a la caché global
                
                if not gdf_tm.empty:
                    if es_nacional or (es_departamento and ("ANTIOQUIA" in terr_norm or "COLOMBIA" in terr_norm)):
                        col_depto = 'dpto_cnmbr' if 'dpto_cnmbr' in gdf_tm.columns else 'departamento'
                        if col_depto in gdf_tm.columns and not es_nacional:
                            mask = gdf_tm[col_depto].apply(norm_text).isin(['antioquia'])
                        else:
                            mask = pd.Series(True, index=gdf_tm.index)
                            
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

            if encontrado:
                st.sidebar.success("🪂 ¡Polígono sincronizado (Topología Exacta)!")
            else:
                st.sidebar.error("⚠️ El polígono no existe en la matriz maestra.")
                
        except Exception as e:
            st.sidebar.error(f"Error de sincronización estructural: {e}")

st.sidebar.success(f"🔗 Conexión Aleph Activa: {nombre_zona}")

# Inicializamos la variable por seguridad
ids_sel = []

# --- 4. FUNCIONES DE SOPORTE CLOUD NATIVE ---
def detectar_columna(df, keywords):
    if df is None or df.empty: return None
    cols_orig = df.columns.tolist()
    for kw in keywords:
        kw_clean = kw.lower().replace('-', '').replace('_', '')
        for col in cols_orig:
            col_clean = col.lower().replace('-', '').replace('_', '')
            if kw_clean in col_clean:
                return col
    return None

@st.cache_data(ttl=600)
def obtener_estaciones_enriquecidas():
    """Obtiene las estaciones y las cruza con las cuencas en memoria (cero archivos locales)"""
    try:
        from modules.data_processor import load_and_process_all_data
        gdf_est, _, _, _, gdf_cuencas, _ = load_and_process_all_data()
        
        if gdf_est is None or gdf_est.empty:
            return pd.DataFrame(), False
            
        df_est = gdf_est.copy()
        
        # Extraer coordenadas para el motor de Isoyetas
        df_est['lat_calc'] = pd.to_numeric(df_est.geometry.y, errors='coerce')
        df_est['lon_calc'] = pd.to_numeric(df_est.geometry.x, errors='coerce')
        
        if gdf_cuencas is not None and not gdf_cuencas.empty:
            if gdf_cuencas.crs != df_est.crs: 
                gdf_cuencas = gdf_cuencas.to_crs(df_est.crs)
                
            # 🧹 BARRIDO FORENSE 1: Evitar el error index_right en el cruce de cuencas
            cols_drop = [c for c in df_est.columns if c in ['index_right', 'index_left']]
            if cols_drop: df_est = df_est.drop(columns=cols_drop)
            
            # Detectar columna de nombre de cuenca (nss3, nom_nss3 o nombre)
            col_cuenca = next((c for c in gdf_cuencas.columns if c.lower() in ['nss3', 'nom_nss3', 'nombre', 'subcuenca']), None)
            
            if col_cuenca:
                gdf_joined = gpd.sjoin(df_est, gdf_cuencas[[col_cuenca, 'geometry']], how='left', predicate='within')
                gdf_joined = gdf_joined.rename(columns={col_cuenca: 'CUENCA_GIS'})
                gdf_joined['CUENCA_GIS'] = gdf_joined['CUENCA_GIS'].fillna('Fuera de Jurisdicción')
                return gdf_joined, True
                
        return df_est, False
    except Exception as e:
        print(f"Error enriqueciendo estaciones: {e}")
        return pd.DataFrame(), False

# 🚀 FIX V3.0: Función de renderizado conectada a la memoria rápida
def add_context_layers_robust(fig, gdf_zona_actual, show_cuencas=False, show_muni=False):
    from modules.data_processor import load_and_process_all_data
    _, gdf_municipios, _, _, gdf_subcuencas, _ = load_and_process_all_data()
    
    # 1. LÍMITE DEL TERRITORIO SELECCIONADO
    if gdf_zona_actual is not None and not gdf_zona_actual.empty:
        gdf_z = gdf_zona_actual.to_crs("EPSG:4326")
        for _, r in gdf_z.iterrows():
            geom = r.geometry
            polys = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
            for p in polys:
                x, y = p.exterior.xy
                fig.add_trace(go.Scatter(x=list(x), y=list(y), mode='lines', line=dict(width=3, color='rgba(0,0,0,0.8)'), name="Límite", hoverinfo='skip'))
    
    # 2. CAPA DE CUENCAS (Desde Caché, ultra rápido)
    if show_cuencas and gdf_subcuencas is not None and not gdf_subcuencas.empty:
        gdf_cu = gdf_subcuencas.to_crs("EPSG:4326")
        gdf_cu['geom_simp'] = gdf_cu.geometry.simplify(0.005) # Suavizado para rendimiento
        for _, r in gdf_cu.iterrows():
            name = r.get('nom_nss3', r.get('nss3', r.get('nombre', 'Cuenca')))
            if pd.notnull(r['geom_simp']):
                polys = [r['geom_simp']] if r['geom_simp'].geom_type == 'Polygon' else list(r['geom_simp'].geoms)
                for p in polys:
                    x, y = p.exterior.xy
                    fig.add_trace(go.Scatter(x=list(x), y=list(y), mode='lines', line=dict(width=1.5, color='rgba(0, 100, 255, 0.8)'), text=f"🌊 {name}", hoverinfo='text', showlegend=False))

    # 3. CAPA DE MUNICIPIOS (Desde Caché)
    if show_muni and gdf_municipios is not None and not gdf_municipios.empty:
        gdf_m = gdf_municipios.to_crs("EPSG:4326")
        gdf_m['geom_simp'] = gdf_m.geometry.simplify(0.005)
        for _, r in gdf_m.iterrows():
            if pd.notnull(r['geom_simp']):
                nom_muni = r.get('municipio', 'Municipio')
                polys = [r['geom_simp']] if r['geom_simp'].geom_type == 'Polygon' else list(r['geom_simp'].geoms)
                for p in polys:
                    x, y = p.exterior.xy
                    fig.add_trace(go.Scatter(x=list(x), y=list(y), mode='lines', line=dict(width=0.7, color='rgba(100, 100, 100, 0.5)', dash='dot'), text=[nom_muni] * len(x), hovertemplate="<b>%{text}</b><extra></extra>", showlegend=False))

def calcular_pronostico(df_anual, target_year):
    proyecciones = []
    for station in df_anual['station_id'].unique():
        datos_est = df_anual[df_anual['station_id'] == station].dropna()
        if len(datos_est) >= 5: 
            try:
                x = datos_est['year'].values
                y = datos_est['total_anual'].values
                slope, intercept = np.polyfit(x, y, 1)
                pred = (slope * target_year) + intercept
                proyecciones.append({'station_id': station, 'valor': max(0, pred)}) 
            except: pass
    return pd.DataFrame(proyecciones)

def generar_analisis_texto_corregido(df_stats, tipo_analisis, config_text):
    if df_stats.empty: return "No hay datos suficientes."
    avg_val = df_stats['valor'].mean()
    min_val = df_stats['valor'].min()
    max_val = df_stats['valor'].max()
    diff = max_val - min_val
    
    try:
        est_max = df_stats.loc[df_stats['valor'].idxmax()]['nombre']
        est_min = df_stats.loc[df_stats['valor'].idxmin()]['nombre']
    except:
        est_max, est_min = "N/A", "N/A"
    
    if diff < 600: conclusion = "un comportamiento regional relativamente uniforme."
    elif diff < 1500: conclusion = "un gradiente de precipitación moderado."
    else: conclusion = "una **fuerte variabilidad orográfica**."
    
    return f"""
    ### 📝 Análisis Automático y Metadatos
    **⚙️ Parámetros de Modelación:**
    {config_text}

    **📊 Resultados Estadísticos:**
    * **Promedio Territorial:** {avg_val:,.0f} mm/año
    * **Rango de Variabilidad:** {diff:,.0f} mm
    * **Punto más Húmedo:** {est_max} ({max_val:,.0f} mm)
    * **Punto más Seco:** {est_min} ({min_val:,.0f} mm)
    * **Conclusión:** El territorio presenta {conclusion}
    """
    
def generar_raster_ascii(grid_z, minx, miny, cellsize, nrows, ncols):
    header = f"ncols        {ncols}\nnrows        {nrows}\nxllcorner    {minx}\nyllcorner    {miny}\ncellsize     {cellsize}\nNODATA_value -9999\n"
    grid_fill = np.nan_to_num(grid_z.T, nan=-9999)
    body = ""
    for row in np.flipud(grid_fill.T): 
        body += " ".join([f"{val:.2f}" for val in row]) + "\n"
    return header + body

# --- 5. SIDEBAR: CONFIGURACIÓN DEL MAPA ---
st.sidebar.header("⚙️ Configuración del Mapa")
tipo_analisis = st.sidebar.selectbox("📊 Modo de Análisis:", ["Año Específico", "Promedio Multianual", "Variabilidad Temporal", "Mínimo Histórico", "Máximo Histórico", "Pronóstico Futuro"])

params_analisis = {}
if tipo_analisis == "Año Específico":
    params_analisis['year'] = st.sidebar.selectbox("📅 Año:", range(2025, 1980, -1))
elif tipo_analisis in ["Promedio Multianual", "Variabilidad Temporal"]:
    params_analisis['start'], params_analisis['end'] = st.sidebar.slider("📅 Periodo:", 1980, 2025, (1990, 2020))
elif tipo_analisis == "Pronóstico Futuro":
    params_analisis['target'] = st.sidebar.slider("🔮 Proyección:", 2026, 2040, 2026)

paleta_colores = st.sidebar.selectbox("🎨 Escala de Color:", options=["YlGnBu", "Jet", "Portland", "Viridis", "RdBu"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🗺️ Capas Vectoriales")
ver_cuencas = st.sidebar.checkbox("✅ Ver Capa de Cuencas", value=True)
ver_municipios = st.sidebar.checkbox("🏙️ Ver Capa de Municipios", value=False)

c1, c2 = st.sidebar.columns(2)
ignore_zeros = c1.checkbox("🚫 No Ceros", value=True)
ignore_nulls = c2.checkbox("🚫 No Nulos", value=True)

do_interp_temp = False
if complete_series: do_interp_temp = st.sidebar.checkbox("🔄 Interpolación Temporal", value=False)

# 🚀 NUEVO: Interruptor del Mapa de Incertidumbre
ver_error = st.sidebar.checkbox("📉 Ver Incertidumbre (Varianza)", value=False, help="Muestra las zonas de mayor error predictivo (solo disponible para Kriging).")

# --- NUEVAS HERRAMIENTAS V3.0 (Resolución, Suavizado e Info) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🛠️ Herramientas de Renderizado")
grid_res = st.sidebar.slider("Resolución Espacial (Píxeles):", min_value=50, max_value=500, value=200, step=50, help="Mayor resolución = isoyetas más definidas pero carga más lenta.")
smooth_val = st.sidebar.slider("Suavizado de Curvas (Smooth):", min_value=0.0, max_value=1.3, value=1.0, step=0.1, help="0 = Cuadrículas crudas. 1.3 = Curvas muy fluidas.")

info_metodos = {
    "Kriging Ordinario": "Usa autocorrelación espacial. Ideal para modelar el clima regional.",
    "Kriging con Deriva Externa (KED)": "Permite usar la altitud como variable secundaria para mayor precisión en montañas.",
    "Spline (Thin Plate)": "Ajusta una superficie exacta por los puntos. Bueno para variaciones suaves.",
    "Distancia Inversa (IDW)": "Método clásico donde los pluviómetros cercanos tienen más peso.",
    "Tendencia Lineal": "Ajusta un plano general. Útil para ver grandes gradientes (ej. Norte-Sur)."
}
st.sidebar.info(f"💡 **Sobre {metodo_seleccionado}:**\n{info_metodos.get(metodo_seleccionado, '')}")

# --- 6. METADATOS Y ÁREA DE INFLUENCIA (BUFFER) ---
with st.spinner("Cargando catálogo de estaciones..."):
    gdf_meta, _ = obtener_estaciones_enriquecidas()

col_id = detectar_columna(gdf_meta, ['id_estacion', 'codigo']) or 'id_estacion'
col_nom = detectar_columna(gdf_meta, ['nombre', 'nom-est']) or 'nombre'
col_muni = detectar_columna(gdf_meta, ['municipio', 'mpio'])
col_alt = detectar_columna(gdf_meta, ['altitud' , 'alt_est'])
col_cuenca = 'CUENCA_GIS' if 'CUENCA_GIS' in gdf_meta.columns else None

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Área de Influencia (Buffer)")
buffer_km = st.sidebar.slider("Radio de Expansión (km):", min_value=0, max_value=50, value=15, step=5, 
                              help="Si el territorio está vacío, aumenta este radio para atrapar estaciones vecinas.")

# 🚀 FIX: Recalcular 'ids_sel' expandiendo el polígono geométricamente
if gdf_zona is not None and not gdf_zona.empty and not gdf_meta.empty:
    try:
        # Reproyectamos a MAGNA-SIRGAS (EPSG:3116) para medir kilómetros reales
        gdf_zona_metric = gdf_zona.to_crs(epsg=3116)
        gdf_meta_metric = gdf_meta.to_crs(epsg=3116)
        
        # 🧹 BARRIDO FORENSE 2: Extinguir cualquier índice residual antes del sjoin
        cols_a_borrar = [c for c in gdf_meta_metric.columns if c in ['index_right', 'index_left']]
        if cols_a_borrar:
            gdf_meta_metric = gdf_meta_metric.drop(columns=cols_a_borrar)
        
        # Expandimos el polígono (convertimos km a metros)
        zona_buffered = gdf_zona_metric.buffer(buffer_km * 1000)
        
        # Encontramos cuáles estaciones caen dentro de la zona expandida
        gdf_buffer = gpd.GeoDataFrame(geometry=zona_buffered, crs="EPSG:3116")
        estaciones_dentro = gpd.sjoin(gdf_meta_metric, gdf_buffer, how="inner", predicate="intersects")
        
        # Actualizamos la lista oficial de estaciones para el SQL
        ids_sel = estaciones_dentro[col_id].unique().tolist()
        st.sidebar.success(f"📡 Estaciones en el radar: {len(ids_sel)}")
    except Exception as e:
        st.sidebar.error(f"Error en buffer espacial: {e}")

# Escudo Anti-Colapso: Si el buffer en 0km sigue vacío, ponemos un ID falso para no quebrar el SQL
if not ids_sel: ids_sel = ['0']

# --- 7. LÓGICA ESPACIAL SINCRONIZADA ---
tab_mapa, tab_datos = st.tabs(["🗺️ Visualización Espacial", "💾 Descargas GIS"])

with tab_mapa:
    try:
        df_agg = pd.DataFrame() # 🛡️ ESCUDO: Inicializamos vacío para evitar errores si no hay estaciones
        engine = db_manager.get_engine()
        
        ids_clean = [str(i).replace("'", "") for i in ids_sel] 
        ids_sql = "('" + "','".join(ids_clean) + "')"
        
        q_raw = text(f"SELECT p.id_estacion, p.fecha, p.valor FROM precipitacion p WHERE p.id_estacion IN {ids_sql}")
        df_raw = pd.read_sql(q_raw, engine)
        
        if not df_raw.empty:
            df_proc = df_raw.copy()
            df_proc['fecha'] = pd.to_datetime(df_proc['fecha'])
            df_proc = df_proc.groupby(['id_estacion', 'fecha'])['valor'].mean().reset_index()
            
            if do_interp_temp and complete_series:
                with st.spinner("Interpolando huecos temporales..."):
                    df_proc = complete_series(df_proc) 
            
            df_proc['year'] = df_proc['fecha'].dt.year
            
            if not do_interp_temp:
                estaciones_antes = df_proc['id_estacion'].nunique()
                year_counts = df_proc.groupby(['id_estacion', 'year'])['valor'].count().reset_index(name='count')
                valid_years = year_counts[year_counts['count'] >= 10]
                df_proc = pd.merge(df_proc, valid_years[['id_estacion', 'year']], on=['id_estacion', 'year'])
                estaciones_despues = df_proc['id_estacion'].nunique()
                
                if estaciones_despues < estaciones_antes:
                    st.warning(f"⚠️ Atención: {estaciones_antes - estaciones_despues} estaciones fueron descartadas porque tienen menos de 10 meses de datos válidos. **Activa 'Interpolación Temporal'** en el menú izquierdo para intentar rescatarlas.")

            df_annual_sums = df_proc.groupby(['id_estacion', 'year'])['valor'].sum().reset_index(name='total_anual')
            df_annual_sums = df_annual_sums.rename(columns={'id_estacion': 'station_id'})

            # --- FILTROS DE ANÁLISIS ---
            if tipo_analisis == "Año Específico":
                df_agg = df_annual_sums[df_annual_sums['year'] == params_analisis['year']].copy()
                df_agg = df_agg.rename(columns={'total_anual': 'valor'})
            elif tipo_analisis == "Promedio Multianual":
                mask = (df_annual_sums['year'] >= params_analisis['start']) & (df_annual_sums['year'] <= params_analisis['end'])
                df_agg = df_annual_sums[mask].groupby('station_id')['total_anual'].mean().reset_index(name='valor')
            elif tipo_analisis == "Pronóstico Futuro":
                df_agg = calcular_pronostico(df_annual_sums, params_analisis['target'])
            else:
                df_agg = df_annual_sums.groupby('station_id')['total_anual'].max().reset_index(name='valor')
                
            # --- GENERACIÓN DE ISOYETAS ---
            if not df_agg.empty:
                df_agg = df_agg.rename(columns={'station_id': col_id})
                
                # CORRECCIÓN DE TYPO: cols_finales ahora está correctamente declarada
                cols_finales = list(set([col_id, col_nom, 'lat_calc', 'lon_calc'] + ([col_muni] if col_muni else []) + ([col_alt] if col_alt else []) + ([col_cuenca] if col_cuenca else [])))
                df_final = pd.merge(df_agg, gdf_meta[cols_finales], on=col_id).groupby(['lat_calc', 'lon_calc']).first().reset_index()

                if ignore_zeros: df_final = df_final[df_final['valor'] > 1] 
                if ignore_nulls: df_final = df_final.dropna(subset=['valor'])
                
                if len(df_final) >= 3:
                    with st.spinner(f"Interpolando {len(df_final)} estaciones válidas..."):
                        
                        margin_lon = (df_final['lon_calc'].max() - df_final['lon_calc'].min()) * 0.15 or 0.1
                        margin_lat = (df_final['lat_calc'].max() - df_final['lat_calc'].min()) * 0.15 or 0.1
                        q_minx, q_maxx = df_final['lon_calc'].min() - margin_lon, df_final['lon_calc'].max() + margin_lon
                        q_miny, q_maxy = df_final['lat_calc'].min() - margin_lat, df_final['lat_calc'].max() + margin_lat
                        
                        gx_raw, gy_raw = np.mgrid[q_minx:q_maxx:complex(0, grid_res), q_miny:q_maxy:complex(0, grid_res)]
                        gdf_final = gpd.GeoDataFrame(df_final, geometry=gpd.points_from_xy(df_final.lon_calc, df_final.lat_calc), crs="EPSG:4326")
                        
                        # 🚀 FIX V3.0 DEFINITIVO: 1. Construir Pseudo-DEM a partir de estaciones históricas
                        try:
                            if col_alt and col_alt in df_final.columns:
                                known_alt = df_final[df_final[col_alt] > 0]
                                if len(known_alt) >= 3:
                                    from scipy.interpolate import griddata
                                    pts = known_alt[['lon_calc', 'lat_calc']].values
                                    vals = known_alt[col_alt].values
                                    # Armamos la superficie de montañas virtual
                                    dem_grid = griddata(pts, vals, (gx_raw, gy_raw), method='linear')
                                    # Tapamos los huecos de los bordes
                                    mask_n = np.isnan(dem_grid)
                                    if np.any(mask_n):
                                        dem_grid[mask_n] = griddata(pts, vals, (gx_raw[mask_n], gy_raw[mask_n]), method='nearest')
                                else:
                                    dem_grid = None
                            else:
                                dem_grid = None
                        except:
                            dem_grid = None

                        # 🚀 FIX V3.0 DEFINITIVO: 1. Traductores a prueba de balas
                        m_cod = 'ked' if 'Deriva' in metodo_seleccionado else ('kriging' if 'Kriging' in metodo_seleccionado else 'spline')
                        
                        dic_var = {"esférico": "spherical", "exponencial": "exponential", "gaussiano": "gaussian", "lineal": "linear"}
                        # Extraemos el valor del sidebar con seguridad
                        var_str = modelo_var_seleccionado.lower() if 'modelo_var_seleccionado' in locals() else "esférico"
                        v_cod = dic_var.get(var_str, "spherical")

                        # 🚀 FIX V3.0 DEFINITIVO: 2. Construir Pseudo-DEM (Relieve Virtual)
                        try:
                            if col_alt and col_alt in df_final.columns:
                                known_alt = df_final[df_final[col_alt] > 0]
                                if len(known_alt) >= 3:
                                    from scipy.interpolate import griddata
                                    pts = known_alt[['lon_calc', 'lat_calc']].values
                                    vals_alt = known_alt[col_alt].values
                                    dem_grid = griddata(pts, vals_alt, (gx_raw, gy_raw), method='linear')
                                    # Tapamos huecos
                                    mask_n = np.isnan(dem_grid)
                                    if np.any(mask_n):
                                        dem_grid[mask_n] = griddata(pts, vals_alt, (gx_raw[mask_n], gy_raw[mask_n]), method='nearest')
                                else:
                                    dem_grid = None
                            else:
                                dem_grid = None
                        except:
                            dem_grid = None

                        # --- LLAMADA AL MOTOR MAESTRO ---
                        try:
                            # Inyectamos los códigos matemáticos traducidos (m_cod y v_cod)
                            grid_z, grid_z_var = interpolador_maestro(df_puntos=gdf_final, col_val='valor', grid_x=gx_raw, grid_y=gy_raw, metodo=m_cod, modelo_variograma=v_cod, dem_grid=dem_grid)
                        except Exception as e:
                            st.error(f"Fallo profundo en el motor matemático: {e}")
                            grid_z = np.zeros_like(gx_raw)
                            grid_z_var = None

                        # --- SWITCH BLINDADO: ISOYETAS VS MAPA DE INCERTIDUMBRE ---
                        if ver_error and grid_z_var is not None and np.any(grid_z_var):
                            matriz_pintar = grid_z_var.T
                            titulo_color = "Error Prom."
                            escala_color = "Reds"
                            tit = f"Mapa de Incertidumbre (Varianza) | {metodo_seleccionado} | {nombre_zona}"
                            z_min_map, z_max_map = np.min(grid_z_var), np.max(grid_z_var)
                        else:
                            if ver_error:
                                st.warning("⚠️ El modelo matemático tuvo que usar algoritmos de respaldo por falta de densidad de puntos en la zona. No hay matriz de varianza disponible.")
                            matriz_pintar = grid_z.T
                            titulo_color = "mm/año"
                            escala_color = paleta_colores
                            tit = f"Isoyetas ({metodo_seleccionado}): {tipo_analisis} | {nombre_zona}"
                            z_min_map, z_max_map = df_final['valor'].min(), df_final['valor'].max()
                            if z_max_map == z_min_map: z_max_map += 0.1

                        fig = go.Figure()
                        
                        # --- RELLENADO INTELIGENTE DE ALTITUD PARA RED PIRAGUA ---
                        c_alt_corregida = []
                        for _, row in df_final.iterrows():
                            alt_actual = row[col_alt] if col_alt and pd.notna(row[col_alt]) else 0
                            
                            if (alt_actual == 0) and dem_grid is not None:
                                try:
                                    alt_interp = griddata((gx_raw.flatten(), gy_raw.flatten()), dem_grid.flatten(), (row['lon_calc'], row['lat_calc']), method='nearest')
                                    val = float(alt_interp[0]) if isinstance(alt_interp, (np.ndarray, list)) else float(alt_interp)
                                    c_alt_corregida.append(round(val, 1))
                                except:
                                    c_alt_corregida.append(alt_actual)
                            else:
                                c_alt_corregida.append(alt_actual)
                                
                        c_alt = np.array(c_alt_corregida)
                        
                        # Tooltips enriquecidos
                        df_final['hover_val'] = df_final['valor'].apply(lambda x: f"{x:,.0f}")
                        c_muni = df_final[col_muni].fillna('-') if col_muni else ["-"]*len(df_final)
                        c_cuenca = df_final[col_cuenca].fillna('-') if col_cuenca else ["-"]*len(df_final)
                        custom_data = np.stack((c_muni, c_alt, c_cuenca, df_final['hover_val']), axis=-1)

                        # --- DIBUJADO DE LA SUPERFICIE ---
                        fig.add_trace(go.Contour(
                            z=matriz_pintar, x=np.linspace(q_minx, q_maxx, grid_res), y=np.linspace(q_miny, q_maxy, grid_res),
                            colorscale=escala_color, zmin=z_min_map, zmax=z_max_map, colorbar=dict(title=titulo_color),
                            contours=dict(coloring='heatmap', showlabels=True, labelfont=dict(size=10, color='white')),
                            opacity=0.8, connectgaps=True, line_smoothing=smooth_val
                        ))
                        
                        # Inyección de las capas espaciales
                        add_context_layers_robust(fig, gdf_zona, ver_cuencas, ver_municipios)
                        
                        # --- PUNTOS DE LAS ESTACIONES ---
                        fig.add_trace(go.Scatter(
                            x=df_final['lon_calc'], y=df_final['lat_calc'], mode='markers',
                            marker=dict(size=6, color='black', line=dict(width=1, color='white')),
                            text=df_final[col_nom], 
                            hovertemplate="<b>%{text}</b><br>Valor: %{customdata[3]} mm<br>🏙️: %{customdata[0]}<br>⛰️: %{customdata[1]} m<extra></extra>", 
                            customdata=custom_data, 
                            name="Estaciones"
                        ))
                        
                        fig.update_layout(title=tit, height=650, margin=dict(l=0,r=0,t=40,b=0), xaxis=dict(visible=False, scaleanchor="y", scaleratio=1), yaxis=dict(visible=False), plot_bgcolor='white', dragmode='pan')
                        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                        
                        # 🚀 FIX: Capturar el estado del sidebar y calcular el área
                        txt_var = f" (Variograma: {modelo_var_seleccionado})" if "Kriging" in metodo_seleccionado else ""
                        
                        if tipo_analisis == "Año Específico": txt_tiempo = f"Año {params_analisis['year']}"
                        elif tipo_analisis in ["Promedio Multianual", "Variabilidad Temporal"]: txt_tiempo = f"Periodo {params_analisis['start']} - {params_analisis['end']}"
                        else: txt_tiempo = f"Proyección {params_analisis.get('target', '')}"
                        
                        # Cálculo matemático del área en km2 usando Magna-Sirgas
                        area_km2 = 0
                        if gdf_zona is not None and not gdf_zona.empty:
                            try:
                                # EPSG:3116 permite medir en metros reales en Colombia
                                area_km2 = gdf_zona.to_crs(epsg=3116).area.sum() / 1_000_000
                            except:
                                pass # Evita errores si la geometría viene rota
                        
                        # Construcción del texto consolidado
                        config_str = f"> *Método:* **{metodo_seleccionado}** {txt_var} | *Temporalidad:* **{txt_tiempo}** | *Radio:* **{buffer_km} km** | *Área de Estudio:* **{area_km2:,.1f} km²**"
                        
                        # Inyección de los datos a la interfaz
                        st.info(generar_analisis_texto_corregido(df_final, tipo_analisis, config_str))
                else:
                    st.warning("⚠️ Quedaron menos de 3 estaciones válidas después de aplicar los filtros de calidad temporal para este año.")
            
            else: 
                st.warning(f"⚠️ Las estaciones en esta zona no tienen registros consolidados para el modo seleccionado ({tipo_analisis}). Intenta con un año anterior o activa la 'Interpolación Temporal'.")
            # --------------------------------

        else:
            st.warning("No hay registros en la base de datos para esta zona y periodo.")
            
        with st.expander("🔍 Ver Datos Crudos", expanded=False):
            # 🚀 Escudo Anti-Errores
            if 'df_final' in locals() and not df_final.empty: 
                st.dataframe(df_final)

    except Exception as e:
        st.error(f"Error procesando datos: {e}")
        
# --- 8. DESCARGAS GIS ---
with tab_datos:
    if 'df_final' in locals() and not df_final.empty:
        st.subheader("💾 Descargas GIS")
        cols_show = [c for c in [col_id, col_nom, col_cuenca, 'valor'] if c in df_final.columns]
        st.dataframe(df_final[cols_show].head(50) if cols_show else df_final.head(50), use_container_width=True)
        
        c1, c2, c3 = st.columns(3)
        gdf_out = gpd.GeoDataFrame(df_final, geometry=gpd.points_from_xy(df_final.lon_calc, df_final.lat_calc), crs="EPSG:4326")
        c1.download_button("🌍 GeoJSON (Puntos)", gdf_out.to_json().encode('utf-8'), f"isoyetas_{tipo_analisis}.geojson", "application/json")
        
        if 'grid_z' in locals():
            asc = generar_raster_ascii(grid_z, q_minx, q_miny, (q_maxx-q_minx)/grid_res, grid_res, grid_res)
            c2.download_button("⬛ Raster (.asc)", asc, f"raster_{tipo_analisis}.asc", "text/plain")
        
        c3.download_button("📊 CSV (Excel)", df_final.to_csv(index=False).encode('utf-8'), f"datos_{tipo_analisis}.csv", "text/csv")
