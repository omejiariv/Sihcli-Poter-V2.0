# pages/Clima_e_Hidrologia.py

import os
for var in ['PROJ_LIB', 'PROJ_DATA', 'PROJ_DEBUG']:
    if var in os.environ: del os.environ[var]
try:
    import pyproj
    pyproj.datadir.set_data_dir(pyproj.datadir.get_data_dir())
except: pass

import sys
import warnings
import io
import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sqlalchemy import text
from rasterio.io import MemoryFile

# 1. CONFIGURACIÓN DE PÁGINA (PRIMERA LÍNEA SIEMPRE)
st.set_page_config(page_title="SIHCLI-POTER", page_icon="🌦️", layout="wide")
warnings.filterwarnings("ignore")

# 2. PARCHE UNIVERSAL (GDAL/PROJ)
if os.name == 'nt':
    try:
        import pyproj
        os.environ['PROJ_LIB'] = pyproj.datadir.get_data_dir()
    except: pass

# 3. IMPORTACIÓN ROBUSTA DE MÓDULOS (PATH FIX)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules import selectors, admin_utils, reporter, visualizer as viz
from modules.config import Config
from modules.db_manager import get_engine
from modules.data_processor import complete_series, load_and_process_all_data
from modules.dem_extractor import completar_altitudes_con_dem

# 4. BLINDAJE DE MÓDULOS (Lazy Loading)
# Solo verificamos disponibilidad, NO importamos las bestias matemáticas aún.
try:
    import rasterio # Prueba de fuego
    PHYSICS_AVAILABLE = True
except ImportError as e:
    PHYSICS_AVAILABLE = False
    st.toast(f"⚠️ Módulos espaciales limitados: {e}", icon="⚠️")

# 5. MENÚ DE NAVEGACIÓN
selectors.renderizar_menu_navegacion("Clima e Hidrología")

# --- INICIALIZACIÓN ESTRUCTURAL DE ESCALAS ---
nivel_norm = str(st.session_state.get('aleph_escala', '')).upper().strip()
es_nacional = "NACION" in nivel_norm
es_departamento = "DEPARTAMENTO" in nivel_norm or "DEPARTAMENTAL" in nivel_norm
es_municipio = "MUNICIPAL" in nivel_norm or "MUNICIPIO" in nivel_norm
es_region = "REGION" in nivel_norm or "SUBREGION" in nivel_norm
es_car = "CAR" in nivel_norm or "AUTORIDAD" in nivel_norm
es_cuenca = "CUENCA" in nivel_norm or "NSS" in nivel_norm or "SZH" in nivel_norm
# ---------------------------------------------

# 6. SINCRONIZACIÓN CLIMÁTICA (NOAA/IRI)
if 'enso_fase' not in st.session_state:
    try:
        from modules.climate_api import get_iri_enso_forecast
        df_enso, _ = get_iri_enso_forecast()
        if df_enso is not None and not df_enso.empty:
            f = df_enso.iloc[0]
            # Usamos update para mantener el código limpio
            st.session_state.update({
                'enso_fase': "Niña 🌧️" if f.get('La Niña', 0) > 50 else ("Niño ☀️" if f.get('El Niño', 0) > 50 else "Neutro ⚖️"),
                'aleph_iri_nino': int(f.get('El Niño', 0)),
                'aleph_iri_neutro': int(f.get('Neutral', 0)),
                'aleph_iri_nina': int(f.get('La Niña', 0)),
                'aleph_iri_trimestre': str(f.get('Trimestre', 'N/A'))
            })
            st.toast(f"📡 Clima Global Sincronizado: {st.session_state['enso_fase']}", icon="✅")
    except Exception:
        st.session_state.update({'enso_fase': "Neutro ⚖️", 'aleph_iri_nino': 0, 'aleph_iri_neutro': 100, 'aleph_iri_nina': 0})
        st.toast("⚠️ Usando clima Neutro por fallo de conexión.", icon="🔌")
        
# 6. CACHÉ DE RASTERS (OPTIMIZADO)
@st.cache_resource(show_spinner=False)
def cargar_raster_db(filename):
    try:
        client = admin_utils.init_supabase()
        return io.BytesIO(client.storage.from_("rasters").download(filename))
    except: return None

@st.cache_resource(show_spinner="📡 Consultando Sistema...")
def load_all_data_cached():
    return load_and_process_all_data()

# 🪂 FUNCIÓN CACHEADA GLOBALMENTE (INMUNE AL ENVENENAMIENTO)
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_territorio_maestro():
    import geopandas as gpd
    import requests, io
    url = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson"
    try:
        res = requests.get(url, timeout=60, verify=False) 
        if res.status_code == 200:
            gdf = gpd.read_file(io.BytesIO(res.content))
            gdf.columns = [c.lower().strip() for c in gdf.columns]
            return gdf
    except Exception as e: 
        print(f"Fallo de red detectado: {e}")
        
    # 🚀 ANTI-ENVENENAMIENTO: Si falló, limpiamos el caché para que intente de nuevo la próxima vez
    st.cache_data.clear()
    return gpd.GeoDataFrame()

# ==========================================
# APLICACIÓN PRINCIPAL
# ==========================================
def main():
    import os
    import pandas as pd
    import geopandas as gpd
    import streamlit as st
    import unicodedata
    import re

    # --- A. LECTURA MAESTRA DEL ALEPH ---
    nombre_zona = st.session_state.get('aleph_lugar', 'COLOMBIA')
    nivel_jerarquico = st.session_state.get('aleph_escala', 'NACIONAL')

    if not nombre_zona or nombre_zona in ["-- Seleccione --", "Sin Selección", "NINGUNO", ""]:
        st.info("👈 Seleccione un Territorio (Cuenca, Municipio o Región) en el menú lateral para comenzar.")
        st.stop()

    buffer_km = st.sidebar.slider("🎯 Radio de Búsqueda (Buffer en km):", 0.0, 50.0, 15.0, 1.0)
    st.session_state['buffer_global_km'] = buffer_km
    st.session_state['nivel_activo_global'] = nivel_jerarquico
    
    # --- B. CARGA DE DATOS BASE ---
    try:
        (gdf_stations, gdf_municipios, df_all_rain, df_enso, gdf_subcuencas, gdf_predios) = load_all_data_cached()
    except Exception as e:
        st.error(f"Error cargando datos base: {e}")
        st.stop()

    # --- C. CEREBRO ESTRUCTURAL (EL ALEPH) ---
    gdf_zona = None
    
    # 1. Recuperar de memoria (si el menú ya lo validó)
    if 'aleph_poligono' in st.session_state and st.session_state['aleph_poligono'] is not None:
        poligono_memoria = st.session_state['aleph_poligono']
        if hasattr(poligono_memoria, 'empty') and not poligono_memoria.empty:
            gdf_zona = poligono_memoria
            
    # 2. Si no está en memoria, resolver Cuenca o Territorio Administrativo sin sobrescribir hallazgos
    if gdf_zona is None or (hasattr(gdf_zona, 'empty') and gdf_zona.empty):
        import re, unicodedata
        from modules.utils import cargar_capa_espacial_cache

        def _limp_cuenca(txt):
            if not isinstance(txt, str):
                return ""
            s = unicodedata.normalize('NFKD', txt.upper().strip()).encode('ascii', 'ignore').decode('utf-8')
            return re.sub(r'[^A-Z0-9]', '', s)

        nivel_up = str(nivel_jerarquico).upper().strip()
        es_cuenca_clima = any(k in nivel_up for k in ["CUENCA", "NSS", "SZH", "ZH", "AH", "HIDROG"])

        if es_cuenca_clima:
            gdf_c_base = gdf_subcuencas
            if gdf_c_base is None or getattr(gdf_c_base, "empty", True):
                try:
                    gdf_c_base = cargar_capa_espacial_cache("SELECT * FROM cuencas", get_engine(), geom_col="geometry")
                except Exception:
                    gdf_c_base = None

            if gdf_c_base is not None and not gdf_c_base.empty:
                m_cod = re.search(r'\(([^()]+)\)\s*$', str(nombre_zona).strip())
                cod_ideam = m_cod.group(1).strip() if m_cod else None
                nom_limpio = _limp_cuenca(re.sub(r'\s*-\s*\([^()]+\)\s*$', '', str(nombre_zona)))

                match_c = gpd.GeoDataFrame()
                if cod_ideam:
                    cols_cod = [c for c in gdf_c_base.columns if c.lower() in ['nss1', 'nss2', 'nss3', 'szh', 'zh', 'ah', 'codigo', 'cod_cuenca']]
                    for col_c in cols_cod:
                        m_sub = gdf_c_base[gdf_c_base[col_c].astype(str).str.strip() == cod_ideam]
                        if not m_sub.empty:
                            match_c = m_sub
                            break

                if match_c.empty and nom_limpio:
                    cols_nom = [c for c in gdf_c_base.columns if any(k in c.lower() for k in ['nom', 'nombre', 'cuenca', 'subc', 'lbl'])]
                    for col_n in cols_nom:
                        m_nom = gdf_c_base[gdf_c_base[col_n].astype(str).apply(_limp_cuenca) == nom_limpio]
                        if not m_nom.empty:
                            match_c = m_nom
                            break

                if not match_c.empty:
                    geom_u = match_c.geometry.make_valid().unary_union
                    gdf_zona = gpd.GeoDataFrame(geometry=[geom_u], crs=gdf_c_base.crs)
                    st.session_state['aleph_poligono'] = gdf_zona

        if gdf_zona is None or (hasattr(gdf_zona, 'empty') and gdf_zona.empty):
            with st.spinner("🌍 Extrayendo geometría desde Territorio Maestro..."):
                nombre_busqueda = st.session_state.get('aleph_lugar_oculto', nombre_zona)
                gdf_tm_res = cargar_capa_espacial_cache(nombre_busqueda, nivel_jerarquico)
                if gdf_tm_res is not None and not getattr(gdf_tm_res, "empty", True):
                    gdf_zona = gdf_tm_res
                    st.session_state['aleph_poligono'] = gdf_zona

    # 3. Muro de Seguridad Final
    if gdf_zona is None or (hasattr(gdf_zona, 'empty') and gdf_zona.empty) or (isinstance(gdf_zona, dict) and not gdf_zona):
        st.error("🚨 Error: No se pudo cargar el polígono del territorio. Asegúrate de tener conexión.")
        st.stop()

    # =========================================================================
    # --- D. CRUCE GEOGRÁFICO FINAL (CON BUFFER MÉTRICO Y LIMPIEZA) ---
    # =========================================================================
    ids_estaciones = []
        
    if gdf_stations is not None and not gdf_stations.empty:
        # Asignar sistema de coordenadas base (WGS84) ANTES de proyectar a metros
        if gdf_zona.crs is None:
            gdf_zona = gdf_zona.set_crs(epsg=4326)
        if gdf_stations.crs is None:
            gdf_stations = gdf_stations.set_crs(epsg=4326)
            
        # Proyección a metros (EPSG:3116 - MAGNA-SIRGAS Colombia)
        gdf_zona_proj = gdf_zona.to_crs(epsg=3116)
        gdf_stations_proj = gdf_stations.to_crs(epsg=3116)
        
        cols_drop = [c for c in gdf_stations_proj.columns if c in ['index_right', 'index_left']]
        if cols_drop: 
            gdf_stations_proj = gdf_stations_proj.drop(columns=cols_drop)
        
        if buffer_km > 0:
            # Reparar geometrías inválidas antes de inflar el buffer
            gdf_zona_proj['geometry'] = gdf_zona_proj.geometry.make_valid()
            gdf_zona_proj['geometry'] = gdf_zona_proj.geometry.buffer(buffer_km * 1000)
        
        # Cruce espacial estricto
        estaciones_dentro = gpd.sjoin(gdf_stations_proj, gdf_zona_proj, how="inner", predicate='intersects')
        
        # Usar .unique() para evitar que una estación cuente doble si toca múltiples sub-polígonos
        ids_estaciones = estaciones_dentro['id_estacion'].unique().tolist()

    if not ids_estaciones:
        st.warning(f"⚠️ No se encontraron estaciones meteorológicas a menos de {buffer_km} km del territorio: {nombre_zona}.")
        st.info("💡 Sugerencia: El polígono es pequeño o no hay infraestructura IDEAM en esta zona. Aumenta el 'Radio de Búsqueda' en el panel lateral.")
        # Quitamos el st.stop() aquí para permitir que la página siga cargando otros módulos (si los hay) 
        # o puedes dejarlo si Clima e Hidrología depende exclusivamente de las estaciones.
        st.stop() 

    # =========================================================================
    # --- E. DESCARGA DINÁMICA DE LLUVIAS ---
    # =========================================================================
    with st.spinner(f"☁️ Descargando historial de precipitaciones para {len(ids_estaciones)} estaciones..."):
        try:
            from sqlalchemy import text
            from modules.db_manager import get_engine

            ids_fmt = ",".join([f"'{str(x).strip()}'" for x in ids_estaciones])
            q_lluvia = text(f"SELECT id_estacion, fecha, valor FROM precipitacion WHERE id_estacion IN ({ids_fmt})")
            
            engine_lluvia = get_engine()
            with engine_lluvia.connect() as conn:
                df_all_rain = pd.read_sql(q_lluvia, conn)
            
            if not df_all_rain.empty:
                df_all_rain['id_estacion'] = df_all_rain['id_estacion'].astype(str).str.strip()
                df_all_rain = df_all_rain.rename(columns={'fecha': Config.DATE_COL, 'valor': Config.PRECIPITATION_COL})
                df_all_rain[Config.DATE_COL] = pd.to_datetime(df_all_rain[Config.DATE_COL])
                df_all_rain[Config.PRECIPITATION_COL] = pd.to_numeric(df_all_rain[Config.PRECIPITATION_COL], errors='coerce')
                df_all_rain = df_all_rain.dropna(subset=[Config.DATE_COL])
                df_all_rain[Config.YEAR_COL] = df_all_rain[Config.DATE_COL].dt.year
                df_all_rain[Config.MONTH_COL] = df_all_rain[Config.DATE_COL].dt.month
                
                df_long = pd.merge(
                    df_all_rain,
                    gdf_stations[["id_estacion", Config.STATION_NAME_COL]],
                    on="id_estacion",
                    how="inner"
                )
            else:
                df_long = pd.DataFrame()
                
        except Exception as e:
            st.error(f"Error descargando historial de lluvias: {e}")
            df_long = pd.DataFrame()

    if df_long.empty:
        st.warning(f"La zona '{nombre_zona}' no tiene registros históricos de precipitación válidos.")
        st.stop()

    # 🛡️ 2. FILTRO DE INTEGRIDAD FÍSICA (PURGA DE ANOMALÍAS EXTREMAS)
    if Config.PRECIPITATION_COL in df_long.columns:
        umbral_maximo = 8000  # Límite físico en mm (Ej. diluvios irreales > 30,000mm)
        picos_mask = df_long[Config.PRECIPITATION_COL] > umbral_maximo
        
        if picos_mask.any():
            num_picos = picos_mask.sum()
            st.warning(f"⚠️ Alerta de Calidad: Se neutralizaron {num_picos} registros físicamente imposibles (> {umbral_maximo}mm) en esta zona. Han sido pasados a nulos para no sesgar la interpolación.")
            df_long.loc[picos_mask, Config.PRECIPITATION_COL] = float('nan')
    
    # 3. 📍 Filtro de geometrías espaciales
    if gdf_stations is not None:
        gdf_stations['id_estacion'] = gdf_stations['id_estacion'].astype(str).str.strip()
        gdf_filtered = gdf_stations[gdf_stations['id_estacion'].isin(ids_estaciones)].copy()
    else:
        gdf_filtered = gpd.GeoDataFrame()

    # =========================================================================
    # --- JERARQUÍA DE NAVEGACIÓN ---
    # =========================================================================
    st.markdown("""
    <style>
    .block-container { padding-top: 3rem !important; }
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #2c3e50, #3498db); border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background: linear-gradient(135deg, #1a252f, #2980b9); transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)

    st.title(f"🌦️ Análisis Hidroclimático: {nombre_zona}")
    st.markdown("### 🎛️ Centro de Comando y Módulos de Análisis")
    
    col_nav1, col_nav2, col_nav3 = st.columns([1.5, 1.5, 1])
    
    with col_nav1:
        categoria_nav = st.selectbox(
            "📂 Categoría de Análisis:",
            ["📊 Analítica y Monitoreo Base", "🔬 Ciencia y Pronóstico Climático", "🌍 Gemelo Digital (Modelación Avanzada)"]
        )
        
    with col_nav2:
        if "Analítica" in categoria_nav:
            opciones = ["🗺️ Distribución", "🚨 Monitoreo", "📈 Gráficos", "📊 Estadísticas", "🧠 Peritaje y Consistencia", "📄 Reporte", "🏠 Inicio"]
        elif "Ciencia" in categoria_nav:
            opciones = ["🔮 Pronóstico Climático", "📉 Tendencias", "⚠️ Anomalías", "🔗 Correlación", "🌊 Extremos", "🧪 Sesgo", "🌀 Dinámica de Sistemas"]
        else:
            opciones = ["🌍 Mapas Avanzados (Motor Aleph)", "✨ Mapas Isoyetas HD", "🌿 Cobertura", "🌱 Zonas Vida", "🌡️ Clima Futuro"]
            
        selected_module_raw = st.selectbox("🎯 Módulo Específico:", opciones)
        
    with col_nav3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refrescar Memoria", help="Limpia el caché y recarga los datos desde cero", width="stretch"):
            st.cache_data.clear()
            st.cache_resource.clear()
            keys_to_delete = ['df_long', 'gdf_stations', 'gdf_subcuencas', 'uploaded_file_hash']
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    # --- D. FILTROS EN BARRA LATERAL (TIEMPO Y LIMPIEZA) ---
    with st.sidebar:
        with st.expander("⏳ Tiempo y Limpieza", expanded=False):
            
            # 🛡️ FIX: Blindaje del Slider de Tiempo
            if df_long is not None and not df_long.empty:
                min_y = int(df_long[Config.YEAR_COL].min())
                max_y = int(df_long[Config.YEAR_COL].max())
            else:
                min_y, max_y = 1980, 2026 # Valores de seguridad
                
            year_range = st.slider("📅 Años:", min_y, max_y, (min_y, max_y))
            
            c1, c2 = st.columns(2)
            ignore_zeros = c1.checkbox("🚫 Sin Ceros", value=False)
            ignore_nulls = c2.checkbox("🚫 Sin Nulos", value=False)
            apply_interp = st.checkbox("🔄 Interpolación", value=False)

        # 🛡️ INYECCIÓN QUIRÚRGICA: Filtro de Homogenización
        st.markdown("---")
        st.markdown("### ⏳ Filtro de Homogenización")
        min_years = st.slider(
            "Años mínimos de registro continuos", 
            min_value=0, max_value=50, value=0, step=1, 
            help="Filtra estaciones que no cumplan con este mínimo de años históricos. Útil para eliminar el 'escalón' de estaciones post-2010."
        )

    # --- E. PROCESAMIENTO ESTRATÉGICO ---
    # 1. Aplicar filtro temporal primero
    mask_time = (df_long[Config.YEAR_COL] >= year_range[0]) & (df_long[Config.YEAR_COL] <= year_range[1])
    df_monthly_filtered = df_long.loc[mask_time].copy()
    
    # 2. LIMPIEZA DE CALIDAD (Fundamental hacerlo antes de contar años)
    if ignore_zeros: 
        df_monthly_filtered = df_monthly_filtered[df_monthly_filtered[Config.PRECIPITATION_COL] > 0]
    if ignore_nulls: 
        df_monthly_filtered = df_monthly_filtered.dropna(subset=[Config.PRECIPITATION_COL])

    # 3. ⏳ FILTRO DE HOMOGENIZACIÓN (Ahora sí, contando solo la verdad)
    if min_years > 0 and not df_monthly_filtered.empty:
        # Contamos años únicos que sobrevivieron a la purga de ceros y nulos
        conteo_agnos = df_monthly_filtered.groupby(Config.STATION_NAME_COL)[Config.YEAR_COL].nunique()
        estaciones_validas = conteo_agnos[conteo_agnos >= min_years].index.tolist()
        
        # Recortamos la matriz
        df_monthly_filtered = df_monthly_filtered[df_monthly_filtered[Config.STATION_NAME_COL].isin(estaciones_validas)]
        st.sidebar.success(f"✅ {len(estaciones_validas)} estaciones cumplen con >{min_years} años reales.")

    # 4. Extraemos la lista final y purificada para los módulos de análisis
    if not df_monthly_filtered.empty:
        stations_for_analysis = df_monthly_filtered[Config.STATION_NAME_COL].unique().tolist()
    else:
        stations_for_analysis = []
        st.warning(f"Ninguna estación cumple con el requisito de tener {min_years} años de datos continuos.")
        st.stop()

    # 5. Interpolación (Solo a las estaciones sobrevivientes históricas)
    if apply_interp:
        with st.spinner("Interpolando series..."):
            df_monthly_filtered = complete_series(df_monthly_filtered)
    
    df_anual_melted = df_monthly_filtered.groupby([Config.STATION_NAME_COL, Config.YEAR_COL])[Config.PRECIPITATION_COL].sum(min_count=10).reset_index()

    # 4. Ajuste de seguridad para year_range
    if 'year_range' not in locals() or year_range is None:
        year_range = [2020, 2026]

    # =========================================================================
    # 🌟 CEREBRO TELEMÉTRICO ESTRUCTURAL (FIX RAÍZ)
    # =========================================================================
    
    # 🚀 0. DETECTOR DE CAMBIO DE TERRITORIO (El Descongelador)
    territorio_actual = str(nombre_zona).strip().upper()
    territorio_anterior = st.session_state.get('aleph_lugar_memoria', '')

    if territorio_actual != territorio_anterior:
        # ¡Cambio de rumbo detectado! Vaciamos la memoria vieja
        keys_to_reset = ['aleph_area_km2', 'aleph_pob_total', 'aleph_altitud_m', 'aleph_altitud_max', 'aleph_altitud_min']
        for k in keys_to_reset:
            if k in st.session_state:
                del st.session_state[k]
        
        # Guardamos el nuevo territorio para la próxima comparación
        st.session_state['aleph_lugar_memoria'] = territorio_actual

    # 1. Área
    area_actual_km2 = float(st.session_state.get('aleph_area_km2', 0.0))
    if area_actual_km2 <= 0 and gdf_zona is not None and not gdf_zona.empty:
        try:
            gdf_zona_calc = gdf_zona.copy()
            if gdf_zona_calc.crs is None: 
                gdf_zona_calc = gdf_zona_calc.set_crs("EPSG:4326")
            gdf_zona_calc['geometry'] = gdf_zona_calc.geometry.make_valid()
            area_actual_km2 = float(gdf_zona_calc.to_crs(epsg=3116).area.sum() / 1e6)
            st.session_state['aleph_area_km2'] = area_actual_km2
        except Exception:
            pass

    # 2. Población Estructural (Conectado al motor demográfico oficial)
    pob_actual = float(st.session_state.get('aleph_pob_total', 0.0))
    if pob_actual <= 0:
        try:
            # 🚀 CIRUGÍA ESTRUCTURAL: Importamos tu motor demográfico
            from modules.demografia_tools import calcular_poblacion_al_vuelo
            
            # Usamos las variables globales que ya tienes en la página 01
            datos_demo = calcular_poblacion_al_vuelo(nombre_zona, nivel_jerarquico, "Total")
            
            if datos_demo is not None and len(datos_demo.get('hist_pob', [])) > 0:
                # Tomamos la población proyectada más reciente (el último dato de la lista)
                pob_real_dane = float(datos_demo['hist_pob'][-1])
                st.session_state['aleph_pob_total'] = pob_real_dane
            elif area_actual_km2 > 0:
                # Solo si el DANE no tiene la cuenca/municipio, usamos la densidad matemática
                st.session_state['aleph_pob_total'] = max((area_actual_km2 * 35.0), 10000.0)
        except Exception as e:
            # Fallback silencioso en caso de error de red
            pass

    # 3. 🚀 NUEVO: Conexión robusta a Matrices Maestras (Inmune a tildes como Medellín/Medelln)
    try:
        from modules.db_manager import get_engine
        from sqlalchemy import text
        import pandas as pd
        import unicodedata, re

        def _norm_alt(txt):
            s = unicodedata.normalize('NFKD', str(txt).upper().strip()).encode('ascii', 'ignore').decode('utf-8')
            return re.sub(r'[^A-Z0-9]', '', s)

        zona_limpia = str(nombre_zona).replace("CAR: ", "").split(" - (")[0].strip()
        key_zona = _norm_alt(zona_limpia)
        cons_zona = re.sub(r'[AEIOU]', '', key_zona)
        eng_alt = get_engine()

        alt_med_ok, alt_min_ok, alt_max_ok = 0.0, 0.0, 0.0

        # A. Intentar primero Matriz Hidro-Geomorfológica (trae Mín, Media y Máx reales)
        try:
            with eng_alt.connect() as conn:
                df_gm = pd.read_sql(text('SELECT "Territorio", "H_Minima", "H_Media", "H_Maxima" FROM matriz_hidrogeomorfologica_maestra'), conn)
            if not df_gm.empty:
                s_gm = df_gm['Territorio'].apply(_norm_alt)
                m_gm = df_gm[s_gm == key_zona]
                if m_gm.empty:
                    m_gm = df_gm[s_gm.apply(lambda x: re.sub(r'[AEIOU]', '', x)) == cons_zona]
                if not m_gm.empty:
                    alt_med_ok = float(m_gm['H_Media'].iloc[0] or 0.0)
                    alt_min_ok = float(m_gm['H_Minima'].iloc[0] or alt_med_ok)
                    alt_max_ok = float(m_gm['H_Maxima'].iloc[0] or alt_med_ok)
        except Exception:
            pass

        # B. Si no estuvo, intentar Matriz Hidrológica Maestra
        if alt_med_ok <= 0:
            with eng_alt.connect() as conn:
                df_hm = pd.read_sql(text('SELECT "Territorio", "Altitud_m" FROM matriz_hidrologica_maestra'), conn)
            if not df_hm.empty:
                s_hm = df_hm['Territorio'].apply(_norm_alt)
                m_hm = df_hm[s_hm == key_zona]
                if m_hm.empty:
                    m_hm = df_hm[s_hm.apply(lambda x: re.sub(r'[AEIOU]', '', x)) == cons_zona]
                if not m_hm.empty:
                    alt_med_ok = float(m_hm['Altitud_m'].iloc[0] or 0.0)
                    alt_min_ok, alt_max_ok = alt_med_ok, alt_med_ok

        # C. Respaldo final: altitud real de las estaciones filtradas en la zona
        if alt_med_ok <= 0 and gdf_filtered is not None and not gdf_filtered.empty and 'altitud' in gdf_filtered.columns:
            alts_est = pd.to_numeric(gdf_filtered['altitud'], errors='coerce').dropna()
            alts_est = alts_est[alts_est > 0]
            if not alts_est.empty:
                alt_med_ok = float(alts_est.mean())
                alt_min_ok = float(alts_est.min())
                alt_max_ok = float(alts_est.max())

        if alt_med_ok > 0:
            st.session_state['aleph_altitud_m'] = alt_med_ok
            st.session_state['aleph_altitud_min'] = alt_min_ok
            st.session_state['aleph_altitud_max'] = alt_max_ok
        else:
            st.session_state['aleph_altitud_m'] = 0.0
    except Exception:
        pass

    # Calculamos y fijamos la población estructuralmente para todas las pestañas
    pob_actual = float(st.session_state.get('aleph_pob_total', 0.0))
    if pob_actual <= 0:
        str_zona = str(nombre_zona).upper()
        if "ANTIOQUIA" in str_zona:
            st.session_state['aleph_pob_total'] = 6901160.0
        elif "COLOMBIA" in str_zona:
            st.session_state['aleph_pob_total'] = 52828000.0
        elif area_actual_km2 > 0:
            st.session_state['aleph_pob_total'] = max((area_actual_km2 * 35.0), 10000.0)

    # =========================================================================
    # 🌟 INYECCIÓN DE CLIMA GLOBAL EN VIVO (BYPASS TABLAS ESTÁTICAS)
    # =========================================================================
    try:
        from modules.climate_api import get_live_oni_data, get_live_soi_data, get_live_iod_data, get_live_sst_data
        
        df_oni_vivo, _ = get_live_oni_data()
        df_soi_vivo, _ = get_live_soi_data()
        df_iod_vivo, _ = get_live_iod_data()
        df_sst_vivo, _ = get_live_sst_data()
        
        if df_oni_vivo is not None and not df_oni_vivo.empty:
            df_enso_vivo = df_oni_vivo.copy()
            
            if df_soi_vivo is not None and not df_soi_vivo.empty:
                df_enso_vivo = pd.merge(df_enso_vivo, df_soi_vivo, on='fecha', how='left')
            if df_iod_vivo is not None and not df_iod_vivo.empty:
                df_enso_vivo = pd.merge(df_enso_vivo, df_iod_vivo, on='fecha', how='left')
            if df_sst_vivo is not None and not df_sst_vivo.empty:
                df_enso_vivo = pd.merge(df_enso_vivo, df_sst_vivo, on='fecha', how='left')
                
            df_enso = df_enso_vivo
    except Exception as e:
        print(f"Error en bypass de clima: {e}")

    # Argumentos Globales para Visualizer
    display_args = {
        "df_long": df_monthly_filtered, "df_complete": df_monthly_filtered,
        "gdf_stations": gdf_stations, "gdf_filtered": gdf_filtered,
        "gdf_municipios": gdf_municipios, "gdf_subcuencas": gdf_subcuencas,
        "gdf_predios": gdf_predios, "df_enso": df_enso,
        "stations_for_analysis": stations_for_analysis, "df_anual_melted": df_anual_melted,
        "df_monthly_filtered": df_monthly_filtered, "analysis_mode": "Anual",
        "selected_regions": [], "selected_municipios": [],
        "selected_months": list(range(1, 13)), "year_range": year_range,
        "start_date": pd.to_datetime(f"{year_range[0]}-01-01"), 
        "end_date": pd.to_datetime(f"{year_range[1]}-12-31"),
        "gdf_coberturas": gdf_predios, "interpolacion": "Si" if apply_interp else "No",
        "user_loc": None, "gdf_zona": gdf_zona 
    }

    selected_module = "🌍 Mapas Avanzados" if "Mapas Avanzados" in selected_module_raw else selected_module_raw

    # =========================================================================
    # --- F. ENRUTADOR DE MÓDULOS ---
    # =========================================================================

    # 👑 TRATAMIENTO VIP PARA EL MOTOR ALEPH (Si fue seleccionado)
    if selected_module == "🌍 Mapas Avanzados":
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); padding: 25px; border-radius: 12px; color: white; margin-bottom: 25px; box-shadow: 0 10px 20px rgba(0,0,0,0.15);">
            <h2 style="color: white; margin-top: 0; display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.2em;">🌍</span> Motor Aleph: Modelación Hidrológica Distribuida
            </h2>
            <p style="font-size: 1.05em; opacity: 0.95; line-height: 1.5; margin-bottom: 0;">
                El nodo central del Gemelo Digital. Aquí la meteorología se fusiona con la topografía (Modelos de Elevación Digital) y las coberturas vegetales satelitales para calcular recarga, infiltración y caudales en cada pixel del territorio.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Módulos Estándar (Usando visualizer.py)
    if selected_module == "🏠 Inicio": viz.display_welcome_tab()
    elif selected_module == "🚨 Monitoreo": viz.display_realtime_dashboard(df_monthly_filtered, gdf_stations, gdf_filtered)
    elif selected_module == "🗺️ Distribución": 
        viz.display_spatial_distribution_tab(**display_args)
        
        # =====================================================================
        # --- CAJA DESPLEGABLE: GUÍA DE CODIFICACIÓN HIDROLÓGICA (IDEAM) ---
        # =====================================================================
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📖 Guía de Navegación: ¿Cómo leer los códigos hidrológicos (IDEAM)?", expanded=False):
            st.markdown("""
            ### El Sistema de las "Muñecas Rusas" (Metodología Pfafstetter)
            Para organizar el agua en Colombia, el IDEAM utiliza un sistema jerárquico. Imagina que el agua de nuestro territorio se organiza como un árbol, desde el tronco más grueso hasta la hoja más pequeña. Cada nivel añade más dígitos al código:
            
            * **🌊 AH (Área Hidrográfica - 1 dígito):** *El Gran Tronco.*
            * **Ríos Principales:**
                * **💧 ZH (Zona Hidrográfica - 2 dígitos):** *Las Ramas Principales.*
                * **🌿 SZH (Subzona Hidrográfica - 4 dígitos):** *Las Ramas Secundarias.*
            * **Tributarios y Microcuencas (Niveles Subsiguientes - NSS):**
                * **🍃 NSS1 (Nivel 4):** Afluentes directos de la SZH.
                * **🌱 NSS2 (Nivel 5):** Microcuencas locales.
                * **💧 NSS3 (Nivel 6):** Pequeños drenajes y nacimientos.
            
            ---
            ### 🗺️ Diccionario Rápido: Códigos Principales en Antioquia
            Para facilitar tu búsqueda en la plataforma, aquí tienes la relación exacta de los códigos mayores (Áreas y Zonas Hidrográficas) que rigen nuestro departamento:
            
            | 🌊 Área Hidrográfica (AH) | Código AH | 💧 Zona Hidrográfica (ZH) | Código ZH |
            | :--- | :---: | :--- | :---: |
            | **Magdalena Cauca** | `2` | Medio Magdalena | `23` |
            | **Magdalena Cauca** | `2` | Cauca | `26` |
            | **Magdalena Cauca** | `2` | Nechí | `27` |
            | **Caribe** | `1` | Atrato - Darién | `11` |
            | **Caribe** | `1` | Caribe - Litoral | `12` |
            | **Caribe** | `1` | Sinú | `13` |
            
            > **💡 Tip de Navegación:** Si buscas el Río Porce (Código `2601`), fíjate que empieza por `26`. Esto te indica inmediatamente que pertenece a la Zona Hidrográfica del **Cauca** y, por consiguiente, al Área Hidrográfica **Magdalena Cauca** (`2`).
            """)
            
            # --- SECCIÓN DE DESCARGA DEL DOCUMENTO OFICIAL ---
            st.markdown("---")
            st.markdown("#### 📚 Documento Oficial de Referencia")
            st.info("Consulta el manual completo de codificación y zonificación hidrológica para comprender los delineamientos técnicos a fondo.")
            
            # Botón de descarga en Streamlit
            try:
                # Asegúrate de que la ruta coincida con donde guardes el PDF en tu servidor/proyecto
                ruta_pdf = "Codificacion Hidrologica Antioquia IDEAM.pdf" 
                with open(ruta_pdf, "rb") as pdf_file:
                    PDFbyte = pdf_file.read()
                
                st.download_button(
                    label="📥 Descargar Manual de Codificación IDEAM (PDF)",
                    data=PDFbyte,
                    file_name="Codificacion_Hidrologica_Antioquia_IDEAM.pdf",
                    mime='application/pdf',
                    width="stretch"
                )
            except FileNotFoundError:
                st.error("⚠️ El archivo PDF de referencia no se encontró en el servidor. (Asegúrate de subir 'Codificacion Hidrologica Antioquia IDEAM.pdf' a la carpeta principal de tu aplicación).")
            
    elif selected_module == "📈 Gráficos": viz.display_graphs_tab(**display_args)
    elif selected_module == "📊 Estadísticas": 
        viz.display_stats_tab(**display_args)
        st.markdown("---")
        viz.display_station_table_tab(**display_args)

    # ==============================================================================
    # 🧠 NUEVO MÓDULO: PERITAJE Y CONSISTENCIA HIDROMETEOROLÓGICA
    # ==============================================================================
    elif selected_module == "🧠 Peritaje y Consistencia":
        st.subheader("🧠 Analítica Avanzada: Peritaje de Consistencia Hidrometeorológica")
        st.markdown("Evaluación forense automática de la calidad de las series de tiempo y su respuesta ante macro-eventos globales (ENOS).")
        
        # Ruta al Modelo de Elevación Digital ráster para Antioquia
        RUTA_DEM = os.path.join("data", "dem_antioquia.tif")
        
        # ----------------------------------------------------------------------
        # 🏢 1. CAJA MENSAJE PERMANENTE: BALANCE MACROREGIONAL (AHORA EXPANDIBLE)
        # ----------------------------------------------------------------------
        if df_monthly_filtered is not None and not df_monthly_filtered.empty and stations_for_analysis:
            with st.expander("🌍 Diagnóstico Macroregional de la Selección", expanded=True):
                df_macro = df_monthly_filtered[df_monthly_filtered[Config.STATION_NAME_COL].isin(stations_for_analysis)].copy()
                
                if not df_macro.empty:
                    df_macro_anual = df_macro.groupby([Config.STATION_NAME_COL, Config.YEAR_COL])[Config.PRECIPITATION_COL].agg(['sum', 'count']).reset_index()
                    df_macro_anual.columns = ['Estación', 'Año', 'Precipitación', 'Meses_Validos']
                    
                    # Filtro de integridad regional robusto (>700 mm)
                    df_macro_integro = df_macro_anual[(df_macro_anual['Meses_Validos'] >= 10) & (df_macro_anual['Precipitación'] >= 700.0)]
                    
                    if not df_macro_integro.empty:
                        idx_macro_max = df_macro_integro['Precipitación'].idxmax()
                        idx_macro_min = df_macro_integro['Precipitación'].idxmin()
                        
                        est_max_reg = df_macro_integro.loc[idx_macro_max, 'Estación']
                        ano_max_reg = int(df_macro_integro.loc[idx_macro_max, 'Año'])
                        val_max_reg = df_macro_integro.loc[idx_macro_max, 'Precipitación']
                        
                        est_min_reg = df_macro_integro.loc[idx_macro_min, 'Estación']
                        ano_min_reg = int(df_macro_integro.loc[idx_macro_min, 'Año'])
                        val_min_reg = df_macro_integro.loc[idx_macro_min, 'Precipitación']
                        
                        df_medias = df_macro_integro.groupby('Estación')['Precipitación'].mean().reset_index()
                        est_mas_humeda = df_medias.loc[df_medias['Precipitación'].idxmax(), 'Estación']
                        media_mas_humeda = df_medias['Precipitación'].max()
                        
                        est_mas_seca = df_medias.loc[df_medias['Precipitación'].idxmin(), 'Estación']
                        media_mas_seca = df_medias['Precipitación'].min()
                        
                        c_macro1, c_macro2 = st.columns(2)
                        with c_macro1:
                            st.markdown(f"**🌧️ Núcleo de Alta Precipitación (Más Húmedo):**")
                            st.markdown(f"* **Estación Predominante:** `{est_mas_humeda}`")
                            st.markdown(f"* **Rendimiento Medio Anual:** `{media_mas_humeda:,.1f} mm/año`")
                            st.markdown(f"* **Récord Histórico Absoluto:** `{val_max_reg:,.1f} mm` en el año **{ano_max_reg}** (`{est_max_reg}`)")
                            
                        with c_macro2:
                            st.markdown(f"**🌵 Núcleo de Sombra de Lluvia (Más Seco):**")
                            st.markdown(f"* **Estación Predominante:** `{est_mas_seca}`")
                            st.markdown(f"* **Rendimiento Medio Anual:** `{media_mas_seca:,.1f} mm/año`")
                            st.markdown(f"* **Mínimo Histórico Absoluto:** `{val_min_reg:,.1f} mm` en el año **{ano_min_reg}** (`{est_min_reg}`)")
                    else:
                        st.warning("⚠️ No hay suficientes años con registros que superen el umbral de integridad de 700 mm en esta selección geográfica.")
                else:
                    st.info("No se encontraron registros de series temporales para las estaciones de este sector.")

        # ----------------------------------------------------------------------
        # 🔍 SELECTOR LOCAL Y PROCESAMIENTO DE LA ESTACIÓN
        # ----------------------------------------------------------------------
        if stations_for_analysis:
            est_sel = st.selectbox("🔍 Seleccione la Estación para Peritaje Forense:", stations_for_analysis)
            
            if est_sel and df_monthly_filtered is not None and not df_monthly_filtered.empty:
                
                nombre_estacion_puro = est_sel.split('[')[0].strip() if '[' in est_sel else est_sel
                codigo_puro = est_sel.split('[')[1].replace(']', '').strip() if '[' in est_sel else ""
                
                df_est = df_monthly_filtered[df_monthly_filtered[Config.STATION_NAME_COL] == est_sel].copy()
                if df_est.empty:
                    df_est = df_monthly_filtered[df_monthly_filtered[Config.STATION_NAME_COL] == nombre_estacion_puro].copy()
                if df_est.empty and codigo_puro:
                    df_est = df_monthly_filtered[df_monthly_filtered[Config.STATION_NAME_COL].astype(str).str.contains(codigo_puro)].copy()
                
                df_est = df_est.dropna(subset=[Config.PRECIPITATION_COL])
                
                df_anual = df_est.groupby(Config.YEAR_COL)[Config.PRECIPITATION_COL].agg(['sum', 'count']).reset_index()
                df_anual.columns = ['Año', 'Precipitación', 'Meses_Validos']
                df_integro = df_anual[(df_anual['Meses_Validos'] >= 10) & (df_anual['Precipitación'] >= 700.0)]
                
                # --- DISEÑO BI-PANEL: FICHA GEOGRÁFICA Y VALIDACIÓN MACROCLIMÁTICA ---
                col_panel1, col_panel2 = st.columns([1.5, 2])
                
                # 🏢 2. FICHA TÉCNICA GEOGRÁFICA (AHORA EXPANDIBLE)
                with col_panel1:
                    with st.expander("🛡️ Ficha Técnica Geográfica", expanded=True):
                        municipio_est = "No especificado"
                        altitud_est = "N/D"
                        
                        if gdf_stations is not None and not gdf_stations.empty:
                            meta_est = gdf_stations[gdf_stations[Config.STATION_NAME_COL].astype(str).str.contains(codigo_puro)] if codigo_puro else gdf_stations[gdf_stations[Config.STATION_NAME_COL] == est_sel]
                            if not meta_est.empty:
                                col_muni = [c for c in meta_est.columns if 'muni' in c.lower() or 'id_muni' in c.lower()]
                                col_alt = [c for c in meta_est.columns if 'alt' in c.lower() or 'ele' in c.lower() or 'msnm' in c.lower()]
                                
                                if col_muni: municipio_est = str(meta_est.iloc[0][col_muni[0]]).upper()
                                
                                if col_alt and pd.notna(meta_est.iloc[0][col_alt[0]]) and str(meta_est.iloc[0][col_alt[0]]).strip() != "":
                                    altitud_est = f"{int(meta_est.iloc[0][col_alt[0]]):,} msnm"
                                elif os.path.exists(RUTA_DEM):
                                    try:
                                        import rasterio
                                        punto_geom = meta_est.geometry.iloc[0]
                                        with rasterio.open(RUTA_DEM) as src:
                                            coord_par = [(punto_geom.x, punto_geom.y)]
                                            for val in src.sample(coord_par):
                                                alt_dem = val[0]
                                                if alt_dem > -9999:
                                                    altitud_est = f"{int(alt_dem):,} msnm (Vía DEM)"
                                    except:
                                        altitud_est = "Error muestreo DEM"
                        
                        st.markdown(f"**📍 Estación:** `{est_sel}`")
                        st.markdown(f"**🏢 Municipio:** `{municipio_est}`")
                        st.markdown(f"**⛰️ Altitud:** `{altitud_est}`")
                        st.divider()
                        
                        años_totales = df_anual.shape[0]
                        años_completos = df_integro.shape[0]
                        años_reconstruidos = df_anual[(df_anual['Precipitación'].notna()) & (df_anual['Precipitación'] % 1 != 0)].shape[0]
                        
                        st.metric(label="Años con Datos Activos", value=f"{años_totales} años")
                        st.metric(label="Años con Integridad (>10 meses)", value=f"{años_completos} años")
                        st.metric(label="Años Reparados por Gemelo Digital", value=f"{años_reconstruidos} años")
                
                # 🌍 3. VALIDACIÓN MACROCLIMÁTICA BASE CON EXTREMOS MENSUALES (AHORA EXPANDIBLE)
                with col_panel2:
                    with st.expander("🌍 Validación Macroclimática Base", expanded=True):
                        
                        if not df_integro.empty:
                            # Cálculos anuales
                            idx_max = df_integro['Precipitación'].idxmax()
                            idx_min = df_integro['Precipitación'].idxmin()
                            
                            max_año = int(df_integro.loc[idx_max, 'Año'])
                            max_val = df_integro.loc[idx_max, 'Precipitación']
                            min_año = int(df_integro.loc[idx_min, 'Año'])
                            min_val = df_integro.loc[idx_min, 'Precipitación']
                            
                            anios_niña_hitos = [1975, 1988, 1999, 2010, 2011, 2022]
                            anios_niño_hitos = [1983, 1992, 1997, 2015, 2023]
                            
                            diag_max = "✅ **Consistente:** Coincide con un evento histórico de excesos por La Niña." if max_año in anios_niña_hitos else "ℹ️ Máximo local regular."
                            diag_min = "✅ **Consistente:** Coincide con una sequía crítica por El Niño fuerte." if min_año in anios_niño_hitos else "ℹ️ Mínimo local regular."
                            
                            # Fila 1: Máximo Anual
                            st.markdown(f"**Año Más Lluvioso Registrado:**")
                            st.markdown(f"🥇 {max_año} con **{max_val:,.1f} mm/año**")
                            st.caption(diag_max)
                            st.divider()
                            
                            # Fila 2: Mínimo Anual
                            st.markdown(f"**Año Menos Lluvioso Registrado:**")
                            st.markdown(f"🌵 {min_año} con **{min_val:,.1f} mm/año**")
                            st.caption(diag_min)
                            st.divider()
                            
                            # Fila 3: Hitos Mensuales Absolutos de la Serie
                            st.markdown(f"**📊 Hitos Mensuales Absolutos de la Serie:**")
                            if Config.MONTH_COL in df_est.columns and not df_est.empty:
                                meses_dict = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
                                              7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
                                
                                idx_mes_max = df_est[Config.PRECIPITATION_COL].idxmax()
                                idx_mes_min = df_est[Config.PRECIPITATION_COL].idxmin()
                                
                                val_mes_max = df_est.loc[idx_mes_max, Config.PRECIPITATION_COL]
                                num_mes_max = int(df_est.loc[idx_mes_max, Config.MONTH_COL])
                                ano_mes_max = int(df_est.loc[idx_mes_max, Config.YEAR_COL])
                                
                                val_mes_min = df_est.loc[idx_mes_min, Config.PRECIPITATION_COL]
                                num_mes_min = int(df_est.loc[idx_mes_min, Config.MONTH_COL])
                                ano_mes_min = int(df_est.loc[idx_mes_min, Config.YEAR_COL])
                                
                                st.markdown(f"🌊 **Mes Más Lluvioso:** {meses_dict.get(num_mes_max, str(num_mes_max))} de {ano_mes_max} con **{val_mes_max:,.1f} mm**")
                                st.markdown(f"🍂 **Mes Menos Lluvioso:** {meses_dict.get(num_mes_min, str(num_mes_min))} de {ano_mes_min} con **{val_mes_min:,.1f} mm**")
                        else:
                            st.warning("⚠️ Sin suficientes años íntegros para emitir un dictamen macroclimático robusto.")
                
                # 📈 4. EVOLUCIÓN MULTIANUAL DE SOPORTE (AHORA EXPANDIBLE)
                st.markdown("---")
                with st.expander("📈 Evolución Multianual de Soporte", expanded=True):
                    df_grafico = df_anual.set_index('Año')[['Precipitación']]
                    st.bar_chart(df_grafico, color="#3498db")
                
                # ----------------------------------------------------------------------
                # 📊 REPORTES CONSOLIDADOS DE LA SELECCIÓN (TABLA MAESTRA)
                # ----------------------------------------------------------------------
                st.markdown("---")
                st.markdown("### 📊 Reporte Consolidado Forense de la Selección")
                st.markdown("Matriz unificada de estadísticas críticas para todas las estaciones activas en la delimitación actual.")
                
                registros_tabla = []
                for est_item in stations_for_analysis:
                    code_item = est_item.split('[')[1].replace(']', '').strip() if '[' in est_item else ""
                    name_item = est_item.split('[')[0].strip() if '[' in est_item else est_item
                    
                    df_sub = df_monthly_filtered[df_monthly_filtered[Config.STATION_NAME_COL].astype(str).str.contains(code_item if code_item else name_item)].copy()
                    df_sub = df_sub.dropna(subset=[Config.PRECIPITATION_COL])
                    
                    if not df_sub.empty:
                        df_sub_anual = df_sub.groupby(Config.YEAR_COL)[Config.PRECIPITATION_COL].agg(['sum', 'count']).reset_index()
                        df_sub_anual.columns = ['Año', 'Precipitación', 'Meses_Validos']
                        df_sub_integro = df_sub_anual[(df_sub_anual['Meses_Validos'] >= 10) & (df_sub_anual['Precipitación'] >= 700.0)]
                        
                        anios_activos = df_sub_anual.shape[0]
                        anios_integros = df_sub_integro.shape[0]
                        media_anual = df_sub_integro['Precipitación'].mean() if not df_sub_integro.empty else float('nan')
                        
                        if not df_sub_integro.empty:
                            idx_sub_max = df_sub_integro['Precipitación'].idxmax()
                            idx_sub_min = df_sub_integro['Precipitación'].idxmin()
                            max_val_anual = f"{df_sub_integro.loc[idx_sub_max, 'Precipitación']:,.1f} ({int(df_sub_integro.loc[idx_sub_max, 'Año'])})"
                            min_val_anual = f"{df_sub_integro.loc[idx_sub_min, 'Precipitación']:,.1f} ({int(df_sub_integro.loc[idx_sub_min, 'Año'])})"
                        else:
                            max_val_anual, min_val_anual = "N/D", "N/D"
                            
                        # 🚀 FIX PYARROW: Forzamos todo a string para evitar colisiones de tipos mixtos (float vs texto)
                        registros_tabla.append({
                            "Código/Estación": str(est_item),
                            "Años Activos": str(anios_activos),
                            "Años Íntegros": str(anios_integros),
                            "Media Anual (mm)": f"{media_anual:.1f}" if pd.notna(media_anual) else "N/D",
                            "Máximo Anual Histór. (Año)": max_val_anual,
                            "Mínimo Anual Histór. (Año)": min_val_anual
                        })
                
                if registros_tabla:
                    df_reporte_final = pd.DataFrame(registros_tabla)
                    
                    # 🚀 FIX PYARROW: Forzar todo a texto puro
                    df_reporte_final = df_reporte_final.astype(str) 
                    
                    st.dataframe(df_reporte_final, width="stretch", hide_index=True)
                    
                    csv_reporte = df_reporte_final.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Reporte de Estadísticas Básicas (CSV)",
                        data=csv_reporte,
                        file_name="Reporte_Consolidado_Forense_Hidro.csv",
                        mime="text/csv",
                        width="stretch"
                    )
            else:
                st.error("❌ No se pudieron procesar las series para la estación seleccionada.")
        else:
            st.info("👈 Seleccione una Cuenca o Municipio con estaciones activas en el menú lateral para iniciar el peritaje.")
            
    elif selected_module == "🔮 Pronóstico Climático": 
        # Llama al visualizador reconstruido (que ahora tiene historia, NOAA y Prophet)
        viz.display_climate_forecast_tab(**display_args)
        
        # =========================================================================
        # 2. NUEVA SECCIÓN: EMISOR CLIMÁTICO (MULTIVERSO ENSO) HACIA EL METABOLISMO
        # =========================================================================

        st.markdown("---")
        st.subheader("📡 Emisor Climático: Multiverso Probabilístico (IRI)")
        st.info("Integra el pronóstico atmosférico en vivo con la realidad terrestre. Exporta el paquete de probabilidades completo a la Memoria Global para evaluar el Riesgo Esperado en el metabolismo territorial y la toma de decisiones.")
        
        # Leemos las probabilidades vivas del Aleph (o asignamos 100% neutro si apenas está cargando)
        p_nino = st.session_state.get('aleph_iri_nino', 0)
        p_neutro = st.session_state.get('aleph_iri_neutro', 100) 
        p_nina = st.session_state.get('aleph_iri_nina', 0)
        
        # Definimos los impactos físicos (anomalías) para cada universo (Ajustables según tu criterio)
        impacto_nino = 0.65   # -35% de Oferta Hídrica (Sequía)
        impacto_neutro = 1.00 # 100% de Oferta Hídrica (Normal)
        impacto_nina = 1.35   # +35% de Oferta Hídrica (Exceso/Inundación)
        
        # Cálculo de la Esperanza Matemática: Factor de Anomalía Esperado Ponderado
        factor_esperado = ((p_nino * impacto_nino) + (p_neutro * impacto_neutro) + (p_nina * impacto_nina)) / 100.0
        
        col_enso1, col_enso2 = st.columns([1.5, 1])
        with col_enso1:
            st.markdown("##### 🌌 Universos Paralelos Integrados:")
            st.markdown(f"- ☀️ **Universo Niño ({p_nino}% prob):** Oferta al 65% (Déficit)")
            st.markdown(f"- ⚖️ **Universo Neutro ({p_neutro}% prob):** Oferta al 100% (Histórico)")
            st.markdown(f"- 🌧️ **Universo Niña ({p_nina}% prob):** Oferta al 135% (Exceso)")
            
        with col_enso2:
            st.metric("Factor de Oferta Esperado (Riesgo Ponderado)", f"{factor_esperado:.2f}x", 
                      f"{(factor_esperado-1)*100:+.1f}% impacto real proyectado", 
                      delta_color="normal" if factor_esperado >= 1 else "inverse")
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("🚀 Enviar Multiverso al Aleph", width="stretch"):
                # 1. Enviamos el paquete completo para el Optimizador de la Pág 09
                st.session_state['aleph_clima_multiverso'] = {
                    "Niño": impacto_nino,
                    "Neutro": impacto_neutro,
                    "Niña": impacto_nina
                }
                
                # 2. Compatibilidad hacia atrás: enviamos el factor esperado para la Pág 08 (Sistemas Hídricos)
                st.session_state['factor_clima_enso'] = factor_esperado
                st.session_state['nombre_escenario_enso'] = f"Multiverso IRI ({factor_esperado:.2f}x)"
                
                st.success("✅ ¡Multiverso inyectado! Ve a Toma de Decisiones o Sistemas Hídricos para ver el impacto probabilístico.")
                
    elif selected_module == "📉 Tendencias": viz.display_trends_and_forecast_tab(**display_args)
    elif selected_module == "⚠️ Anomalías": viz.display_anomalies_tab(**display_args)
    elif selected_module == "🔗 Correlación": viz.display_correlation_tab(**display_args)
    elif selected_module == "🌊 Extremos": viz.display_drought_analysis_tab(**display_args)
    elif selected_module == "🌀 Dinámica de Sistemas": 
        viz.display_enso_system_dynamics_tab(
            df_monthly_filtered=display_args["df_monthly_filtered"],
            nombre_zona=nombre_zona,
            gdf_zona=gdf_zona
        )
    
    # --- MÓDULO: MAPAS AVANZADOS (VERSIÓN DEFINITIVA CORREGIDA) ---
    elif selected_module == "🌍 Mapas Avanzados":
        
        # 🚀 LAZY LOADING: Importamos las librerías pesadas SOLO si el usuario entra aquí
        import io
        import os
        import numpy as np
        import rasterio
        from rasterio.warp import reproject, Resampling, calculate_default_transform
        from rasterio.io import MemoryFile
        from modules import hydro_physics as physics
        from modules.utils import cargar_capa_espacial_cache
        
        # --- A. FUNCIONES AUXILIARES LOCALES ---
        def local_warper_force_4326(tif_path, bounds_wgs84, shape_out):
            """Reproyección forzada a WGS84 (Compatible con Nube y Local)."""
            
            # Parche para Windows/PROJ
            if os.name == 'nt':
                try:
                    import pyproj
                    os.environ['PROJ_LIB'] = pyproj.datadir.get_data_dir()
                except: pass

            try:
                # --- LÓGICA CENTRAL (Para evitar errores de indentación al repetir) ---
                def _core_process(src):
                    transform, width, height = calculate_default_transform(
                        src.crs, 'EPSG:4326', src.width, src.height, *src.bounds
                    )
                    minx, miny, maxx, maxy = bounds_wgs84
                    dst_transform = rasterio.transform.from_bounds(minx, miny, maxx, maxy, shape_out[0], shape_out[1])
                    destination = np.zeros(shape_out, dtype=np.float32)
                    
                    reproject(
                        source=rasterio.band(src, 1), 
                        destination=destination,
                        src_transform=src.transform, 
                        src_crs=src.crs,
                        dst_transform=dst_transform, 
                        dst_crs='EPSG:4326',
                        resampling=Resampling.bilinear,
                        dst_nodata=np.nan
                    )
                    return destination

                # --- APERTURA SEGÚN TIPO DE ARCHIVO ---
                
                # CASO 1: Archivo en Memoria (BytesIO desde Supabase)
                if isinstance(tif_path, (io.BytesIO, bytes)) or hasattr(tif_path, 'read'):
                    
                    # 🛡️ BLINDAJE BytesIO: Rebobinar el puntero al inicio (EOF Fix)
                    if hasattr(tif_path, 'seek'):
                        tif_path.seek(0)
                        
                    with MemoryFile(tif_path) as memfile:
                        with memfile.open() as src:
                            return _core_process(src)
                # CASO 2: Ruta de archivo normal (String)
                else:
                    with rasterio.open(tif_path) as src:
                        return _core_process(src)

            except Exception:
                return None

        def generar_popup_html_avanzado(row):
            """Popup HTML enriquecido."""
            nombre = str(row.get(Config.STATION_NAME_COL, 'Estación'))
            muni = str(row.get('municipio', 'N/A'))
            alt = float(row.get('altitud', 0))
            ppt = float(row.get('ppt_media', 0))
            std = float(row.get('ppt_std', 0))
            
            return f"""
            <div style='font-family:sans-serif; font-size:12px; min-width:160px; line-height:1.4;'>
                <b style='color:#1f77b4; font-size:14px'>{nombre}</b><hr style='margin:4px 0; border-top:1px solid #ddd'>
                📍 <b>Mpio:</b> {muni}<br>
                ⛰️ <b>Altitud:</b> {alt:.0f} msnm<br>
                💧 <b>P. Anual:</b> {ppt:.0f} mm<br>
                📊 <b>Desv. Std:</b> ±{std:.0f} mm
            </div>
            """

        if not PHYSICS_AVAILABLE:
            st.error("❌ Módulos 'hydro_physics' o 'admin_utils' no disponibles.")
        else:
            st.header("🌍 Modelación Hidrológica Distribuida (Aleph)")
            
            # --- 0. CARGA DE RECURSOS (NUBE SUPABASE) ---
            # Inicializamos variables
            dem_path = None # En este caso, será un objeto en memoria (BytesIO), no un "path" de texto
            cov_path = None
            gdf_bocatomas = None 

            # A. Carga de Rasters desde BD (Sin archivos locales)
            try:
                # Usamos la función global cargar_raster_db definida al inicio del script
                # (Si no está definida arriba, avísame para dártela)
                dem_bytes = cargar_raster_db("DemAntioquia_EPSG3116.tif")
                cov_bytes = cargar_raster_db("Cob25m_WGS84.tif") # Asegúrate de subir este también si lo usas
                
                if dem_bytes:
                    dem_path = dem_bytes # Asignamos el objeto bytes a la variable
                else:
                    st.error("⛔ Falta el DEM en la Base de Datos. Súbelo en el Panel Admin.")
                    st.stop()
                    
                if cov_bytes:
                    cov_path = cov_bytes
            except NameError:
                st.error("⚠️ La función 'cargar_raster_db' no está definida. Revisa el Paso 2 de las instrucciones.")
                st.stop()

            # B. Bocatomas (Carga Segura)
            try:
                # Intentamos importar get_engine solo si es necesario
                from modules.db_manager import get_engine
                engine = get_engine()
                if engine:
                    gdf_bocatomas = cargar_capa_espacial_cache("SELECT * FROM bocatomas", engine, geom_col="geometry")
                    # Estandarización de nombre para visualizer
                    if 'nombre_bocatoma' in gdf_bocatomas.columns: 
                        gdf_bocatomas['nombre_predio'] = gdf_bocatomas['nombre_bocatoma'] 
                    elif 'nombre' in gdf_bocatomas.columns: 
                        gdf_bocatomas['nombre_predio'] = gdf_bocatomas['nombre']
                    else: 
                        gdf_bocatomas['nombre_predio'] = "Bocatoma"
            except Exception as e:
                # Si falla la BD o no existe la tabla, seguimos sin bocatomas (no es crítico)
                gdf_bocatomas = None

            # 1. CONFIGURACIÓN GRID Y SINCRONIZACIÓN ESPACIAL
            # 🤝 LECTURA MAESTRA: El lienzo toma el tamaño exacto que el Sidebar le dicte
            
            # Buscamos el valor en las posibles variables del sidebar (por si cambió de nombre)
            buffer_km = float(st.session_state.get("buffer_km", st.session_state.get("buffer_global_km", 15.0)))
            
            # Forzamos la actualización visual para que refleje el número exacto
            st.info(f"📏 Modelando con un área de influencia de **{buffer_km} km** (Sincronizado con el panel lateral).")
            
            # Dejamos solo el slider de resolución para no saturar la interfaz
            grid_res = st.slider("Resolución del Grid (Celdas)", min_value=50, max_value=500, value=100, help="Mayor resolución = más detalle pero más tiempo de cálculo.")
            
            # 2. GEOMETRÍA (El Fix Métrico Real)
            if gdf_zona is None or gdf_zona.empty: 
                gdf_zona = gdf_filtered
            
            # 🚀 FIX: Buffer Geodésico Real (Evita deformaciones por usar grados)
            # Proyectamos a Magna-Sirgas (EPSG:3116) para trabajar en metros reales
            gdf_zona_proj = gdf_zona.to_crs(epsg=3116)
            
            if buffer_km > 0:
                gdf_zona_proj['geometry'] = gdf_zona_proj.geometry.buffer(buffer_km * 1000)
                
            # Devolvemos a grados (WGS84) para calcular la caja matemática
            gdf_buffer = gdf_zona_proj.to_crs(epsg=4326)
            minx, miny, maxx, maxy = gdf_buffer.total_bounds
            
            # Creamos la malla matemática (Meshgrid)
            import numpy as np 
            xi = np.linspace(minx, maxx, grid_res)
            yi = np.linspace(miny, maxy, grid_res)
            grid_x, grid_y = np.meshgrid(xi, yi)
            bounds_calc = (minx, miny, maxx, maxy)
            
            # 3. DATOS ESTACIONES
            df_annual_sums = df_monthly_filtered.groupby([Config.STATION_NAME_COL, Config.YEAR_COL])[Config.PRECIPITATION_COL].sum(min_count=10).reset_index()
            df_stats = df_annual_sums.groupby(Config.STATION_NAME_COL)[Config.PRECIPITATION_COL].agg(['mean', 'std']).reset_index()
            df_stats.columns = [Config.STATION_NAME_COL, 'ppt_media', 'ppt_std']
            
            gdf_calc = gdf_filtered.merge(df_stats, on=Config.STATION_NAME_COL)
            gdf_calc = gdf_calc.dropna(subset=['ppt_media', 'geometry'])
            gdf_calc['ppt_media'] = pd.to_numeric(gdf_calc['ppt_media'], errors='coerce').fillna(0)
            gdf_calc['ppt_std'] = pd.to_numeric(gdf_calc['ppt_std'], errors='coerce').fillna(0)
            gdf_calc['popup_html'] = gdf_calc.apply(generar_popup_html_avanzado, axis=1)

            # 4. PROCESAMIENTO DEM Y COBERTURAS
            # Usamos las rutas directas de Config (que ahora apuntan a la nube)
            dem_path = Config.DEM_FILE_PATH
            # 🚀 FIX: Usamos el nombre estandarizado y añadimos un buscador por si acaso
            cov_path = getattr(Config, 'LAND_COVER_FILE_PATH', getattr(Config, 'LAND_COVER_RASTER_PATH', None))

            dem_array = None
            with st.spinner("🏔️ Conectando con Supabase y procesando topografía..."):
                try: 
                    # Usa el mismo warper que construimos para hydro_physics
                    dem_array = physics.warper_raster_to_grid(dem_path, bounds_calc, grid_x.shape)
                except Exception as e: 
                    st.warning(f"Aviso Topografía: {e}")
            
            # 5. EJECUCIÓN
            metodo = st.selectbox("Método Interpolación", ['kriging', 'idw', 'spline', 'ked'])
            
            if st.button("🚀 Ejecutar Modelo"):
                st.session_state['ejecutar_aleph'] = True
            
            if st.session_state.get('ejecutar_aleph', False):
                col_close = st.columns([6, 1])[1]
                if col_close.button("❌ Cerrar"):
                    st.session_state['ejecutar_aleph'] = False; st.rerun()

                with st.spinner("Calculando balance hídrico distribuido (esto puede tardar unos segundos)..."):
                    try:
                        # 0. CARGAR MUNICIPIOS (Bypass v2)
                        gdf_municipios = None
                        try:
                            import geopandas as gpd
                            from modules.db_manager import get_engine
                            eng = get_engine()
                            # Leemos la tabla v2 que acabas de subir
                            gdf_municipios = cargar_capa_espacial_cache("SELECT * FROM municipios", eng, geom_col="geometry")
                            
                            # Forzar sistema de coordenadas para Folium
                            if gdf_municipios.crs is None:
                                gdf_municipios.set_crs("EPSG:4326", inplace=True)
                            elif gdf_municipios.crs != "EPSG:4326":
                                gdf_municipios = gdf_municipios.to_crs("EPSG:4326")
                            
                            # Limpieza de nombres para el popup
                            gdf_municipios = gdf_municipios.rename(columns={'MPIO_CNMBR': 'Municipio'})

                        except ImportError:
                            st.error("❌ Error Crítico: La librería 'geopandas' no está instalada en el servidor.")
                            
                        except Exception as e:
                            st.warning(f"Capa de municipios v2 no disponible aún: {e}")
                            
                        # 1. DATOS ESTACIONES
                        df_anios_count = df_monthly_filtered.groupby(Config.STATION_NAME_COL)[Config.YEAR_COL].nunique().reset_index(name='n_anios')
                        gdf_calc = gdf_calc.merge(df_anios_count, on=Config.STATION_NAME_COL, how='left').fillna(0)

                        # A. INTERPOLACIÓN HISTÓRICA BASE
                        dem_safe = np.nan_to_num(dem_array, nan=0) if dem_array is not None else None
                        
                        # 💉 BISTURÍ: Enrutamos el Motor Aleph hacia nuestro nuevo interpolador blindado
                        try:
                            from modules.interpolation import interpolador_maestro
                            Z_P_base, Z_Err = interpolador_maestro(
                                df_puntos=gdf_calc, 
                                col_val='ppt_media', 
                                grid_x=grid_x, 
                                grid_y=grid_y, 
                                metodo=str(metodo).lower(), 
                                dem_grid=dem_safe
                            )
                        except Exception as e:
                            st.warning(f"Error en interpolador maestro: {e}. Usando fallback...")
                            Z_P_base, Z_Err = physics.interpolar_variable(
                                gdf_calc, 'ppt_media', grid_x, grid_y, method=metodo, dem_array=dem_safe
                            )
                            
                        if metodo == 'ked': Z_P_base = np.maximum(Z_P_base, 0)

                        # B. BISTURÍ: INYECCIÓN DE ESCENARIOS CMIP6 (Cambio Climático)
                        delta_ppt_sim = st.session_state.get('sim_delta_ppt', 0.0) 
                        delta_temp_sim = st.session_state.get('sim_delta_temp', 0.0)

                        Z_P = Z_P_base * (1 + (delta_ppt_sim / 100.0))
                        
                        # C. MOTOR FÍSICO DISTRIBUIDO (Conectado a la Nube)
                        # AQUÍ ASEGURAMOS QUE cov_path y dem_path SE ENVÍAN AL MOTOR
                        matrices_finales = physics.run_distributed_model(
                            Z_P, grid_x, grid_y, {'dem': dem_path, 'cobertura': cov_path}, bounds_calc
                        )
                        
                        # C. INCERTIDUMBRE
                        if Z_Err is not None:
                            matrices_finales['12. Incertidumbre Interpolación (Std)'] = Z_Err

                        # D. VECTORES (Predios / Bocatomas)
                        gdf_predios_viz = None
                        try:
                            # Intentamos recargar DIRECTAMENTE de la BD para tener todas las columnas (pk_predios, nombre_pre, etc.)
                            from modules.db_manager import get_engine
                            gdf_predios_viz = cargar_capa_espacial_cache("SELECT * FROM predios", get_engine(), geom_col="geometry")
                            
                            # Aseguramos proyección WGS84 para el mapa
                            if gdf_predios_viz.crs and gdf_predios_viz.crs.to_string() != "EPSG:4326":
                                gdf_predios_viz = gdf_predios_viz.to_crs("EPSG:4326")
                        except Exception as e:
                            # Si falla la recarga (o no hay BD conectada), usamos la variable global como respaldo
                            if gdf_predios is not None and not gdf_predios.empty:
                                gdf_predios_viz = gdf_predios.copy()

                        # Bocatomas (Misma lógica de seguridad)
                        gdf_bocatomas_viz = None
                        if gdf_bocatomas is not None and not gdf_bocatomas.empty:
                             gdf_bocatomas_viz = gdf_bocatomas.copy()

                        # E. VISUALIZACIÓN
                        viz.display_advanced_maps_tab(
                            df_long=df_monthly_filtered,
                            gdf_stations=gdf_calc,
                            matrices=matrices_finales, 
                            grid=(grid_x, grid_y),
                            mask=None, 
                            gdf_zona=gdf_zona, 
                            gdf_buffer=gdf_buffer, 
                            gdf_predios=gdf_predios_viz, # <--- Aquí va la versión recargada y completa
                            gdf_bocatomas=gdf_bocatomas_viz,
                            gdf_municipios=gdf_municipios
                        )
                        
                        # F. DASHBOARD DE ESTADÍSTICAS (5 COLUMNAS - SUPER COMPLETO)
                        st.markdown("---")
                        st.markdown(f"### 📊 Diagnóstico Hidrológico Integral: {nombre_zona}")
                        
                        try:
                            # 🔥 FIX ANTI-COLAPSO (TOPOLOGY EXCEPTION)
                            # Reparamos cualquier "nudo" o cruce inválido en el polígono antes de medirlo
                            gdf_zona_valida = gdf_zona.copy()
                            gdf_zona_valida['geometry'] = gdf_zona_valida.geometry.make_valid()

                            # --- 1. CÁLCULOS GEOMÉTRICOS ---
                            gdf_zona_proj = gdf_zona_valida.to_crs(epsg=3116) # Proyectar a metros (Magna Sirgas)
                            area_km2 = gdf_zona_proj.area.sum() / 1e6
                            perim_km = gdf_zona_proj.length.sum() / 1e3
                            
                            # Índice de Forma (Compacidad de Gravelius): Kc = 0.28 * P / sqrt(A)
                            ind_gravelius = (0.282 * perim_km) / (np.sqrt(area_km2)) if area_km2 > 0 else 0

                            # --- 2. EXTRACCIÓN DE VARIABLES DEL MODELO ---
                            from shapely.vectorized import contains
                            
                            # Usamos la geometría ya reparada y simplificada levemente si es muy compleja
                            geom_unificada = gdf_zona_valida.geometry.simplify(0.001).unary_union
                            mask_exact = contains(geom_unificada, grid_x, grid_y)
                            
                            # 🏔️ EXTRACCIÓN TOPOGRÁFICA DIRECTA DEL DEM (Para Telemetría Global)
                            alt_media, alt_max, alt_min = 1500.0, 1500.0, 1500.0
                            if dem_array is not None:
                                alts_mask = dem_array[mask_exact]
                                # Filtramos nodata o valores anómalos de bordes
                                alts_validas = alts_mask[(alts_mask > -500) & (alts_mask != 0)]
                                if len(alts_validas) > 0:
                                    alt_media = np.nanmean(alts_validas)
                                    alt_max = np.nanmax(alts_validas)
                                    alt_min = np.nanmin(alts_validas)
                            
                            # 💉 INYECCIÓN AL ALEPH (Para que el Simulador ENSO los herede sin recalcular)
                            st.session_state['aleph_altitud_m'] = float(alt_media)
                            st.session_state['aleph_altitud_max'] = float(alt_max)
                            st.session_state['aleph_altitud_min'] = float(alt_min)
                            
                            def get_avg(keyword): 
                                """Busca la capa en matrices_finales y calcula el promedio zonal."""
                                for k, v in matrices_finales.items():
                                    if keyword in k and v is not None: 
                                        return np.nanmean(v[mask_exact])
                                return 0
                            
                            v_ppt = get_avg("Precipitación")
                            v_temp = get_avg("Temperatura")
                            v_etr = get_avg("Evapotranspiración")
                            v_esc = get_avg("Escorrentía")
                            v_inf = get_avg("Infiltración")
                            v_rec_pot = get_avg("Recarga Potencial")
                            v_rec_real = get_avg("Recarga Real")
                            
                            # --- 3. HIDROLOGÍA Y CAUDALES ---
                            # Factor Q (m3/s) = (mm/año * km2 * 1000) / (31536000 s/año)
                            factor_q = (area_km2 * 1000) / 31536000
                            
                            # Caudales Estimados
                            Q_medio = (v_esc + v_rec_real) * factor_q # Oferta Hídrica Total
                            Q_base = v_rec_real * factor_q # Flujo base (aprox Caudal Mínimo sostenido)
                            Q_maximo = Q_medio * 2.5 # Estimación empírica pico anual (sin datos diarios)
                            Q_ecologico = Q_medio * 0.25 # 25% del Medio (Criterio MADS usual)
                            
                            # Rendimiento Hídrico (m3/ha-año)
                            # 1 mm = 10 m3/ha
                            Rendimiento_m3ha = (v_esc + v_rec_real) * 10 

                            # --- 4. ÍNDICES CLIMÁTICOS Y DE EROSIÓN ---
                            # Índice de Aridez (Martonne): I = P / (T + 10)
                            # 0-10 (Árido), 20-30 (Húmedo), >55 (Perhúmedo)
                            ind_martonne_aridez = v_ppt / (v_temp + 10) if v_temp else 0
                            
                            # Índice Climático (Lang): I = P / T
                            ind_lang = v_ppt / v_temp if v_temp > 0 else 0
                            
                            # Erosividad (Aprox Fournier Modificado o R-USLE simplificado)
                            # R = 0.0739 * P^1.8 (Aprox tropical)
                            ind_erosividad = 0.07 * (v_ppt ** 1.5)

                            # --- 5. RENDERIZADO (5 COLUMNAS) ---
                            # 🎨 INYECCIÓN CSS: Convertimos st.metric en Tarjetas Premium
                            st.markdown("""
                            <style>
                            div[data-testid="metric-container"] {
                                background-color: #fdfdfd;
                                border: 1px solid #e0e0e0;
                                padding: 15px;
                                border-radius: 8px;
                                box-shadow: 2px 2px 8px rgba(0,0,0,0.04);
                                transition: transform 0.2s ease;
                            }
                            div[data-testid="metric-container"]:hover {
                                transform: translateY(-2px);
                                box-shadow: 2px 4px 12px rgba(0,0,0,0.08);
                                border-color: #3498db;
                            }
                            </style>
                            """, unsafe_allow_html=True)

                            k1, k2, k3, k4, k5 = st.columns(5)
                            
                            # COL 1: MORFOMETRÍA
                            k1.markdown("#### 📏 Morfometría")
                            k1.metric("Área", f"{area_km2:.2f} km²")
                            # ⛰️ NUEVO: Integración de Elevaciones
                            k1.metric("Elevación Media", f"{alt_media:,.0f} msnm", f"Mín: {alt_min:,.0f}m | Máx: {alt_max:,.0f}m", delta_color="off")
                            k1.metric("Perímetro", f"{perim_km:.1f} km")
                            k1.metric("Índice Gravelius", f"{ind_gravelius:.2f}", "Forma (Kc)")
                            k1.metric("Estaciones Base", f"{len(gdf_calc)}")
                            
                            # COL 2: BALANCE HÍDRICO
                            k2.markdown("#### 💧 Balance (mm)")
                            k2.metric("Precipitación", f"{v_ppt:.0f} mm")
                            k2.metric("ETR", f"{v_etr:.0f} mm", "Pérdida")
                            k2.metric("Escorrentía", f"{v_esc:.0f} mm", "Superficial")
                            k2.metric("Infiltración", f"{v_inf:.0f} mm", "Suelo")
                            
                            # COL 3: CAUDALES
                            k3.markdown("#### 🌊 Caudales (m³/s)")
                            k3.metric("Caudal Medio", f"{Q_medio:.2f}")
                            k3.metric("Caudal Mínimo", f"{Q_base:.2f}", "Base Est.")
                            k3.metric("Caudal Máximo", f"{Q_maximo:.2f}", "Pico Est.")
                            k3.metric("Caudal Ecológico", f"{Q_ecologico:.2f}", "25% Qm")
                            
                            # COL 4: ÍNDICES
                            k4.markdown("#### 📉 Índices")
                            k4.metric("Rendimiento", f"{Rendimiento_m3ha:.0f}", "m³/ha-año")
                            k4.metric("Aridez (Martonne)", f"{ind_martonne_aridez:.1f}")
                            k4.metric("Factor Lang", f"{ind_lang:.1f}", "Clima")
                            k4.metric("Erosividad", f"{ind_erosividad:.0f}", "Potencial")

                            # COL 5: AGUAS SUBTERRÁNEAS (NUEVA)
                            k5.markdown("#### ⏬ Aguas Subt.")
                            k5.metric("Recarga Potencial", f"{v_rec_pot:.0f} mm", "Infiltración Total")
                            k5.metric("Recarga Real", f"{v_rec_real:.0f} mm", "Acuífero")
                            k5.metric("Volumen Recarga", f"{(v_rec_real * area_km2 * 1000):.2e} m³", "Anual")
                            
                            # 🌐 INYECCIÓN COMPLETA AL ALEPH (Memoria Global para todo el Gemelo Digital)
                            st.session_state['aleph_ppt_anual'] = float(v_ppt)
                            st.session_state['aleph_etr_anual'] = float(v_etr)
                            st.session_state['aleph_esc_anual'] = float(v_esc)
                            st.session_state['aleph_inf_anual'] = float(v_inf)
                            st.session_state['aleph_rec_pot_mm'] = float(v_rec_pot)
                            st.session_state['aleph_recarga_mm'] = float(v_rec_real)
                            st.session_state['aleph_area_km2'] = float(area_km2)
                            st.session_state['recarga_total_m3'] = float(v_rec_real * area_km2 * 1000.0)
                            
                            # 🚀 LAS NUEVAS CONEXIONES HIDROLÓGICAS UNIFICADAS
                            st.session_state['aleph_q_rio_m3s'] = float(Q_medio)      # Caudal Medio Oferta Total
                            st.session_state['aleph_q_min_m3s'] = float(Q_base)       # Caudal Mínimo (Estiaje / Base)
                            st.session_state['aleph_q_max_m3s'] = float(Q_maximo)     # Caudal Máximo Pico
                            st.session_state['aleph_q_eco_m3s'] = float(Q_ecologico)  # Caudal Ecológico (25% Qm)
                            
                            st.success("🧠 **¡Conexión Exitosa!** Balance completo, caudales y recarga inyectados en vivo al Gemelo Digital (`Aguas Subterráneas`, `Calidad`, `Toma de Decisiones` y `Simulador Integral`).")
                            
                            # 💾 BOTÓN PARA SELLAR ESTE CÁLCULO EN LA MATRIZ HIDROLÓGICA MAESTRA DE SUPABASE
                            if st.button(f"💾 Sellar Física de '{nombre_zona}' en Matriz Hidrológica Maestra (Supabase)", type="primary"):
                                try:
                                    from sqlalchemy import text
                                    from modules.db_manager import get_engine
                                    import unicodedata, re
                                    
                                    eng_h = get_engine()
                                    with eng_h.connect() as conn:
                                        df_hm = pd.read_sql(text("SELECT * FROM matriz_hidrologica_maestra LIMIT 1"), conn)
                                    cols_hm = df_hm.columns.tolist()
                                    
                                    # Actualizamos dinámicamente las columnas que existan en matriz_hidrologica_maestra
                                    mapeo_posible = {
                                        'area_km2': float(area_km2), 'Area_km2': float(area_km2),
                                        'altitud_m': float(alt_media), 'Altitud_m': float(alt_media),
                                        'temp_c': float(v_temp), 'Temp_C': float(v_temp),
                                        'lluvia_mm': float(v_ppt), 'Lluvia_mm': float(v_ppt),
                                        'precipitacion_mm': float(v_ppt), 'Precipitacion_mm': float(v_ppt), 'ppt_mm': float(v_ppt),
                                        'etr_mm': float(v_etr), 'ETR_mm': float(v_etr),
                                        'escorrentia_mm': float(v_esc), 'Escorrentia_mm': float(v_esc),
                                        'infiltracion_mm': float(v_inf), 'Infiltracion_mm': float(v_inf),
                                        'recarga_mm': float(v_rec_real), 'Recarga_mm': float(v_rec_real), 'recarga_real_mm': float(v_rec_real),
                                        'caudal_medio_m3s': float(Q_medio), 'Caudal_Medio_m3s': float(Q_medio), 'Q_Medio_m3s': float(Q_medio), 'q_medio_m3s': float(Q_medio), 'Caudal_Medio': float(Q_medio),
                                        'caudal_min_m3s': float(Q_base), 'Caudal_Min_m3s': float(Q_base), 'Q_Min_m3s': float(Q_base), 'q_min_m3s': float(Q_base), 'Caudal_Minimo': float(Q_base),
                                        'caudal_max_m3s': float(Q_maximo), 'Caudal_Max_m3s': float(Q_maximo), 'Q_Max_m3s': float(Q_maximo), 'q_max_m3s': float(Q_maximo),
                                        'caudal_eco_m3s': float(Q_ecologico), 'Caudal_Eco_m3s': float(Q_ecologico), 'Q_Eco_m3s': float(Q_ecologico), 'q_eco_m3s': float(Q_ecologico)
                                    }
                                    sets_sql = []
                                    params_sql = {'terr': str(nombre_zona).strip()}
                                    for c_bd in cols_hm:
                                        if c_bd in mapeo_posible:
                                            sets_sql.append(f'"{c_bd}" = :{c_bd}')
                                            params_sql[c_bd] = mapeo_posible[c_bd]
                                    
                                    col_terr_h = next((c for c in cols_hm if c.lower() in ['territorio', 'nombre', 'unidad', 'cuenca', 'municipio']), 'Territorio')
                                    if sets_sql:
                                        q_up = text(f'UPDATE matriz_hidrologica_maestra SET {", ".join(sets_sql)} WHERE UPPER(TRIM("{col_terr_h}")) = UPPER(TRIM(:terr))')
                                        with eng_h.begin() as conn:
                                            conn.execute(q_up, params_sql)
                                        st.cache_data.clear()
                                        st.success(f"✅ ¡Matriz Hidrológica Maestra actualizada en Supabase para **{nombre_zona}** con Caudal Medio = {Q_medio:,.2f} m³/s!")
                                except Exception as ex_h:
                                    st.error(f"Error actualizando matriz hidrológica: {ex_h}")

                            # 🧹 GARBAGE COLLECTION: Liberamos la memoria RAM de los pesados arrays raster
                            del matrices_finales
                            if 'dem_array' in locals(): del dem_array
                            import gc; gc.collect()
                            
                        except Exception as e:
                            st.warning(f"Cálculos parciales: {e}")

                    except Exception as e:
                        st.error(f"Error crítico: {e}")

    # --- OTROS MÓDULOS ---
    elif selected_module == "🧪 Sesgo": viz.display_bias_correction_tab(**display_args)
    elif selected_module == "🌿 Cobertura": viz.display_land_cover_analysis_tab(**display_args)

    # --- ZONAS DE VIDA (NATIVO EN LA NUBE) ---
    elif selected_module == "🌱 Zonas Vida":
        # 1. Le pasamos las URLs directas a los argumentos del visualizador
        display_args['dem_file'] = Config.DEM_FILE_PATH
        display_args['ppt_file'] = Config.PRECIP_RASTER_PATH
        
        # 2. Llamamos al visualizador
        try:
            viz.display_life_zones_tab(**display_args)
        except Exception as e:
            st.error(f"⚠️ Error renderizando Zonas de Vida: {e}. Asegúrate de que los Rasters estén en Supabase.")
            
    elif selected_module == "🌡️ Clima Futuro": viz.display_climate_scenarios_tab(**display_args)
    
    # --- ISOYETAS HD (MOTOR FOLIUM - SIG COMPLETO, POLÍGONO TERRITORIAL Y BLINDAJE DE DATOS) ---
    elif selected_module == "✨ Mapas Isoyetas HD":
        import numpy as np
        import geopandas as gpd
        from shapely.geometry import Point
        from modules.interpolation import interpolador_maestro
        import folium
        from streamlit_folium import st_folium
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        import scipy.linalg as la
        import io
        import base64
        
        st.header("🗺️ Laboratorio Geoestadístico Dual (Visor SIG)")
        
        # --- 1. CAJA DE HERRAMIENTAS CARTOGRÁFICAS Y CLÍNICA DE DATOS ---
        col_herramientas, col_clinica = st.columns([2, 1])
        
        with col_herramientas:
            st.markdown("**Opciones de Diseño**")
            hc1, hc2, hc3, hc4 = st.columns([1.2, 1.2, 0.8, 1.1])
            colorscale_sel = hc1.selectbox("🎨 Escala:", ["Viridis", "Turbo", "Plasma", "YlGnBu", "Spectral", "Inferno"])
            suavidad = hc2.slider("🌫️ Transparencia:", 0.0, 1.0, 0.65)
            mostrar_lineas = hc3.checkbox("📉 Líneas", value=True)
            unificar_escala = hc4.checkbox("🔗 Unificar A=B", value=True, help="Usa el mismo rango de colores en ambos mapas para comparar años Niño vs. Niña sin distorsión visual.")
            
        with col_clinica:
            st.markdown("**Motor de Inteligencia**")
            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("✨ Activar Aleph", type="primary", use_container_width=True):
                st.session_state['usar_aleph'] = True
            if c_btn2.button("❌ Desactivar", use_container_width=True):
                st.session_state['usar_aleph'] = False
                
        estado_aleph = st.session_state.get('usar_aleph', False)
        if estado_aleph:
            st.info("🧠 **El Aleph está ACTIVO:** Reconstruyendo meses faltantes y falsos ceros con la red espacial de estaciones vecinas.")
        else:
            st.caption("🔍 **Modo Observacional Puro:** Mostrando estaciones con >=80% de meses válidos en el año (sin ceros ni duplicados).")
            
        cmap_dict = {"Viridis": "viridis", "Turbo": "turbo", "Plasma": "plasma", "YlGnBu": "YlGnBu", "Spectral": "Spectral", "Inferno": "inferno"}
        cmap_mpl = cmap_dict.get(colorscale_sel, "viridis")
        
        enso_historico = {
            2010: "🌧️ La Niña Fuerte",
            2011: "🌧️ La Niña Moderada",
            2012: "⚖️ Neutro",
            2013: "⚖️ Neutro",
            2014: "⚖️ Neutro",
            2015: "☀️ El Niño Muy Fuerte",
            2016: "☀️ El Niño Fuerte / Transición",
            2017: "🌧️ La Niña Débil / Neutro",
            2018: "⚖️ Neutro",
            2019: "☀️ El Niño Débil",
            2020: "🌧️ La Niña Moderada",
            2021: "🌧️ La Niña Moderada",
            2022: "🌧️ La Niña Fuerte",
            2023: "☀️ El Niño Fuerte",
            2024: "☀️ El Niño / Neutro",
            2025: "🌧️ La Niña Débil / Neutro Frío",
            2026: "🔥 Súper El Niño"
        }
        
        def obtener_etiqueta_enso(anio):
            from datetime import datetime
            anio_int = int(anio)
            if anio_int == datetime.now().year:
                oni_vivo = None
                for k in ['oni_actual', 'oni', 'aleph_oni', 'ultimo_oni', 'oni_val', 'indice_oni']:
                    val = st.session_state.get(k)
                    if val is not None:
                        try:
                            oni_vivo = float(val)
                            break
                        except (TypeError, ValueError):
                            pass
                if oni_vivo is not None:
                    if oni_vivo >= 2.0:   return f"🔥 Súper El Niño (ONI {oni_vivo:+.2f})"
                    if oni_vivo >= 1.5:   return f"☀️ El Niño Fuerte (ONI {oni_vivo:+.2f})"
                    if oni_vivo >= 1.0:   return f"☀️ El Niño Moderado (ONI {oni_vivo:+.2f})"
                    if oni_vivo >= 0.5:   return f"☀️ El Niño Débil (ONI {oni_vivo:+.2f})"
                    if oni_vivo <= -2.0:  return f"🌊 Súper La Niña (ONI {oni_vivo:+.2f})"
                    if oni_vivo <= -1.5:  return f"🌧️ La Niña Fuerte (ONI {oni_vivo:+.2f})"
                    if oni_vivo <= -1.0:  return f"🌧️ La Niña Moderada (ONI {oni_vivo:+.2f})"
                    if oni_vivo <= -0.5:  return f"🌧️ La Niña Débil (ONI {oni_vivo:+.2f})"
                    return f"⚖️ Neutro (ONI {oni_vivo:+.2f})"
            return enso_historico.get(anio_int, "⚖️ Neutro / Histórico")

        # 🧭 BUSCADOR INTELIGENTE DE LA CAPA DEL TERRITORIO SELECCIONADO (Municipio, Cuenca, Región, CAR)
        def obtener_poligono_territorio():
            candidatos = [
                'gdf_territorio', 'gdf_zona', 'gdf_poly', 'gdf_limite', 'gdf_limites',
                'gdf_municipio', 'gdf_cuenca', 'gdf_region', 'gdf_car', 'gdf_context',
                'gdf_mask', 'gdf_seleccion', 'poligono_seleccionado', 'zona_estudio', 'gdf_bound'
            ]
            for nombre in candidatos:
                obj = st.session_state.get(nombre)
                if obj is None:
                    obj = globals().get(nombre)
                if isinstance(obj, (gpd.GeoDataFrame, gpd.GeoSeries)) and not obj.empty:
                    tipos = set(obj.geometry.geom_type.dropna().unique())
                    if any('Polygon' in t for t in tipos):
                        gdf_p = gpd.GeoDataFrame(geometry=obj.geometry, crs=obj.crs)
                        if gdf_p.crs is not None and gdf_p.crs.to_epsg() != 4326:
                            gdf_p = gdf_p.to_crs(epsg=4326)
                        return gdf_p

            for fuente in [st.session_state, globals()]:
                for k, v in list(fuente.items()):
                    if k == 'gdf_filtered':
                        continue
                    try:
                        if isinstance(v, (gpd.GeoDataFrame, gpd.GeoSeries)) and not v.empty:
                            tipos = set(v.geometry.geom_type.dropna().unique())
                            if any('Polygon' in t for t in tipos) and len(v) <= 30:
                                gdf_p = gpd.GeoDataFrame(geometry=v.geometry, crs=v.crs)
                                if gdf_p.crs is not None and gdf_p.crs.to_epsg() != 4326:
                                    gdf_p = gdf_p.to_crs(epsg=4326)
                                return gdf_p
                    except Exception:
                        continue
            return None
        
        st.markdown("---")
        
        ids_validos = tuple(gdf_filtered['id_estacion'].unique())
        
        if len(ids_validos) > 3:
            try:
                from modules.db_manager import get_engine
                from sqlalchemy import text
                import pandas as pd
                
                engine = get_engine()
                ids_sql = str(ids_validos) if len(ids_validos) > 1 else f"('{ids_validos[0]}')"
                
                # Función maestra para cargar datos (CON FILTRO SIN CEROS, ANTI-DUPLICADOS Y CONTROL DE ANOMALÍAS)
                def cargar_datos_isoyetas(anio):
                    # Agrupamos con AVG(p.valor) por (id_estacion, fecha) para evitar sumas duplicadas/triplicadas
                    # y filtramos p.valor > 0 para descartar falsos ceros mensuales (como Jardín Botánico 27015270 en 2020)
                    q_raw = text(f"""
                        SELECT p.id_estacion,
                               MAX(e.nombre) as nombre,
                               p.fecha,
                               AVG(p.valor) as valor,
                               MAX(e.latitud) as latitud,
                               MAX(e.longitud) as longitud
                        FROM precipitacion p
                        JOIN estaciones e ON p.id_estacion = e.id_estacion
                        WHERE extract(year from p.fecha) = :y
                          AND e.id_estacion IN {ids_sql}
                          AND p.valor > 0
                          AND p.valor <= 900
                        GROUP BY p.id_estacion, p.fecha
                    """)
                    df_raw = pd.read_sql(q_raw, engine, params={"y": anio})
                    if df_raw.empty:
                        return pd.DataFrame(columns=['id_estacion', 'nombre', 'lat', 'lon', 'valor'])
                    
                    df_raw['fecha'] = pd.to_datetime(df_raw['fecha']).dt.to_period('M').dt.to_timestamp()
                    cat_nombres = df_raw[['id_estacion', 'nombre', 'latitud', 'longitud']].drop_duplicates(subset=['id_estacion']).rename(
                        columns={'latitud': 'lat', 'longitud': 'lon'}
                    )
                    
                    if estado_aleph:
                        from modules.data_clinic import sanar_matriz_espacial
                        df_curado = sanar_matriz_espacial(
                            df_raw, gdf_filtered, col_fecha='fecha', col_valor='valor', col_id='id_estacion', mostrar_alerta=False
                        )
                        df_final = df_curado.groupby('id_estacion', as_index=False)['valor'].sum()
                        df_final = pd.merge(df_final, cat_nombres, on='id_estacion', how='left')
                    else:
                        meses_en_anio = df_raw['fecha'].nunique()
                        min_meses = max(1, int(np.ceil(meses_en_anio * 0.8)))
                        
                        resumen = df_raw.groupby('id_estacion').agg(
                            valor=('valor', 'sum'),
                            n_meses=('fecha', 'nunique')
                        ).reset_index()
                        
                        resumen = resumen[resumen['n_meses'] >= min_meses].drop(columns=['n_meses'])
                        df_final = pd.merge(resumen, cat_nombres, on='id_estacion', how='left')
                    
                    df_final = df_final.dropna(subset=['lat', 'lon', 'valor'])
                    # Cortafuegos anual: elimina estaciones con suma anual <= 100 mm o picos corruptos (> 5500 mm)
                    df_final = df_final[(df_final['valor'] > 100.0) & (df_final['valor'] <= 5500.0)].copy()
                    return df_final.reset_index(drop=True)

                # --- 2. PANELES DE CONTROL DUALES ---
                rango_anios = list(range(int(year_range[1]), int(year_range[0])-1, -1))
                col_map1, col_map2 = st.columns(2)
                
                with col_map1:
                    ph_titulo_a = st.empty()
                    ph_caja_a = st.empty()
                    c1a, c1b = st.columns(2)
                    year_1 = c1a.selectbox("Año A:", rango_anios, key="y1")
                    metodo_1 = c1b.selectbox("Método A:", ["rbf", "kriging", "idw", "spline", "trend"], format_func=lambda x: x.upper(), key="m1")
                    
                with col_map2:
                    ph_titulo_b = st.empty()
                    ph_caja_b = st.empty()
                    c2a, c2b = st.columns(2)
                    idx_y2 = 1 if len(rango_anios) > 1 else 0
                    year_2 = c2a.selectbox("Año B:", rango_anios, index=idx_y2, key="y2")
                    metodo_2 = c2b.selectbox("Método B:", ["kriging", "rbf", "idw", "spline", "trend"], format_func=lambda x: x.upper(), key="m2")

                df_iso1 = cargar_datos_isoyetas(year_1)
                df_iso2 = cargar_datos_isoyetas(year_2)

                enso_1 = obtener_etiqueta_enso(year_1)
                enso_2 = obtener_etiqueta_enso(year_2)
                n_est_1 = len(df_iso1)
                n_est_2 = len(df_iso2)
                prom_1 = f"{df_iso1['valor'].mean():.0f} mm" if n_est_1 > 0 else "Sin datos"
                prom_2 = f"{df_iso2['valor'].mean():.0f} mm" if n_est_2 > 0 else "Sin datos"

                ph_titulo_a.subheader(f"Mapa A ({enso_1} | {n_est_1} estaciones)")
                ph_caja_a.info(f"📌 **Año {year_1} ({enso_1})** — **{n_est_1}** estaciones válidas (sin ceros) | Promedio: **{prom_1}**")

                ph_titulo_b.subheader(f"Mapa B ({enso_2} | {n_est_2} estaciones)")
                ph_caja_b.info(f"📌 **Año {year_2} ({enso_2})** — **{n_est_2}** estaciones válidas (sin ceros) | Promedio: **{prom_2}**")

                def calcular_kriging_ordinario(lons, lats, vals, gx, gy):
                    coords = np.column_stack([lons, lats])
                    _, unique_idx = np.unique(np.round(coords, 5), axis=0, return_index=True)
                    unique_idx = np.sort(unique_idx)
                    x, y, v = lons[unique_idx], lats[unique_idx], vals[unique_idx]
                    n = len(v)
                    if n < 3 or np.std(v) < 1e-6:
                        return np.full_like(gx, np.mean(v))
                        
                    dist_mat = np.sqrt((x[:, None] - x[None, :])**2 + (y[:, None] - y[None, :])**2)
                    rango = max(float(np.percentile(dist_mat, 65)), 1e-4)
                    sill = max(float(np.var(v)), 1.0)
                    nugget = 0.05 * sill
                    
                    def variograma(h):
                        return np.where(h == 0, 0.0, nugget + sill * (1.0 - np.exp(-h / (rango / 2.5))))
                        
                    K = np.zeros((n + 1, n + 1))
                    K[:n, :n] = variograma(dist_mat) + np.eye(n) * (1e-5 * sill)
                    K[:n, n] = 1.0
                    K[n, :n] = 1.0
                    
                    gx_flat, gy_flat = gx.ravel(), gy.ravel()
                    dist_grid = np.sqrt((gx_flat[:, None] - x[None, :])**2 + (gy_flat[:, None] - y[None, :])**2)
                    rhs = np.ones((len(gx_flat), n + 1))
                    rhs[:, :n] = variograma(dist_grid)
                    
                    pesos = la.solve(K, rhs.T, assume_a='sym')
                    z_pred = np.dot(pesos[:n, :].T, v).reshape(gx.shape)
                    return np.clip(z_pred, max(0.0, float(np.min(v)) * 0.85), float(np.max(v)) * 1.10)

                def renderizar_barra_leyenda_html(vmin, vmax, cmap_name, metodo_str, anio_str):
                    cmap_obj = plt.get_cmap(cmap_name)
                    hex_list = [mcolors.to_hex(cmap_obj(i)) for i in np.linspace(0, 1, 12)]
                    gradiente_css = ", ".join(hex_list)
                    ticks = np.linspace(vmin, vmax, 6)
                    spans_ticks = "".join([f"<span style='font-weight:700; color:#0f172a; font-size:12.5px;'>{t:.0f} mm</span>" for t in ticks])
                    return f"""
                    <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:8px 14px; margin-top:2px; margin-bottom:12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                        <div style="font-size:12px; font-weight:700; color:#1e293b; margin-bottom:5px; text-align:center;">
                            🎨 Escala de Precipitación Estimada ({anio_str} — {metodo_str.upper()})
                        </div>
                        <div style="height:15px; width:100%; background: linear-gradient(to right, {gradiente_css}); border-radius:4px; border:1px solid #64748b;"></div>
                        <div style="display:flex; justify-content:space-between; margin-top:5px;">
                            {spans_ticks}
                        </div>
                    </div>
                    """

                gdf_poligono_actual = obtener_poligono_territorio()

                def crear_mapa_folium(df_data, metodo, map_tag, vmin_fijo=None, vmax_fijo=None):
                    if df_data.empty or len(df_data) < 3:
                        return folium.Map(location=[6.25, -75.58], zoom_start=11), 0.0, 100.0, 0.0
                        
                    geometry = [Point(xy) for xy in zip(df_data['lon'], df_data['lat'])]
                    gdf_puntos = gpd.GeoDataFrame(df_data, geometry=geometry, crs="EPSG:4326")
                    
                    # Extensión de la malla: une el polígono del territorio con las estaciones filtradas
                    minx, miny, maxx, maxy = gdf_puntos.total_bounds
                    if gdf_poligono_actual is not None and not gdf_poligono_actual.empty:
                        px1, py1, px2, py2 = gdf_poligono_actual.total_bounds
                        minx, miny = min(minx, px1), min(miny, py1)
                        maxx, maxy = max(maxx, px2), max(maxy, py2)
                        
                    pad_x = max((maxx - minx) * 0.05, 0.01)
                    pad_y = max((maxy - miny) * 0.05, 0.01)
                    minx, maxx = minx - pad_x, maxx + pad_x
                    miny, maxy = miny - pad_y, maxy + pad_y
                    gx, gy = np.mgrid[minx:maxx:150j, miny:maxy:150j]
                    
                    lons = df_data['lon'].values.astype(float)
                    lats = df_data['lat'].values.astype(float)
                    vals = df_data['valor'].values.astype(float)
                    
                    if metodo == "kriging":
                        z = calcular_kriging_ordinario(lons, lats, vals, gx, gy)
                    elif metodo == "rbf":
                        from scipy.interpolate import Rbf
                        rbf = Rbf(lons, lats, vals, function='thin_plate', smooth=0.08)
                        z = np.clip(rbf(gx, gy), float(np.min(vals)) * 0.8, float(np.max(vals)) * 1.15)
                    elif metodo == "idw":
                        dist = np.sqrt((gx.ravel()[:, None] - lons[None, :])**2 + (gy.ravel()[:, None] - lats[None, :])**2)
                        dist = np.where(dist < 1e-9, 1e-9, dist)
                        w = 1.0 / (dist ** 2)
                        z = (np.sum(w * vals[None, :], axis=1) / np.sum(w, axis=1)).reshape(gx.shape)
                    else:
                        try:
                            z, _ = interpolador_maestro(gdf_puntos, 'valor', gx, gy, metodo=metodo)
                            if z is None or np.nanstd(z) < 1e-3:
                                z = calcular_kriging_ordinario(lons, lats, vals, gx, gy)
                        except Exception:
                            z = calcular_kriging_ordinario(lons, lats, vals, gx, gy)
                            
                    z = np.nan_to_num(z, nan=float(np.nanmean(vals)))
                    vmin, vmax = float(np.min(z)), float(np.max(z))
                    if abs(vmax - vmin) < 1e-2:
                        vmin, vmax = float(np.min(vals)), float(np.max(vals))
                        if abs(vmax - vmin) < 1e-2:
                            vmax = vmin + 10.0

                    if vmin_fijo is not None and vmax_fijo is not None:
                        vmin, vmax = vmin_fijo, vmax_fijo        
                    
                    # Precipitación media areal exacta dentro del polígono rojo
                    media_poligono = float(np.nanmean(z))
                    if gdf_poligono_actual is not None and not gdf_poligono_actual.empty:
                        try:
                            from shapely import contains_xy
                            geom_union = gdf_poligono_actual.geometry.unary_union
                            mask_poly = contains_xy(geom_union, gx, gy)
                            if np.any(mask_poly):
                                media_poligono = float(np.nanmean(z[mask_poly]))
                        except Exception:
                            pass

                    fig_m = plt.figure(figsize=(8, 8), dpi=180)
                    ax_m = fig_m.add_axes([0, 0, 1, 1])
                    ax_m.axis('off')
                    ax_m.set_xlim(minx, maxx)
                    ax_m.set_ylim(miny, maxy)
                    
                    niveles = np.linspace(vmin, vmax, 16)
                    ax_m.contourf(gx, gy, z, levels=niveles, cmap=cmap_mpl, alpha=suavidad, extend='both')
                    if mostrar_lineas:
                        import matplotlib.patheffects as pe
                        cs = ax_m.contour(
                            gx, gy, z,
                            levels=niveles,
                            colors='black',
                            linewidths=0.55,
                            alpha=0.80
                        )
                        etiquetas = ax_m.clabel(
                            cs,
                            levels=niveles,       # Etiqueta TODAS las isoyetas
                            inline=True,
                            inline_spacing=2,     # Permite etiquetar curvas más cerradas
                            fmt='%.0f',           # Más corto (la unidad mm ya está en la barra)
                            fontsize=5.2,         # Tamaño cartográfico fino al hacer zoom
                            colors='white'
                        )
                        for txt in etiquetas:
                            txt.set_fontweight('bold')
                            txt.set_path_effects([
                                pe.Stroke(linewidth=1.3, foreground='#0f172a', alpha=0.85),
                                pe.Normal()
                            ])
                    
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png', transparent=True)
                    plt.close(fig_m)
                    
                    encoded_img = base64.b64encode(buf.getvalue()).decode('utf-8')
                    img_url = 'data:image/png;base64,' + encoded_img
                    
                    m = folium.Map(
                        location=[(miny+maxy)/2, (minx+maxx)/2],
                        zoom_start=11,
                        tiles=None,
                        scrollWheelZoom=True
                    )
                    
                    folium.TileLayer('OpenStreetMap', name='Calles (OSM)', control=True).add_to(m)
                    folium.TileLayer('CartoDB positron', name='Base Clara', control=True).add_to(m)
                    folium.TileLayer(
                        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                        attr='Esri', name='Satélite', control=True
                    ).add_to(m)
                    
                    folium.raster_layers.ImageOverlay(
                        image=img_url,
                        bounds=[[miny, minx], [maxy, maxx]],
                        opacity=1.0,
                        name='Capa de Isoyetas'
                    ).add_to(m)
                    
                    # Capa del Territorio Seleccionado (Municipio, Cuenca, Región o CAR) reproyectada a EPSG:4326
                    if gdf_poligono_actual is not None and not gdf_poligono_actual.empty:
                        folium.GeoJson(
                            gdf_poligono_actual.to_json(),
                            name='Límite Territorial Seleccionado',
                            style_function=lambda x: {
                                'fillColor': 'transparent',
                                'color': '#ef4444',
                                'weight': 3.0,
                                'dashArray': '6, 6',
                                'opacity': 0.95
                            }
                        ).add_to(m)
                        
                    station_group = folium.FeatureGroup(name="Estaciones Meteorológicas")
                    for _, row in df_data.iterrows():
                        folium.CircleMarker(
                            location=[row['lat'], row['lon']],
                            radius=4.5, color='black', weight=1.2, fill_color='white', fill_opacity=1.0,
                            tooltip=f"<b>{row['nombre']}</b> ({row['id_estacion']})<br>Lluvia: {row['valor']:.1f} mm"
                        ).add_to(station_group)
                    station_group.add_to(m)
                    
                    sync_and_css = f"""
                    <style>
                        .legend {{
                            background-color: rgba(255, 255, 255, 0.94) !important;
                            padding: 6px 10px !important;
                            border-radius: 6px !important;
                            border: 1px solid #334155 !important;
                            box-shadow: 0 2px 6px rgba(0,0,0,0.35) !important;
                            font-weight: 700 !important;
                            color: #0f172a !important;
                        }}
                        .legend svg text {{
                            fill: #0f172a !important;
                            font-weight: 700 !important;
                            font-size: 11px !important;
                        }}
                    </style>
                    <script>
                    (function() {{
                        var mapTag = "{map_tag}";
                        var isSyncing = false;
                        var channel = ("BroadcastChannel" in window) ? new BroadcastChannel("sihcli_isoyetas_sync") : null;

                        function findLeafletMap() {{
                            for (var k in window) {{
                                if (k.startsWith("map_") && window[k] && typeof window[k].getCenter === "function") {{
                                    return window[k];
                                }}
                            }}
                            return null;
                        }}

                        function setupSync() {{
                            var myMap = findLeafletMap();
                            if (!myMap) {{
                                setTimeout(setupSync, 200);
                                return;
                            }}

                            function broadcastView() {{
                                if (isSyncing || !channel) return;
                                var c = myMap.getCenter();
                                var z = myMap.getZoom();
                                channel.postMessage({{
                                    source: mapTag,
                                    lat: c.lat,
                                    lng: c.lng,
                                    zoom: z
                                }});
                            }}

                            myMap.on("moveend", broadcastView);
                            myMap.on("zoomend", broadcastView);

                            if (channel) {{
                                channel.onmessage = function(event) {{
                                    var data = event.data;
                                    if (data && data.source !== mapTag) {{
                                        isSyncing = true;
                                        myMap.setView([data.lat, data.lng], data.zoom, {{ animate: false }});
                                        setTimeout(function() {{ isSyncing = false; }}, 150);
                                    }}
                                }};
                            }}
                        }}
                        setupSync();
                    }})();
                    </script>
                    """
                    m.get_root().html.add_child(folium.Element(sync_and_css))
                    
                    folium.LayerControl().add_to(m)
                    return m, vmin, vmax, media_poligono

                vmin_glob, vmax_glob = None, None
                if unificar_escala and not df_iso1.empty and not df_iso2.empty:
                    vmin_glob = float(min(df_iso1['valor'].min(), df_iso2['valor'].min()))
                    vmax_glob = float(max(df_iso1['valor'].max(), df_iso2['valor'].max()))
                    if abs(vmax_glob - vmin_glob) < 1e-2:
                        vmax_glob = vmin_glob + 10.0

                with col_map1:
                    m1, vmin1, vmax1, media_poly1 = crear_mapa_folium(df_iso1, metodo_1, "MAPA_A", vmin_glob, vmax_glob)
                    ph_caja_a.info(
                        f"📌 **Año {year_1} ({enso_1})** — **{n_est_1}** estaciones | "
                        f"Red: **{prom_1}** | 🎯 Polígono: **{media_poly1:,.0f} mm**"
                    )
                    st_folium(m1, use_container_width=True, height=580, returned_objects=[], key="fol_m1")
                    st.markdown(renderizar_barra_leyenda_html(vmin1, vmax1, cmap_mpl, metodo_1, year_1), unsafe_allow_html=True)
                
                with col_map2:
                    m2, vmin2, vmax2, media_poly2 = crear_mapa_folium(df_iso2, metodo_2, "MAPA_B", vmin_glob, vmax_glob)
                    ph_caja_b.info(
                        f"📌 **Año {year_2} ({enso_2})** — **{n_est_2}** estaciones | "
                        f"Red: **{prom_2}** | 🎯 Polígono: **{media_poly2:,.0f} mm**"
                    )
                    st_folium(m2, use_container_width=True, height=580, returned_objects=[], key="fol_m2")
                    st.markdown(renderizar_barra_leyenda_html(vmin2, vmax2, cmap_mpl, metodo_2, year_2), unsafe_allow_html=True)

                # --- 3. ZONA DE DESCARGAS ---
                st.markdown("### 📥 Centro de Exportación Cartográfica")
                c_d1, c_d2 = st.columns(2)
                with c_d1:
                    csv_data1 = df_iso1.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button(f"📄 CSV Estaciones {year_1}", data=csv_data1, file_name=f"estaciones_A_{year_1}.csv", mime="text/csv", use_container_width=True)
                with c_d2:
                    csv_data2 = df_iso2.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button(f"📄 CSV Estaciones {year_2}", data=csv_data2, file_name=f"estaciones_B_{year_2}.csv", mime="text/csv", use_container_width=True)
                
                # --- 4. FICHA TÉCNICA HISTÓRICA ---
                st.markdown("---")
                st.subheader("📊 Ficha Técnica Estacional (Métricas Históricas)")
                
                with st.spinner("Calculando estadísticas históricas integrales..."):
                    q_stats = text(f"""
                        SELECT id_estacion, extract(year from fecha) as anio, extract(month from fecha) as mes, valor 
                        FROM precipitacion WHERE id_estacion IN {ids_sql}
                    """)
                    df_all = pd.read_sql(q_stats, engine)
                    
                    if not df_all.empty:
                        stats = []
                        for est in ids_validos:
                            df_est = df_all[df_all['id_estacion'] == est]
                            if df_est.empty: continue
                            
                            nombre_est = gdf_filtered[gdf_filtered['id_estacion'] == est]['nombre'].values[0]
                            anios_disp = df_est['anio'].nunique()
                            
                            prom_mes = df_est['valor'].mean()
                            std_mes = df_est['valor'].std()
                            mes_max = df_est.loc[df_est['valor'].idxmax()]
                            mes_min = df_est.loc[df_est['valor'].idxmin()]
                            
                            df_anios = df_est.groupby('anio')['valor'].sum().reset_index()
                            prom_anual = df_anios['valor'].mean()
                            anio_max = df_anios.loc[df_anios['valor'].idxmax()]
                            anio_min = df_anios.loc[df_anios['valor'].idxmin()]
                            
                            stats.append({
                                "Estación": nombre_est, "Años Hist.": anios_disp, "Prom. Anual": round(prom_anual, 1),
                                "Año + Lluvioso": f"{anio_max['valor']:.1f} ({int(anio_max['anio'])})",
                                "Año - Lluvioso": f"{anio_min['valor']:.1f} ({int(anio_min['anio'])})",
                                "Prom. Mensual": round(prom_mes, 1), "Desv. Est.": round(std_mes, 1),
                                "Mes + Lluvioso": f"{mes_max['valor']:.1f} ({int(mes_max['mes'])}/{int(mes_max['anio'])})",
                                "Mes - Lluvioso": f"{mes_min['valor']:.1f} ({int(mes_min['mes'])}/{int(mes_min['anio'])})"
                            })
                        st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)
                        
            except Exception as e: 
                st.error(f"Error en el Motor del Laboratorio: {e}")
        else: 
            st.warning("Se requieren mín. 3 estaciones espaciales para habilitar la malla geoestadística.")

    # --- REPORTE INTEGRADO (ACTUALIZADO) ---
    elif selected_module == "📄 Reporte":
        st.header("Generación de Informe")
        
        # 1. IMPORTAR EL NUEVO MOTOR
        from modules import reporter
        
        # 2. CAPTURAR EL CAPÍTULO ACTUAL
        fig_actual = st.session_state.get('fig_clima_principal') 
        capitulo = {
            'title': 'Análisis Hidroclimático',
            'text': f'Análisis realizado con {len(stations_for_analysis)} estaciones. Periodo: {year_range}.',
            'fig': fig_actual
        }
        
        # 3. GUARDAR EN EL ESTADO GLOBAL
        if 'pdf_chapters' not in st.session_state:
            st.session_state.pdf_chapters = []
        if capitulo not in st.session_state.pdf_chapters:
            st.session_state.pdf_chapters.append(capitulo)
            st.success("✅ Capítulo de Clima capturado para el reporte final.")
        
        # 4. GENERAR PDF CONSOLIDADO
        st.info("Este reporte consolidará todo lo que hayas visitado en otras pestañas.")
        if st.button("📥 Generar PDF Consolidado de SIHCLI"):
            # AQUÍ ESTÁ LA CLAVE: Llamamos al nombre correcto de la función
            pdf_data = reporter.generate_consolidated_pdf(st.session_state.pdf_chapters)
            st.download_button(
                "Descargar PDF Final", 
                pdf_data, 
                "Reporte_Sihcli_Final.pdf", 
                "application/pdf"
            )
    
    # ==============================================================================
    # ⚙️ BÓVEDA DE ADMINISTRADOR: FORJA DE LA MATRIZ MAESTRA UNIFICADA (HIDRO + SUBT)
    # ==============================================================================
    st.markdown("---")
    with st.expander("⚙️ Área Restringida: Motor de Generación de Matriz Hidrológica", expanded=False):
        st.subheader("Matriz Hidrológica y Subterránea Maestra (Recálculo Global)")
        
        admin_pwd = st.text_input("🔑 Ingrese clave de administrador para desbloquear el motor:", type="password", key="admin_pwd_forja")
        
        if admin_pwd == "AdminPoter":
            st.success("🔓 Acceso Concedido. Protocolos de forja desbloqueados.")
            
            st.markdown("""
            <div style="border-left: 5px solid #f39c12; padding: 15px; background-color: rgba(243, 156, 18, 0.1); border-radius: 5px; margin-bottom: 15px;">
                <h4 style="color: #d35400; margin-top: 0;">⚠️ Sincronización Física Total (Superficial + Subterránea)</h4>
                <b style="font-size: 0.95em;">Esta Matriz Maestra alimenta en milisegundos a Aguas Subterráneas, Calidad y Vertimientos, Toma de Decisiones y Simulador Integral con una única verdad física.</b>
            </div>
            """, unsafe_allow_html=True)

            from modules.db_manager import get_engine
            engine = get_engine()

            if st.button("⚡ Forjar Matriz Multiescala Definitiva", key="btn_gen_rep_multi", type="primary"):
                try:
                    import numpy as np
                    import geopandas as gpd
                    from sqlalchemy import text
                    import pandas as pd
                    import unicodedata, re
                    
                    def limpiar_llave_estandar(txt):
                        t = str(txt).split("(")[0].replace("- NSS -", "").replace("- NSS", "").strip()
                        t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode('utf-8').upper()
                        t = re.sub(r'[^A-Z0-9]', '_', t)
                        return re.sub(r'_+', '_', t).strip('_')

                    prog_nivel = st.progress(0, text="Iniciando motores espaciales...")

                    # 1. Cargamos el clima global priorizando la serie limpia y filtrada del modelo
                    with st.spinner("📡 Cargando red de Estaciones y Perfiles Mensuales Depurados..."):
                        q_est = text("SELECT id_estacion, nombre, altitud, ST_SetSRID(ST_MakePoint(CAST(longitud AS FLOAT), CAST(latitud AS FLOAT)), 4326) as geometry FROM estaciones WHERE latitud IS NOT NULL")
                        gdf_est = cargar_capa_espacial_cache(q_est, geom_col="geometry").to_crs("EPSG:3116")
                        gdf_est['id_estacion'] = gdf_est['id_estacion'].astype(str)
                        
                        # Calculamos la lluvia anual real sumando por año (min_count=10) como en el Motor Distribuido
                        q_anual_real = text("""
                            SELECT id_estacion, anio, SUM(valor) as ppt_anual
                            FROM (
                                SELECT CAST(id_estacion AS TEXT) as id_estacion, 
                                       EXTRACT(year FROM fecha) as anio, 
                                       EXTRACT(month FROM fecha) as mes, 
                                       AVG(valor) as valor
                                FROM precipitacion
                                WHERE valor > 0
                                GROUP BY CAST(id_estacion AS TEXT), EXTRACT(year FROM fecha), EXTRACT(month FROM fecha)
                            ) sub
                            GROUP BY id_estacion, anio
                            HAVING COUNT(mes) >= 10
                        """)
                        df_anual_est = pd.read_sql(q_anual_real, engine)
                        
                        q_meses = text("""
                            SELECT CAST(id_estacion AS TEXT) as id_estacion, EXTRACT(month FROM fecha) as mes, AVG(valor) as ppt_mes
                            FROM precipitacion 
                            WHERE valor > 0
                            GROUP BY CAST(id_estacion AS TEXT), EXTRACT(month FROM fecha)
                        """)
                        df_rain_mes = pd.read_sql(q_meses, engine)
                        
                        if not df_anual_est.empty:
                            df_rain_anual = df_anual_est.groupby('id_estacion')['ppt_anual'].mean().reset_index(name='ppt')
                        elif not df_rain_mes.empty:
                            df_rain_anual = df_rain_mes.groupby('id_estacion')['ppt_mes'].sum().reset_index(name='ppt')
                        else:
                            df_rain_anual = pd.DataFrame(columns=['id_estacion', 'ppt'])

                    res_multiescala = []

                    def procesar_capa_espacial(gdf_base, dicc_niveles, offset_progreso, total_pasos):
                        gdf_base['geometry'] = gdf_base.geometry.make_valid()
                        gdf_base = gdf_base[gdf_base.geometry.notnull()]
                        
                        paso_actual = offset_progreso
                        for nombre_nivel, col_bd in dicc_niveles.items():
                            if col_bd not in gdf_base.columns: continue
                            
                            prog_nivel.progress(min(0.99, paso_actual / total_pasos), text=f"Calculando Física Hidrológica para: {nombre_nivel}")
                            paso_actual += 1
                            
                            gdf_nivel = gdf_base.dissolve(by=col_bd).reset_index()
                            
                            for i, row in gdf_nivel.iterrows():
                                nom_territorio = str(row.get(col_bd, "Desconocido")).strip()
                                if nom_territorio in ["", "None", "nan", "Cuenca Sin Nombre", "Sin Datos"]: continue
                                
                                area_km2 = row.geometry.area / 1e6
                                if area_km2 <= 0: area_km2 = 1.0
                                
                                buffer_seguro = float(st.session_state.get("buffer_global_km", 25.0))
                                buf = row.geometry.buffer(buffer_seguro * 1000)
                                est_in = gdf_est[gdf_est.geometry.within(buf)]
                                
                                # Si una microcuenca pequeña no alcanza estaciones con el buffer, toma las 3 más cercanas
                                if est_in.empty and not gdf_est.empty:
                                    dists = gdf_est.geometry.distance(row.geometry.centroid)
                                    est_in = gdf_est.loc[dists.nsmallest(3).index]
                                
                                ppt_media, altitud_media = 2800.0, 1500.0
                                dict_meses = {m: 0.0 for m in range(1, 13)}
                                
                                if not est_in.empty:
                                    ids = est_in['id_estacion'].astype(str).tolist()
                                    vals_ppt = df_rain_anual[df_rain_anual['id_estacion'].isin(ids)]['ppt']
                                    if not vals_ppt.empty:
                                        ppt_media = float(vals_ppt.mean())
                                    
                                    df_local_mes = df_rain_mes[df_rain_mes['id_estacion'].isin(ids)]
                                    if not df_local_mes.empty:
                                        promedios = df_local_mes.groupby('mes')['ppt_mes'].mean().to_dict()
                                        suma_meses = sum(promedios.values())
                                        factor_ajuste_mes = (ppt_media / suma_meses) if suma_meses > 0 else 1.0
                                        for m in range(1, 13):
                                            dict_meses[m] = promedios.get(m, 0.0) * factor_ajuste_mes
                                            
                                    vals_alt = pd.to_numeric(est_in['altitud'], errors='coerce').dropna()
                                    if not vals_alt.empty:
                                        altitud_media = float(vals_alt.mean())
                                    
                                # Física Unificada (Turc Modificado + Partición Hidrogeológica Equivalente al Motor Distribuido)
                                temp_calc = max(5.0, 28.0 - (0.006 * altitud_media))
                                L = 300.0 + 25.0 * temp_calc + 0.05 * (temp_calc ** 3)
                                etr = ppt_media / np.sqrt(0.9 + (ppt_media / L) ** 2) if L > 0 else 0.0
                                agua_disponible = max(0.0, ppt_media - etr)
                                
                                # Coeficientes calibrados con el modelo distribuido (Ki ~ 0.546, Kg ~ 0.30 de infiltración -> Recarga ~ 16.4% de disp)
                                infiltracion_mm = agua_disponible * 0.546
                                recarga_mm = infiltracion_mm * 0.30
                                escorrentia_superficial = max(0.0, agua_disponible - infiltracion_mm)
                                
                                # Oferta Hídrica Total = Escorrentía Superficial + Recarga Subterránea (Flujo Base)
                                factor_q = (area_km2 * 1000.0) / 31536000.0
                                q_medio_total = (escorrentia_superficial + recarga_mm) * factor_q
                                q_base_min = recarga_mm * factor_q
                                q_max_pico = q_medio_total * 2.5
                                q_eco_25 = q_medio_total * 0.25
                                
                                fila_base = {
                                    "Jerarquia": nombre_nivel,
                                    "Territorio": nom_territorio,
                                    "Area_km2": round(area_km2, 2), 
                                    "Altitud_m": round(altitud_media, 0),
                                    "Temp_C": round(temp_calc, 1),
                                    "Lluvia_mm": round(ppt_media, 0), 
                                    "ETR_mm": round(etr, 0),
                                    "Infiltracion_mm": round(infiltracion_mm, 0),
                                    "Recarga_mm": round(recarga_mm, 0),
                                    "Escorrentia_mm": round(escorrentia_superficial, 0),
                                    "Caudal_Medio_m3s": round(q_medio_total, 3),
                                    "Caudal_Min_m3s": round(q_base_min, 3),
                                    "Caudal_Max_m3s": round(q_max_pico, 3),
                                    "Caudal_Eco_m3s": round(q_eco_25, 3),
                                    "P_01": round(dict_meses[1], 1), "P_02": round(dict_meses[2], 1),
                                    "P_03": round(dict_meses[3], 1), "P_04": round(dict_meses[4], 1),
                                    "P_05": round(dict_meses[5], 1), "P_06": round(dict_meses[6], 1),
                                    "P_07": round(dict_meses[7], 1), "P_08": round(dict_meses[8], 1),
                                    "P_09": round(dict_meses[9], 1), "P_10": round(dict_meses[10], 1),
                                    "P_11": round(dict_meses[11], 1), "P_12": round(dict_meses[12], 1)
                                }
                                res_multiescala.append(fila_base)
                        return paso_actual

                    # --- 🗺️ FASE 1: PROCESAR CUENCAS ---
                    with st.spinner("Calculando red hidrográfica..."):
                        gdf_cuencas = cargar_capa_espacial_cache("SELECT * FROM cuencas", geom_col="geometry").to_crs("EPSG:3116")

                        # Formato exacto del Selector del Aleph: "Nombre - (Codigo)"
                        mapa_columnas = {'nom_nss3': 'nss3', 'nom_nss2': 'nss2', 'nom_nss1': 'nss1', 'nom_szh': 'szh', 'nomzh': 'zh', 'nomah': 'ah'}
                        for col_nom, col_cod in mapa_columnas.items():
                            if col_nom in gdf_cuencas.columns and col_cod in gdf_cuencas.columns:
                                gdf_cuencas[col_nom] = gdf_cuencas.apply(
                                    lambda r: f"{str(r[col_nom]).strip()} - ({str(r[col_cod]).strip()})"
                                    if pd.notnull(r[col_nom]) and str(r[col_nom]).strip() != "" and pd.notnull(r[col_cod]) and str(r[col_cod]).strip() not in str(r[col_nom])
                                    else r[col_nom], axis=1
                                )
                        
                        if 'CorpoAmb' in gdf_cuencas.columns and 'depto_regi' in gdf_cuencas.columns:
                            gdf_cuencas['CorpoAmb'] = gdf_cuencas['CorpoAmb'].str.strip()
                            gdf_cuencas['depto_regi'] = gdf_cuencas['depto_regi'].str.strip()
                            mask_aburra = gdf_cuencas['depto_regi'].str.contains('Aburr', case=False, na=False)
                            gdf_cuencas.loc[mask_aburra, 'CorpoAmb'] = 'AMVA'

                        niveles_cuencas = {'NSS3': 'nom_nss3', 'NSS2': 'nom_nss2', 'NSS1': 'nom_nss1', 'SZH': 'nom_szh', 'ZH': 'nomzh', 'AH': 'nomah'}
                        pasos_totales = len(niveles_cuencas) + 5
                        paso_actual = procesar_capa_espacial(gdf_cuencas, niveles_cuencas, 0, pasos_totales)

                    # --- 🏛️ FASE 2: PROCESAR MUNICIPIOS, SUBREGIONES, CARs Y DEPARTAMENTO ---
                    with st.spinner("🏛️ Sincronizando Niveles Administrativos..."):
                        import io, requests
                        url_maestro = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/territorio_maestro.xlsx"
                        res_m = requests.get(url_maestro, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
                        df_maestro = pd.read_excel(io.BytesIO(res_m.content))
                        
                        def normalize_col_name(col):
                            return str(col).lower().strip().replace(' ', '_').replace('.', '').replace('-', '_')
                        
                        df_maestro.columns = [normalize_col_name(c) for c in df_maestro.columns]
                        col_mapping = {
                            'sub_region': 'subregion', 'subreg': 'subregion',
                            'departamento': 'depto_nom', 'depto': 'depto_nom',
                            'corporacion': 'car', 'corp': 'car',
                            'cod_dane': 'dp_mp', 'codigo_dane': 'dp_mp'
                        }
                        df_maestro.rename(columns=col_mapping, inplace=True)
                        
                        if 'dp_mp' in df_maestro.columns:
                            df_maestro['dp_mp'] = df_maestro['dp_mp'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(5)
                        
                        gdf_mun = cargar_capa_espacial_cache("SELECT * FROM municipios", geom_col="geometry").to_crs("EPSG:3116")
                        gdf_mun.columns = [normalize_col_name(c) for c in gdf_mun.columns]
                        
                        posibles_cols_id = ['id_municipio', 'mpio_cdpmp', 'dane', 'dp_mp', 'cod_dane', 'mpo_cdpmp']
                        col_id_mapa = next((c for c in posibles_cols_id if c in gdf_mun.columns), None)
                        
                        if col_id_mapa and 'dp_mp' in df_maestro.columns:
                            gdf_mun['dp_mp'] = gdf_mun[col_id_mapa].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(5)
                            merge_on = 'dp_mp'
                        else:
                            posibles_cols_nom = ['nombre_municipio', 'mpio_cnmbr', 'municipio']
                            col_nom_mapa = next((c for c in posibles_cols_nom if c in gdf_mun.columns), 'municipio')
                            col_nom_excel = next((c for c in posibles_cols_nom if c in df_maestro.columns), 'municipio')
                            gdf_mun['match_name'] = gdf_mun[col_nom_mapa].apply(limpiar_llave_estandar)
                            df_maestro['match_name'] = df_maestro[col_nom_excel].apply(limpiar_llave_estandar)
                            merge_on = 'match_name'

                        cols_requeridas = ['municipio', 'subregion', 'region', 'depto_nom', 'car']
                        cols_a_borrar = [c for c in cols_requeridas if c in gdf_mun.columns and c != merge_on]
                        if cols_a_borrar:
                            gdf_mun = gdf_mun.drop(columns=cols_a_borrar)

                        cols_a_traer = [merge_on] + [c for c in cols_requeridas if c in df_maestro.columns and c != merge_on]
                        gdf_mun = gdf_mun.merge(df_maestro[cols_a_traer], on=merge_on, how='left')
                        
                        for col in cols_requeridas:
                            if col not in gdf_mun.columns: gdf_mun[col] = 'Sin Datos'
                            else: gdf_mun[col] = gdf_mun[col].fillna('Sin Datos')

                        mask_aburra = gdf_mun['subregion'].str.contains('aburr', case=False, na=False)
                        gdf_mun.loc[mask_aburra, 'car'] = 'AMVA'
                        
                        posibles_cols_nom = ['nombre_municipio', 'mpio_cnmbr', 'municipio']
                        col_nom_mapa = next((c for c in posibles_cols_nom if c in gdf_mun.columns), 'municipio')
                        gdf_mun['municipio_clean'] = gdf_mun[col_nom_mapa]
                        
                        if 'dp_mp' in gdf_mun.columns:
                            gdf_mun = gdf_mun[gdf_mun['dp_mp'].str.startswith('05')].copy()
                        
                        niveles_admin = {
                            'MUNICIPAL': 'municipio_clean',
                            'REGION': 'subregion',
                            'DEPARTAMENTO': 'depto_nom',
                            'CAR': 'car'
                        }
                        paso_actual = procesar_capa_espacial(gdf_mun, niveles_admin, paso_actual, pasos_totales)
                    
                    prog_nivel.progress(1.0, text="¡Física territorial procesada al 100%!")
                    
                    # --- 💾 GUARDADO MAESTRO CON LLAVES UNIVERSALES SIN COLISIÓN (1,954 TERRITORIOS) ---
                    with st.spinner("Forjando Llaves Universales e Inyectando a PostgreSQL..."):
                        from modules.utils import normalizar_texto
                        df_matriz = pd.DataFrame(res_multiescala)
                        
                        def forjar_llave_hidro(row):
                            jerarquia = str(row.get('Jerarquia', '')).upper().strip()
                            if jerarquia in ["DEPARTAMENTAL", "DEPARTAMENTO"]: 
                                jerarquia = "DEPARTAMENTO"
                            elif jerarquia in ["REGIONAL", "REGION", "SUBREGION"]: 
                                jerarquia = "REGION"
                            elif jerarquia in ["MUNICIPAL", "MUNICIPIO"]: 
                                jerarquia = "MUNICIPIO"
                                
                            terr_raw = row.get('Territorio')
                            if terr_raw is None or str(terr_raw) == 'nan': 
                                return None
                                
                            # Usamos normalizar_texto original para preservar el texto después de (mi)/(md)
                            terr = str(normalizar_texto(str(terr_raw))).replace(" ", "_").upper()
                            terr = re.sub(r'_+', '_', terr).strip('_')
                            return f"{jerarquia}_{terr}_TOTAL"

                        df_matriz['LLAVE_UNIVERSAL'] = df_matriz.apply(forjar_llave_hidro, axis=1)
                        # Deduplicamos por (Jerarquia, Territorio) para no perder nunca cuencas homónimas (ej. dos Q. La Honda con distinto código IDEAM)
                        df_matriz = df_matriz.dropna(subset=['LLAVE_UNIVERSAL']).drop_duplicates(subset=['Jerarquia', 'Territorio'], keep='first')
                        
                        with engine.begin() as conn:
                            conn.execute(text('ALTER TABLE matriz_hidrologica_maestra ADD COLUMN IF NOT EXISTS "LLAVE_UNIVERSAL" TEXT;'))
                            conn.execute(text('ALTER TABLE matriz_hidrologica_maestra ADD COLUMN IF NOT EXISTS "Infiltracion_mm" FLOAT;'))
                            conn.execute(text('ALTER TABLE matriz_hidrologica_maestra ADD COLUMN IF NOT EXISTS "Caudal_Min_m3s" FLOAT;'))
                            conn.execute(text('ALTER TABLE matriz_hidrologica_maestra ADD COLUMN IF NOT EXISTS "Caudal_Max_m3s" FLOAT;'))
                            conn.execute(text('ALTER TABLE matriz_hidrologica_maestra ADD COLUMN IF NOT EXISTS "Caudal_Eco_m3s" FLOAT;'))
                            for i in range(1, 13):
                                conn.execute(text(f'ALTER TABLE matriz_hidrologica_maestra ADD COLUMN IF NOT EXISTS "P_{i:02d}" FLOAT;'))
                                
                            conn.execute(text("DELETE FROM matriz_hidrologica_maestra;"))
                            
                        df_matriz.to_sql("matriz_hidrologica_maestra", engine, if_exists='append', index=False, chunksize=300, method='multi')
                        st.cache_data.clear()
                        if 'df_matriz_hidrologica' in st.session_state:
                            del st.session_state['df_matriz_hidrologica']
                        st.success(f"✅ EL ALEPH HIDROLÓGICO Y SUBTERRÁNEO ESTÁ COMPLETO. {len(df_matriz)} territorios sincronizados en Supabase.")
                        
                        csv_data = df_matriz.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Descargar Matriz Recién Forjada (CSV)", csv_data, "Matriz_Hidro_Multiescala.csv", "text/csv")

                except Exception as e:
                    st.error(f"❌ Error crítico: {e}")

            st.markdown("---")
            if st.button("🔍 Preparar Descarga de Base Guardada"):
                try:
                    df_export = pd.read_sql("SELECT * FROM matriz_hidrologica_maestra", engine)
                    if not df_export.empty:
                        st.write(f"✅ Se encontraron {len(df_export)} territorios listos para exportar.")
                        csv_export = df_export.to_csv(index=False).encode('utf-8')
                        st.download_button(label="💾 Descargar Matriz Maestra (CSV)", data=csv_export, file_name="Matriz_Hidro_Maestra_SQL.csv", mime="text/csv")
                    else:
                        st.warning("La base de datos está vacía. Ejecuta la forja primero.")
                except Exception as e:
                    st.error(f"Error al conectar con la base: {e}")
                    
        elif admin_pwd != "":
            st.error("❌ Clave incorrecta. Acceso denegado.")

if __name__ == "__main__":
    main()