# modules/utils.py

import io
import os
import re
import unicodedata
import warnings
import pandas as pd
import numpy as np
import streamlit as st

# ==============================================================================
# 💉 SISTEMA INMUNOLÓGICO Y VARIABLES GLOBALES
# ==============================================================================
def inicializar_torrente_sanguineo():
    """
    Vacuna de memoria: Asegura que todas las arterias del Gemelo Digital 
    tengan un valor base (Fallback) para evitar colapsos por saltos de página.
    """
    diccionario_maestro = {
        'aleph_q_max_m3s': 0.0,
        'geomorfo_q_pico_racional': 0.0,
        'aleph_twi_umbral': 0.0,
        'ultima_zona_procesada': "",
        'gdf_rios': None, 'grid_obj': None, 'acc_obj': None, 'fdir_obj': None,
        'eco_lodo_total_m3': 0.0,
        'eco_lodo_colas_m3': 0.0,
        'eco_lodo_fondo_m3': 0.0,
        'eco_lodo_abrasivo_m3': 0.0,
        'eco_fosforo_kg': 0.0,
        'eco_sobrecosto_usd': 0.0,
        'activar_tormenta_sankey': False,
        'carga_dbo_total_ton': 0.0,
        'carga_dbo_mitigada_ton': 0.0,
        'ica_bovinos_calc_met': 0.0,
        'ica_porcinos_calc_met': 0.0,
        'pob_hum_calc_met': 0.0,
        'aleph_lugar': "Antioquia",
        'aleph_escala': "Departamental",
        'aleph_anio': 2024,
        'aleph_pob_total': 0.0,
        'ejecutar_aleph': False,
        'beta_unlocked': False
    }

    for llave, valor_seguro in diccionario_maestro.items():
        if llave not in st.session_state:
            st.session_state[llave] = valor_seguro

# ==============================================================================
# 🧽 FUNCIONES MAESTRAS DE LIMPIEZA (ORIGINALES INTACTAS)
# ==============================================================================

@st.cache_data(ttl=3600)
def cargar_diccionario_veredas():
    # ☁️ LECTURA DIRECTA DESDE TU BUCKET PÚBLICO EN SUPABASE
    url = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/homologacion_veredas.csv"
    try:
        return pd.read_csv(url)
    except:
        return pd.DataFrame()

def normalizar_texto_maestro(t, municipio_padre=""):
    """
    La aplanadora de texto definitiva para el SIHCLI-POTER.
    Maneja el 99% de las inconsistencias geográficas y ortográficas.
    """
    if not t or pd.isna(t): return ""
    t = str(t).lower().strip()

    # 💉 VACUNA VEREDAL
    if municipio_padre:
        id_busqueda = t.upper() + "_" + str(municipio_padre).upper().strip()
        id_busqueda = re.sub(r'[^A-Z0-9_]', '', id_busqueda)
        try:
            df_homologacion = cargar_diccionario_veredas()
            if not df_homologacion.empty and 'ID_TABLA' in df_homologacion.columns:
                match = df_homologacion[df_homologacion['ID_TABLA'] == id_busqueda]
                if not match.empty:
                    id_curado = str(match.iloc[0]['ID_MAPA'])
                    return id_curado.split("_")[0].lower()
        except: pass

    # Limpiezas estructurales
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'\s*-\s*nss.*|\s*-\s*szh.*|\s*-\s*zh.*|\s*-\s*ah.*', '', t)
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')

    reemplazos_hidro = {
        r'\brio\b': 'r', r'\br\.\s*': 'r ',
        r'\bquebrada\b': 'q', r'\bqda\.?\s*': 'q ', r'\bq\.\s*': 'q ',
        r'\bcano\b': 'cn', r'\bc\.\s*': 'cn ',
        r'\barroyo\b': 'a', r'\ba\.\s*': 'a ',
        r'\bcienaga\b': 'cga', r'\bcga\.\s*': 'cga '
    }
    for patron, reemplazo in reemplazos_hidro.items():
        t = re.sub(patron, reemplazo, t)

    stop_words = [r'\bvereda\b', r'\bvda\.?\b', r'\bsector\b', r'\bcaserio\b', r'\bcentro poblado\b', r'\bcp\b', r'\bcorregimiento\b', r'\bcorreg\b', r'\bcge\b']
    for word in stop_words: 
        t = re.sub(word, '', t)

    rebeldes_mpio = {
        r'\bel carmen de viboral\b': 'carmen de viboral',
        r'\bsan vicente ferrer\b': 'san vicente',
        r'\bsan jose de la montana\b': 'san jose de la montana',
        r'\bdonmatias\b': 'don matias',
        r'\bsantafe de antioquia\b': 'santa fe de antioquia',
        r'\bel santuario\b': 'santuario',
        r'\bel penol\b': 'penol',
        r'\barea metropolitana( del valle de aburra)?\b': 'valle de aburra' 
    }
    for regex, reemplazo in rebeldes_mpio.items(): 
        t = re.sub(regex, reemplazo, t)

    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()

    diccionario_final = {
        "bogotadc": "bogota", "sanjosedecucuta": "cucuta", 
        "laguajira": "guajira", "valle": "valledelcauca",
        "r aures": "aures", "r buey": "buey"
    }
    
    t_sin_espacios = t.replace(" ", "")
    if t_sin_espacios in diccionario_final: 
        return diccionario_final[t_sin_espacios]

    return t

normalizar_texto = normalizar_texto_maestro # Alias

@st.cache_data
def standardize_numeric_column(series):
    if series.dtype == object:
        series = series.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(series, errors="coerce")

# ==============================================================================
# 🗝️ NUEVAS FUNCIONES MAESTRAS (LLAVES Y BÚSQUEDAS)
# ==============================================================================
import re
import unicodedata
import pandas as pd
import streamlit as st

# 🔥 LA FUNCIÓN QUE FALTABA PARA QUE EL BUSCADOR NO COLAPSE EN SILENCIO
def limpiar_texto_maestro(texto):
    """Limpia tildes, caracteres especiales y convierte a mayúsculas puras."""
    if pd.isna(texto): return ""
    t = str(texto).upper()
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9]', '', t).strip()

def generar_llave_universal(nivel, territorio, area="TOTAL"):
    """
    Generador único de llaves de titanio. Sincronizado con Excel y a prueba de guiones de la UI.
    """
    def purificar_acentos(texto):
        if pd.isna(texto): return ""
        t = str(texto).upper()
        return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn').strip()

    n_crudo = purificar_acentos(nivel)
    
    # 🔥 FIX: Limpiamos los selectores ruidosos de las Cuencas antes de forjar la llave
    t_crudo = str(territorio).split(" - (")[0]
    t_crudo = t_crudo.replace(" - NSS", "").replace("- NSS", "").replace(" NSS", "")
    t_crudo = t_crudo.replace(" - SZH", "").replace("- SZH", "").replace(" SZH", "")
    t_crudo = t_crudo.replace("R. Grande - Chico", "R Grande Chico") # Arreglo específico para R. Grande
    t_crudo = purificar_acentos(t_crudo.strip())

 
    if "DEPARTAMENTO" in n_crudo or "DEPARTAMENTAL" in n_crudo: n_base = "DEPARTAMENTAL"
    elif "MUNICIPIO" in n_crudo or "MUNICIPAL" in n_crudo: n_base = "MUNICIPIO"
    elif "REGION" in n_crudo or "SUBREGION" in n_crudo: n_base = "REGION"
    elif "CAR" in n_crudo or "AUTORIDA" in n_crudo: n_base = "CAR"
    elif "NSS3" in n_crudo: n_base = "NSS3"
    elif "NSS2" in n_crudo: n_base = "NSS2"
    elif "NSS1" in n_crudo: n_base = "NSS1"
    elif "SZH" in n_crudo: n_base = "SZH"
    elif "ZH" in n_crudo: n_base = "ZH"
    elif "AH" in n_crudo: n_base = "AH"
    else: n_base = "CUENCA" 

    if t_crudo == "VALLE DE ABURRA" and n_base == "CAR": t_crudo = "AMVA"
    
    t_base = re.sub(r'[^A-Z0-9]', '_', t_crudo)
    t_base = re.sub(r'_+', '_', t_base).strip('_') 
    a_base = purificar_acentos(area)
    
    return f"{n_base}_{t_base}_{a_base}"

@st.cache_data(ttl=3600)
def extraer_datos_matriz_sql(nombre_tabla, territorio_busqueda, nivel="", es_llave=False):
    """
    Lector inteligente centralizado. Prioriza la LLAVE_UNIVERSAL y exige coincidencia EXACTA del nombre.
    """
    try:
        from modules.db_manager import get_engine
        engine = get_engine()
        df = pd.read_sql(f"SELECT * FROM {nombre_tabla}", engine)
        if df.empty: return pd.DataFrame()

        # 1. Búsqueda por LLAVE UNIVERSAL (Prioridad Máxima)
        if es_llave or 'LLAVE_UNIVERSAL' in df.columns:
            llave_limpia = str(territorio_busqueda).upper().strip()
            df_filtrado = df[df['LLAVE_UNIVERSAL'] == llave_limpia]
            if not df_filtrado.empty: return df_filtrado

        # 2. Búsqueda Semántica ESTRICTA (Sin colisiones)
        t_crudo = str(territorio_busqueda)
        t_puro = t_crudo.split(" - (")[0].strip() 
        t_clean = limpiar_texto_maestro(t_puro)

        if 'Territorio' in df.columns:
            df['t_match'] = df['Territorio'].apply(limpiar_texto_maestro)
            
            # Escudo de Alias
            if t_clean == "AMVA": t_clean = "VALLEDEABURRA"
            elif t_clean == "VALLEDEABURRA": t_clean = "AMVA"
            
            # MATCH EXACTO (Evita que 'MEDELLIN' se cruce con 'DIRECTOS ABURRA ZU MEDELLIN')
            df_exact = df[df['t_match'] == t_clean]
            if not df_exact.empty:
                # Si hay varios, priorizar el nivel correcto si se envió
                if nivel and 'Nivel' in df_exact.columns:
                    n_clean = limpiar_texto_maestro(str(nivel))
                    mask = df_exact['Nivel'].apply(limpiar_texto_maestro).str.contains(n_clean[:4], na=False)
                    if mask.any(): 
                        return df_exact[mask]  # 🔥 FIX: Quitamos el .head(1) para traer todas las especies
                return df_exact

        return pd.DataFrame()
    except Exception as e:
        print(f"Error extrayendo de {nombre_tabla}: {e}")
        return pd.DataFrame()

def proyectar_modelo_sql(f, anio_obj):
    import pandas as pd
    import numpy as np

    def limpiar_num(val):
        if val is None or pd.isna(val) or val == "" or str(val).strip().lower() in ['none', 'nan', 'null']:
            return 0.0
        if isinstance(val, (int, float, np.number)):
            return float(val)
        s = str(val).strip().replace(',', '')
        if s.count('.') > 1:
            partes = s.rsplit('.', 1)
            s = partes[0].replace('.', '') + '.' + partes[1]
        try:
            return float(s)
        except Exception:
            return 0.0

    anio_base = limpiar_num(f.get('Año_Base', 1985))
    if anio_base <= 0:
        anio_base = 1985.0
    x_norm = float(anio_obj) - anio_base

    col_pob = next((c for c in f.keys() if str(c).lower() in ['pob_base', 'poblacion_base']), None)
    pob_base = limpiar_num(f.get(col_pob, 0.0)) if col_pob else 0.0

    mod = str(f.get('Modelo_Recomendado', 'Polinomial_3')).lower().strip()
    resultado = 0.0

    try:
        if 'logist' in mod or 'logíst' in mod:
            k = limpiar_num(f.get('Log_K', 0.0))
            a = limpiar_num(f.get('Log_a', 0.0))
            r = limpiar_num(f.get('Log_r', 0.0))
            if k > 0:
                resultado = k / (1.0 + a * np.exp(-r * x_norm))
        elif 'exp' in mod:
            ea = limpiar_num(f.get('Exp_a', 0.0))
            eb = limpiar_num(f.get('Exp_b', 0.0))
            if ea > 0:
                resultado = ea * np.exp(eb * x_norm)
        elif 'lin' in mod:
            resultado = limpiar_num(f.get('Lin_m', 0.0)) * x_norm + limpiar_num(f.get('Lin_b', 0.0))
        else:
            # Polinomial grado 3 (Estándar por defecto de la Matriz Maestra)
            resultado = (
                limpiar_num(f.get('Poly_A', 0.0)) * (x_norm ** 3) +
                limpiar_num(f.get('Poly_B', 0.0)) * (x_norm ** 2) +
                limpiar_num(f.get('Poly_C', 0.0)) * x_norm +
                limpiar_num(f.get('Poly_D', 0.0))
            )

        # Fallback seguro solo si el polinomio da negativo o explota (>25x la base)
        # Escudo Demográfico Realista: ningún territorio crece >3.2x entre 1985 y 2060 ni cae a negativo
        if resultado <= 0 or (pob_base > 0 and (resultado > pob_base * 3.2 or resultado < pob_base * 0.35)):
            k = limpiar_num(f.get('Log_K', 0.0))
            a = limpiar_num(f.get('Log_a', 0.0))
            r = limpiar_num(f.get('Log_r', 0.0))
            while pob_base > 0 and k > pob_base * 3.2: k /= 10.0
            while r > 0.10: r /= 10.0
            if k > 0 and a > 0:
                resultado = k / (1.0 + a * np.exp(-r * x_norm))
            if resultado <= 0 or (pob_base > 0 and resultado > pob_base * 3.2):
                resultado = pob_base * (1.0 + 0.008 * max(0.0, x_norm))

        return max(0.0, float(resultado))
    except Exception:
        return max(0.0, float(pob_base))

# ==============================================================================
# 🧠 CEREBRO CENTRAL: MEMORIA Y GEOPROCESOS
# ==============================================================================

@st.cache_data(ttl=3600)
def descargar_matriz_sql_cache(nombre_tabla):
    try:
        from modules.db_manager import get_engine
        engine = get_engine()
        return pd.read_sql(f"SELECT * FROM {nombre_tabla}", engine)
    except Exception as e: return pd.DataFrame()

def encender_gemelo_digital():
    try: inicializar_torrente_sanguineo()
    except Exception: pass
    
    if 'df_matriz_demografica' not in st.session_state or st.session_state['df_matriz_demografica'].empty:
        st.session_state['df_matriz_demografica'] = descargar_matriz_sql_cache("matriz_maestra_demografica")
        
    if 'df_matriz_pecuaria' not in st.session_state or st.session_state['df_matriz_pecuaria'].empty:
        st.session_state['df_matriz_pecuaria'] = descargar_matriz_sql_cache("matriz_maestra_pecuaria")

# DEPRECATED: Se mantiene solo por compatibilidad si alguna página antigua lo requiere.
# Se recomienda usar calcular_poblacion_al_vuelo() de demografia_tools.py
def obtener_metabolismo_exacto(nombre_seleccion, anio_destino=None):
    res = {'pob_urbana': 0.0, 'pob_rural': 0.0, 'pob_total': 0.0, 'bovinos': 0.0, 'porcinos': 0.0, 'aves': 0.0, 'status': "Obsoleto (Use demografia_tools)"}
    return res

def display_plotly_download_buttons(fig, file_prefix):
    import streamlit as st
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        html_bytes = fig.to_html(include_plotlyjs="cdn").encode('utf-8')
        st.download_button("Descargar HTML", html_bytes, f"{file_prefix}.html", "text/html")
    with col2:
        try:
            img_bytes = fig.to_image(format="png")
            st.download_button("Descargar PNG", img_bytes, f"{file_prefix}.png", "image/png")
        except: 
            st.info("💡 Para descarga PNG instala: `pip install kaleido`")


# 🚀 CIRUGÍA 5B: Eliminamos geopandas y reestructuramos el decorador de caché
import plotly.express as px
import pandas as pd
import streamlit as st

# Quitamos el hash_funcs de sqlalchemy para que la app no explote al iniciar
@st.cache_data(ttl=86400, show_spinner=False)
def cargar_capa_espacial_cache(query_sql, _arg2=None, geom_col="geometry", **kwargs):
    if isinstance(_arg2, str): geom_col = _arg2
    try:
        # ⚠️ Lazy Loading Múltiple: Solo cargamos esto si la función realmente se usa
        from sqlalchemy import text
        from modules.db_manager import get_engine
        import geopandas as gpd 
        
        engine_geo = get_engine() 
        with engine_geo.connect() as conn:
            conn.execute(text("SET statement_timeout = '600000';")) 
            sql_a_ejecutar = text(query_sql) if isinstance(query_sql, str) else query_sql
            return gpd.read_postgis(sql_a_ejecutar, conn, geom_col=geom_col)
    except ImportError:
        # Si falta geopandas o sqlalchemy (porque es el frontend), no estrellamos la app
        return None
    except Exception as e: 
        return None

# ==============================================================================
# 🗺️ RENDERIZADOR DE MINIMAPA RADAR (Contexto Espacial Inercial)
# ==============================================================================
def renderizar_radar_espacial(gdf_base, gdf_activo, titulo="Ubicación Relativa"):
    import plotly.express as px
    import streamlit as st
    import pandas as pd
    
    # 1. Asegurar proyección WGS84 para Mapbox
    if gdf_base is not None and not (isinstance(gdf_base, pd.DataFrame) and gdf_base.empty):
        try:
            if gdf_base.crs != "EPSG:4326": gdf_base = gdf_base.to_crs(epsg=4326)
            gdf_base['geometry'] = gdf_base['geometry'].simplify(0.01)
        except Exception:
            gdf_base = None
            
    if gdf_activo is not None and not (isinstance(gdf_activo, pd.DataFrame) and gdf_activo.empty):
        try:
            if gdf_activo.crs != "EPSG:4326": gdf_activo = gdf_activo.to_crs(epsg=4326)
            gdf_activo['geometry'] = gdf_activo['geometry'].simplify(0.005)
        except Exception:
            gdf_activo = None

    # 2. Construir la figura
    fig = None
    
    # Si tenemos base, la dibujamos de fondo
    if gdf_base is not None:
        fig = px.choropleth_mapbox(
            gdf_base, 
            geojson=gdf_base.geometry, 
            locations=gdf_base.index,
            color_discrete_sequence=["rgba(30, 41, 59, 0.4)"],
            mapbox_style="carto-darkmatter"
        )
        
    # Si tenemos el polígono activo, lo pintamos de cian
    if gdf_activo is not None:
        fig_activo = px.choropleth_mapbox(
            gdf_activo, 
            geojson=gdf_activo.geometry, 
            locations=gdf_activo.index,
            color_discrete_sequence=["#38bdf8"]
        )
        if fig is not None and len(fig.data) > 0:
            fig.add_trace(fig_activo.data[0])
        else:
            fig = fig_activo
            fig.update_layout(mapbox_style="carto-darkmatter")

    # Si por alguna razón ambos fallaron, lanzamos un mapa vacío oscuro
    if fig is None:
        fig = px.choropleth_mapbox(mapbox_style="carto-darkmatter")

    # 3. Centrar el mapa (Zoom inercial)
    centro_lat, centro_lon = 6.2, -75.5
    zoom_level = 5.5
    
    if gdf_activo is not None:
        bounds = gdf_activo.total_bounds
        centro_lon = (bounds[0] + bounds[2]) / 2
        centro_lat = (bounds[1] + bounds[3]) / 2
        diff_lon = bounds[2] - bounds[0]
        if diff_lon < 0.2: zoom_level = 9.0
        elif diff_lon < 0.5: zoom_level = 8.0
        elif diff_lon < 1.0: zoom_level = 6.5
        else: zoom_level = 5.2
    elif gdf_base is not None:
        bounds = gdf_base.total_bounds
        centro_lon = (bounds[0] + bounds[2]) / 2
        centro_lat = (bounds[1] + bounds[3]) / 2

    fig.update_layout(
        margin={"r":0,"t":25,"l":0,"b":0},
        mapbox=dict(center=dict(lat=centro_lat, lon=centro_lon), zoom=zoom_level),
        showlegend=False,
        height=220,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title=dict(text=titulo, font=dict(color="#94a3b8", size=12))
    )
    
    st.plotly_chart(fig, width="stretch", config={'staticPlot': True, 'displayModeBar': False})