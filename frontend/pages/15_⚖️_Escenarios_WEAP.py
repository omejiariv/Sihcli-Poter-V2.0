# pages/15_⚖️_Escenarios_WEAP.py

import sys
import os
import streamlit as st
import pandas as pd
from sqlalchemy import text

# 1. RUTA Y MÓDULOS
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from modules.db_manager import get_engine
from modules import selectors, escenarios_weap
from modules.utils import normalizar_texto

# 2. Configuración de página
st.set_page_config(page_title="SIHCLI | Escenarios WEAP", page_icon="⚖️", layout="wide")

# 3. Renderizar menú
selectors.renderizar_menu_navegacion("Escenarios WEAP")

# ==============================================================================
# 🧠 4. SELECTOR ESPACIAL Y CONEXIÓN ALEPH (Topología Estricta WEAP)
# ==============================================================================
st.sidebar.markdown("---")
try:
    ids_sel_dummy, nombre_zona_raw, altitud_ref, gdf_zona_dummy, nivel_jerarquico_raw = selectors.render_selector_espacial(modo_firma="weap")
except Exception as e:
    st.error(f"Error en selector: {e}")
    st.stop()

# 🚀 CONEXIÓN ALEPH
nombre_zona = st.session_state.get('aleph_lugar', nombre_zona_raw)
nivel_jerarquico = st.session_state.get('aleph_escala', nivel_jerarquico_raw)

if not nombre_zona or str(nombre_zona).strip() in ["", "None", "-- Seleccione --"]:
    st.info("👈 Seleccione un Territorio (Cuenca, Municipio o Región) en el menú lateral para iniciar.")
    st.stop()

if nivel_jerarquico == "Estaciones":
    st.error("🛑 **Escala Geográfica Incorrecta**")
    st.warning("El simulador WEAP requiere una unidad territorial que contenga población (como una **Cuenca** o un **Municipio**).")
    st.stop()

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

# 🚀 RESCATE ESTRUCTURAL: Usar el caché de memoria viva (Si existe)
gdf_zona = None
if 'aleph_poligono' in st.session_state and st.session_state['aleph_poligono'] is not None and not st.session_state['aleph_poligono'].empty:
    gdf_zona = st.session_state['aleph_poligono']

# 🪂 PARACAÍDAS CARTOGRÁFICO ESTRUCTURAL
if gdf_zona is None or gdf_zona.empty:
    with st.spinner("🪂 Sincronizando topología estricta de WEAP..."):
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
                gdf_tm = fetch_territorio_maestro() 
                
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
                st.sidebar.success("🪂 ¡Topología sincronizada para WEAP!")
            else:
                st.sidebar.error("⚠️ El polígono no existe en la matriz maestra.")
                
        except Exception as e:
            st.sidebar.error(f"Error de sincronización estructural: {e}")

st.sidebar.success(f"🔗 Conexión Aleph Activa: {nombre_zona}")

# ==============================================================================
# 🧠 5. NÚCLEO WEAP (Cruce Base de Datos - Inteligencia Activa)
# ==============================================================================
territorio_str = nombre_zona[0] if isinstance(nombre_zona, list) else nombre_zona

if territorio_str != "Territorio Global":
    try:
        from sqlalchemy import text
        from modules.db_manager import get_engine
        engine = get_engine() 
        nombre_puro = territorio_str.split(" - (")[0].strip() if " - (" in territorio_str else territorio_str.strip()
        
        import unicodedata
        def normalizar(texto):
            if not isinstance(texto, str): return ""
            return unicodedata.normalize('NFKD', texto.lower().strip()).encode('ascii', 'ignore').decode('utf-8')
        
        nombre_normalizado = normalizar(nombre_puro)
        
        # Diccionarios de mapeo para escalas agregadas
        M_SUB = {
            "valle de aburra": ["medellin", "bello", "itagui", "envigado", "sabaneta", "copacabana", "la estrella", "girardota", "caldas", "barbosa"],
            "amva": ["medellin", "bello", "itagui", "envigado", "sabaneta", "copacabana", "la estrella", "girardota", "caldas", "barbosa"],
            "bajo cauca": ["caucasia", "caceres", "el bagre", "nechi", "taraza", "zaragoza"],
            "oriente": ["abejorral", "alejandria", "argelia", "el carmen de viboral", "cocorna", "concepcion", "el peñol", "el retiro", "el santuario", "guarne", "guatape", "la ceja", "la union", "marinilla", "nariño", "rionegro", "san carlos", "san francisco", "san luis", "san rafael", "san vicente", "sonson", "granada"],
            "cornare": ["abejorral", "alejandria", "argelia", "el carmen de viboral", "cocorna", "concepcion", "el peñol", "el retiro", "el santuario", "guarne", "guatape", "la ceja", "la union", "marinilla", "nariño", "rionegro", "san carlos", "san francisco", "san luis", "san rafael", "san vicente", "sonson", "granada", "puerto nare", "puerto triunfo"]
        }

        with engine.connect() as conn:
            conn.execute(text("SET statement_timeout = '120000'"))
            
            # --- 1. CONEXIÓN DEMOGRÁFICA ---
            if "COLOMBIA" in nombre_normalizado.upper():
                # Regla de oro nacional: Proyección oficial DANE ~52.8M (Año base 2026)
                st.session_state['aleph_pob_total'] = 52828000.0
                st.sidebar.success("👥 Demografía Nacional (DANE) aplicada por defecto.")
            else:
                q_demo = text('''
                    SELECT "Pob_Base" 
                    FROM matriz_maestra_demografica 
                    WHERE LOWER(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("Territorio", 'Á', 'A'), 'É', 'E'), 'Í', 'I'), 'Ó', 'O'), 'Ú', 'U'), ' ', ''))) = REPLACE(:t_norm, ' ', '')
                    AND UPPER(TRIM("Area")) = 'TOTAL'
                    LIMIT 1
                ''')
                pob_real = conn.execute(q_demo, {"t_norm": nombre_normalizado}).scalar()
                
                if pob_real is not None:
                    st.session_state['aleph_pob_total'] = float(pob_real)
                else:

                    # FALLBACK INTELIGENTE
                    area_km2 = 0
                    if gdf_zona is not None and not gdf_zona.empty:
                        try: area_km2 = gdf_zona.to_crs(epsg=3116).area.sum() / 1_000_000
                        except: pass
                    st.session_state['aleph_pob_total'] = max((area_km2 * 35.0), 10000.0)

            # --- 2. OFERTA HÍDRICA (Lógica IDEAM - Nombre Completo) ---
            # 🚀 FIX: Usamos territorio_str (que tiene el código IDEAM completo) en lugar de nombre_puro
            q_h = text('SELECT "Caudal_Medio_m3s" FROM matriz_hidrologica_maestra WHERE LOWER(TRIM("Territorio")) = LOWER(TRIM(:t)) LIMIT 1')
            oferta_real = conn.execute(q_h, {"t": territorio_str}).scalar()
            
            if oferta_real is not None:
                st.session_state['aleph_oferta_m3s'] = float(oferta_real)
            else:
                # Fallback de búsqueda laxa en caso de discrepancias de espacios
                q_h_laxa = text('SELECT "Caudal_Medio_m3s" FROM matriz_hidrologica_maestra WHERE "Territorio" ILIKE :t LIMIT 1')
                oferta_laxa = conn.execute(q_h_laxa, {"t": f"%{nombre_puro}%"}).scalar()
                if oferta_laxa is not None:
                    st.session_state['aleph_oferta_m3s'] = float(oferta_laxa)

            # --- 3. EXTRACCIÓN RURH (Con Mapeo Regional) ---
            import pandas as pd
            df_rurh = pd.read_sql(text('SELECT * FROM matriz_presiones_rurh'), conn)
            
            rurh_total_m3s = 0.0
            if not df_rurh.empty:
                col_terr = next((c for c in df_rurh.columns if 'TERR' in c.upper()), 'Territorio')
                col_val = next((c for c in df_rurh.columns if 'RURH' in c.upper() or 'PRESION' in c.upper()), 'Presion_Total_RURH_m3s')
                
                df_rurh['terr_norm'] = df_rurh[col_terr].apply(normalizar)
                
                # Identificar si es una región/CAR con múltiples municipios
                mpios_a_sumar = M_SUB.get(nombre_normalizado, [nombre_normalizado])
                
                # Sumar el RURH de todos los municipios involucrados
                df_rurh_filtrado = df_rurh[df_rurh['terr_norm'].isin(mpios_a_sumar)]
                if not df_rurh_filtrado.empty:
                    rurh_total_m3s = float(df_rurh_filtrado[col_val].sum())
                else:
                    # Búsqueda laxa si falla la estricta
                    mask_laxa = df_rurh['terr_norm'].str.contains(nombre_normalizado.split()[0], na=False)
                    if mask_laxa.any():
                        rurh_total_m3s = float(df_rurh[mask_laxa][col_val].sum())
                        
            st.session_state['aleph_concesiones_m3s'] = rurh_total_m3s
            
    except Exception as e:
        st.error(f"Error en motor hidrosocial: {e}")

# Renderizado final del motor
escenarios_weap.renderizar_motor_escenarios_weap(nombre_zona, gdf_zona)