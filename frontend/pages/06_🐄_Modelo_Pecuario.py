# pages/06_🐄_Modelo_Pecuario.py

import os
import sys
import warnings
import re
import unicodedata

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.optimize import curve_fit

import streamlit as st

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Modelo Pecuario", page_icon="🐄", layout="wide")
warnings.filterwarnings('ignore')

try:
    from modules import selectors
    from modules.utils import cargar_capa_espacial_cache, encender_gemelo_digital, normalizar_texto
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules import selectors
    from modules.utils import cargar_capa_espacial_cache, encender_gemelo_digital, normalizar_texto

selectors.renderizar_menu_navegacion("Modelo Pecuario")
encender_gemelo_digital()

# ====================================================================
# 🧽 ESTADO GLOBAL Y LECTURA DEL ALEPH
# ====================================================================
if 'aleph_lugar' not in st.session_state:
    st.warning("👈 Selecciona un territorio en 'El Aleph' (Panel Lateral Izquierdo) para comenzar.")
    st.stop()

territorio_sel = st.session_state['aleph_lugar']
nivel_backend = st.session_state['aleph_escala']

st.title("🐄 Modelo Pecuario (Proyección Demográfica Animal)")
st.markdown("Proyecciones matemáticas de inventarios bovinos, porcinos y avícolas conectadas a la dinámica espacial de la cuenca.")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configuración del Modelo")
anio_destino = st.sidebar.slider("Horizonte de Proyección:", 2024, 2050, 2030)

# ====================================================================
# 🚀 AUTO-CARGA DE LA MATRIZ SQL
# ====================================================================
if 'df_matriz_pecuaria' not in st.session_state:
    with st.spinner("Conectando con el Cerebro Pecuario en Supabase..."):
        try:
            from modules.db_manager import get_engine
            engine_sql = get_engine()
            df_sql = pd.read_sql("SELECT * FROM matriz_maestra_pecuaria", engine_sql)
            if not df_sql.empty:
                st.session_state['df_matriz_pecuaria'] = df_sql
        except Exception as e:
            pass

@st.cache_data(ttl=3600)
def cargar_historico_pecuario():
    url = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/Censo_Pecuario_Historico_Cuencas.csv"
    return pd.read_csv(url)

df_pecuario = cargar_historico_pecuario()

# =====================================================================
# 🔬 PERFIL VISUAL Y SINCRONIZACIÓN AL ALEPH
# =====================================================================
if 'df_matriz_pecuaria' in st.session_state:
    df_mat = st.session_state['df_matriz_pecuaria']
    
    st.subheader(f"📊 Perfil Pecuario: {territorio_sel}")
    
    # 🚀 BÚSQUEDA INTELIGENTE CON LLAVE UNIVERSAL (Soluciona amnesia de El Peñol, Colombia y CARs)
    nombre_puro = territorio_sel.split(" - (")[0].strip() if " - (" in territorio_sel else territorio_sel.strip()
    
    try:
        terr_n = normalizar_texto(nombre_puro).upper()
    except:
        terr_n = re.sub(r'[^A-Z0-9]', '', unicodedata.normalize('NFD', str(nombre_puro).upper()).encode('ascii', 'ignore').decode('utf-8'))
        
    nivel_n = str(nivel_backend).upper().strip()
    if "NACION" in nivel_n: nivel_n = "NACIONAL"
    elif "DEPARTAMENTO" in nivel_n or "DEPARTAMENTAL" in nivel_n: nivel_n = "DEPARTAMENTAL"
    elif "MUNICIP" in nivel_n: nivel_n = "MUNICIPAL"
    elif "REGION" in nivel_n or "SUBREGION" in nivel_n: nivel_n = "REGIONAL"
    elif "CAR" in nivel_n or "AUTORIDAD" in nivel_n: nivel_n = "CAR"
    elif "CUENCA" in nivel_n or "NSS" in nivel_n or "SZH" in nivel_n or "ZH" in nivel_n or "AH" in nivel_n: nivel_n = "CUENCA"

    llave_busqueda = f"{nivel_n}_{terr_n}_TOTAL".upper().replace(" ", "_")

    # 1. Buscamos primero con la llave blindada
    if 'LLAVE_UNIVERSAL' in df_mat.columns:
        df_filtrado = df_mat[df_mat['LLAVE_UNIVERSAL'] == llave_busqueda]
    else:
        # Fallback de emergencia si la BD es muy vieja
        mask = df_mat['Territorio'].astype(str).str.upper().str.startswith(nombre_puro.upper())
        df_filtrado = df_mat[mask]
    
    if df_filtrado.empty:
        st.warning(f"⚠️ No hay modelos entrenados para **{territorio_sel}**. Despliega el 'Entrenador de Modelos' abajo para forjarlo. \n\n*(Llave matemática esperada: `{llave_busqueda}`)*")
    else:
        tabs = st.tabs(["🐄 Bovinos", "🐖 Porcinos", "🐔 Aves"])
        especies = ["Bovinos", "Porcinos", "Aves"]
        resultados_calculados = {}
        
        for tab, especie in zip(tabs, especies):
            with tab:
                fila_esp = df_filtrado[df_filtrado['Especie'] == especie]
                if fila_esp.empty:
                    st.info(f"No hay registros de {especie} en esta zona.")
                    resultados_calculados[especie] = 0.0
                    continue
                    
                fila_terr = fila_esp.iloc[0]
                mejor_modelo = fila_terr.get('Modelo_Recomendado', 'Logístico')
                
                x_offset = fila_terr.get('Año_Base', 2018)
                x_pred = np.arange(x_offset, anio_destino + 1)
                x_norm_pred = x_pred - x_offset
                
                y_ganador = np.zeros_like(x_pred, dtype=float)
                if mejor_modelo == 'Logístico' and fila_terr.get('Log_K', 0) > 0:
                    y_ganador = fila_terr['Log_K'] / (1 + fila_terr['Log_a'] * np.exp(-fila_terr['Log_r'] * x_norm_pred))
                elif mejor_modelo == 'Exponencial':
                    y_ganador = fila_terr['Exp_a'] * np.exp(fila_terr['Exp_b'] * x_norm_pred)
                elif mejor_modelo == 'Lineal':
                    y_ganador = fila_terr['Lin_m'] * x_norm_pred + fila_terr['Lin_b']
                elif 'Polinomial' in mejor_modelo:
                    y_ganador = fila_terr['Poly_A']*(x_norm_pred**3) + fila_terr['Poly_B']*(x_norm_pred**2) + fila_terr['Poly_C']*x_norm_pred + fila_terr['Poly_D']
                
                valor_futuro = max(0.0, float(y_ganador[-1]))
                resultados_calculados[especie] = valor_futuro
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=x_pred, y=y_ganador, mode='lines', name=f"Proyección {mejor_modelo}", line=dict(color='#27ae60', width=4)))
                
                fig.update_layout(
                    title=f"Evolución {especie} | Base: {x_offset} ➔ Destino: {anio_destino}", 
                    xaxis_title="Año", yaxis_title="Cabezas / Aves", hovermode="x unified", height=400,
                    margin=dict(l=20, r=20, t=50, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.success(f"📈 Proyección **{anio_destino}**: **{int(valor_futuro):,}** {especie.lower()}.")

        # ==============================================================================
        # 🧠 INYECCIÓN DIRECTA AL CEREBRO GLOBAL (Para Módulo de Calidad)
        # ==============================================================================
        st.session_state['ica_bovinos_calc_met'] = resultados_calculados.get('Bovinos', 0.0)
        st.session_state['ica_porcinos_calc_met'] = resultados_calculados.get('Porcinos', 0.0)
        st.session_state['ica_aves_calc_met'] = resultados_calculados.get('Aves', 0.0)
        st.session_state['aleph_lugar_pecuario'] = territorio_sel
        st.session_state['aleph_anio_pecuario'] = anio_destino

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("🐄 Carga Bovina", f"{int(resultados_calculados.get('Bovinos', 0)):,}", "Lista para Calidad del Agua")
        c2.metric("🐖 Carga Porcina", f"{int(resultados_calculados.get('Porcinos', 0)):,}", "Lista para Calidad del Agua")
        c3.metric("🐔 Carga Avícola", f"{int(resultados_calculados.get('Aves', 0)):,}", "Lista para Calidad del Agua")

# =====================================================================
# 🛠️ ENTRENADOR DE MODELOS PECUTARIOS (FORJA SQL COMPLETA)
# =====================================================================
st.markdown("---")
with st.expander("🛠️ Entrenador de Modelos Pecuarios (Forja SQL)", expanded=False):
    st.info("Utiliza esta herramienta para re-entrenar los modelos con la nueva 'Llave Universal' para todas las escalas, o si la BD está vacía.")
    
    if st.button("⚙️ Iniciar Forja Pecuaria Integral", type="primary"):
        texto_progreso = st.empty()
        barra_progreso = st.progress(0)
        
        try:
            import geopandas as gpd
            from sqlalchemy import text
            from rasterstats import zonal_stats
            import tempfile
            import urllib.request
            import gc
            from modules.db_manager import get_engine
            
            engine_geo = get_engine()

            # 1. DESCARGA Y CRUCE DASIMÉTRICO
            texto_progreso.info("📍 Fase 1/2: Descargando Raster de Usos del Suelo (2022)...")
            URL_RASTER = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/rasters/Cob25m_WGS84.tif"
            tmp_raster = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
            urllib.request.urlretrieve(URL_RASTER, tmp_raster.name)
            raster_path = tmp_raster.name

            texto_progreso.info("🗺️ Fase 1/2: Cruzando cartografía (Municipios y Cuencas)...")
            q_mun = "SELECT * FROM municipios WHERE geometry IS NOT NULL"
            gdf_mun = cargar_capa_espacial_cache(q_mun, geom_col="geometry")
            if gdf_mun is not None and not gdf_mun.empty: gdf_mun = gdf_mun.to_crs(epsg=4326)
            else: raise ValueError("La capa de municipios está vacía.")

            q_cue = """
                SELECT COALESCE(
                    CASE WHEN TRIM(nom_nss3) != '' THEN TRIM(nom_nss3) || ' - (' || TRIM(CAST(nss3 AS TEXT)) || ')' ELSE NULL END,
                    CASE WHEN TRIM(nom_nss2) != '' THEN TRIM(nom_nss2) || ' - (' || TRIM(CAST(nss2 AS TEXT)) || ')' ELSE NULL END,
                    CASE WHEN TRIM(nom_nss1) != '' THEN TRIM(nom_nss1) || ' - (' || TRIM(CAST(nss1 AS TEXT)) || ')' ELSE NULL END,
                    CASE WHEN TRIM(nom_szh) != '' THEN TRIM(nom_szh) || ' - (' || TRIM(CAST(szh AS TEXT)) || ')' ELSE NULL END,
                    CASE WHEN TRIM(nomzh) != '' THEN TRIM(nomzh) || ' - (' || TRIM(CAST(zh AS TEXT)) || ')' ELSE NULL END,
                    CASE WHEN TRIM(nomah) != '' THEN TRIM(nomah) || ' - (' || TRIM(CAST(ah AS TEXT)) || ')' ELSE NULL END,
                    'Cuenca Sin Nombre'
                ) AS subc_lbl, geometry
                FROM cuencas WHERE geometry IS NOT NULL
            """
            gdf_cue = cargar_capa_espacial_cache(q_cue, geom_col="geometry")
            if gdf_cue is not None and not gdf_cue.empty: gdf_cue = gdf_cue.to_crs(epsg=4326)
            else: raise ValueError("La capa de cuencas está vacía.")

            col_mun = next((c for c in ['nombre_municipio', 'mpio_cnmbr', 'MPIO_CNMBR', 'municipio'] if c in gdf_mun.columns), 'municipio')
            gdf_mun['mun_norm'] = gdf_mun[col_mun].astype(str).str.upper().str.strip()
            
            gdf_mun['geometry'] = gdf_mun.geometry.buffer(0)
            gdf_cue['geometry'] = gdf_cue.geometry.buffer(0)
            
            inter_mc = gpd.overlay(gdf_mun[['mun_norm', 'geometry']], gdf_cue[['subc_lbl', 'geometry']], how='intersection')
            inter_mc = inter_mc[inter_mc.geometry.area > 0.000001].copy()
            inter_mc['area_geo_frag'] = inter_mc.geometry.area
            
            del gdf_mun, gdf_cue; gc.collect()

            texto_progreso.info("🌱 Fase 1/2: Escaneando usos del suelo para hábitats específicos...")
            stats = zonal_stats(inter_mc, raster_path, categorical=True, nodata=-9999)
            
            CLASES_BOVINOS = [7] 
            CLASES_GRANJAS = [2, 3, 4, 5, 6, 8] 
            inter_mc['pixeles_bovinos'] = [sum(stat.get(c, 0) for c in CLASES_BOVINOS) for stat in stats]
            inter_mc['pixeles_granjas'] = [sum(stat.get(c, 0) for c in CLASES_GRANJAS) for stat in stats]

            texto_progreso.info("⚖️ Fase 1/2: Calculando pesos dasimétricos...")
            bovinos_municipio = inter_mc.groupby('mun_norm')['pixeles_bovinos'].transform('sum')
            granjas_municipio = inter_mc.groupby('mun_norm')['pixeles_granjas'].transform('sum')
            area_geo_municipio = inter_mc.groupby('mun_norm')['area_geo_frag'].transform('sum')

            inter_mc['peso_bovinos'] = np.where(bovinos_municipio > 0, inter_mc['pixeles_bovinos'] / bovinos_municipio, inter_mc['area_geo_frag'] / area_geo_municipio)
            inter_mc['peso_granjas'] = np.where(granjas_municipio > 0, inter_mc['pixeles_granjas'] / granjas_municipio, inter_mc['area_geo_frag'] / area_geo_municipio)

            import os
            os.remove(raster_path) 
            barra_progreso.progress(0.4)

            # 2. MOTOR MATEMÁTICO UNIVERSAL
            texto_progreso.info("🧠 Fase 2/2: Entrenando modelos matemáticos multiescala...")
            
            def f_log(t, k, a, r): return k / (1 + a * np.exp(-r * t))
            def f_exp(t, a, b): return a * np.exp(b * t)
            def calcular_r2(y_real, y_pred):
                ss_tot = np.sum((y_real - np.mean(y_real)) ** 2)
                return 1 - (np.sum((y_real - y_pred) ** 2) / ss_tot) if ss_tot > 0 else 0
            
            matriz_resultados = []
            
            def ajustar_modelos(x, y, nivel, territorio, especie):
                if len(x) < 3 or max(y) <= 0: return 
                x_offset = x[0]
                x_norm = x - x_offset
                p0_val = max(1, y[0])
                max_y = max(y)
                es_creciente = y[-1] >= p0_val
                
                log_k, log_a, log_r, log_r2 = 0, 0, 0, 0
                try:
                    k_max = max_y * 3.0 if es_creciente else max_y * 1.1
                    k_guess = max_y * 1.2 if es_creciente else (y[-1] * 0.9 if y[-1] > 0 else max_y)
                    a_guess = (k_guess - p0_val) / p0_val if p0_val > 0 else 1
                    r_guess = 0.02 if es_creciente else -0.02
                    limites = ([max_y*0.8 if es_creciente else max_y*0.1, 0, -0.2], [k_max, np.inf, 0.3])
                    popt_log, _ = curve_fit(f_log, x_norm, y, p0=[k_guess, a_guess, r_guess], bounds=limites, maxfev=50000)
                    log_k, log_a, log_r = popt_log
                    log_r2 = calcular_r2(y, f_log(x_norm, *popt_log))
                except Exception: pass

                exp_a, exp_b, exp_r2 = 0, 0, 0
                try:
                    popt_exp, _ = curve_fit(f_exp, x_norm, y, p0=[p0_val, 0.01], maxfev=50000)
                    exp_a, exp_b = popt_exp
                    exp_r2 = calcular_r2(y, f_exp(x_norm, *popt_exp))
                except Exception: pass

                poly_A, poly_B, poly_C, poly_D, poly_r2 = 0, 0, 0, 0, 0
                try:
                    coefs = np.polyfit(x_norm, y, 3)
                    poly_A, poly_B, poly_C, poly_D = coefs
                    poly_r2 = calcular_r2(y, np.polyval(coefs, x_norm))
                except Exception: pass

                lin_m, lin_b, lin_r2 = 0, 0, 0
                try:
                    coefs_lin = np.polyfit(x_norm, y, 1)
                    lin_m, lin_b = coefs_lin
                    lin_r2 = calcular_r2(y, np.polyval(coefs_lin, x_norm))
                except Exception: pass

                dic_modelos = {'Logístico': log_r2, 'Exponencial': exp_r2, 'Polinomial_3': poly_r2, 'Lineal': lin_r2}
                mejor_modelo = max(dic_modelos, key=dic_modelos.get)
                mejor_r2 = dic_modelos[mejor_modelo]

                # 🔑 LLAVE UNIVERSAL PERFECTA E HIGIÉNICA
                terr_visual = " ".join(str(territorio).split()) 
                try: terr_n = normalizar_texto(territorio).upper()
                except: terr_n = re.sub(r'[^A-Z0-9]', '', unicodedata.normalize('NFD', str(territorio).upper()).encode('ascii', 'ignore').decode('utf-8'))
                
                nivel_norm = str(nivel).upper().strip()
                if "NACION" in nivel_norm: nivel_norm = "NACIONAL"
                elif "DEPARTAMENTO" in nivel_norm or "DEPARTAMENTAL" in nivel_norm: nivel_norm = "DEPARTAMENTAL"
                elif "MUNICIP" in nivel_norm: nivel_norm = "MUNICIPAL"
                elif "REGION" in nivel_norm or "SUBREGION" in nivel_norm: nivel_norm = "REGIONAL"
                elif "CAR" in nivel_norm or "AUTORIDAD" in nivel_norm: nivel_norm = "CAR"
                elif "CUENCA" in nivel_norm or "NSS" in nivel_norm or "SZH" in nivel_norm or "ZH" in nivel_norm or "AH" in nivel_norm: nivel_norm = "CUENCA"

                llave_u = f"{nivel_norm}_{terr_n}_TOTAL".upper().replace(" ", "_")

                matriz_resultados.append({
                    'Especie': especie, 'Nivel': nivel_norm, 'Territorio': terr_visual, 
                    'LLAVE_UNIVERSAL': llave_u, 'Año_Base': int(x_offset), 'Poblacion_Base': round(p0_val, 0),
                    'Log_K': log_k, 'Log_a': log_a, 'Log_r': log_r, 'Log_R2': round(log_r2, 4),
                    'Exp_a': exp_a, 'Exp_b': exp_b, 'Exp_R2': round(exp_r2, 4),
                    'Poly_A': poly_A, 'Poly_B': poly_B, 'Poly_C': poly_C, 'Poly_D': poly_D, 'Poly_R2': round(poly_r2, 4),
                    'Lin_m': lin_m, 'Lin_b': lin_b, 'Lin_R2': round(lin_r2, 4), 
                    'Modelo_Recomendado': mejor_modelo, 'Mejor_R2': round(mejor_r2, 4)
                })

            df_censo = df_pecuario.copy()
            col_censo_mun = 'Municipio_Norm' if 'Municipio_Norm' in df_censo.columns else 'Municipio'
            df_censo['mun_norm'] = df_censo[col_censo_mun].astype(str).str.upper().str.strip()

            # 🚀 0. NACIONAL (COLOMBIA)
            df_nacional = df_censo.groupby('Anio')[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
            for esp in ['Bovinos', 'Porcinos', 'Aves']:
                ajustar_modelos(df_nacional['Anio'].values, df_nacional[esp].values, 'NACIONAL', 'COLOMBIA', esp)

            # --- E. DEPARTAMENTAL (ANTIOQUIA) ---
            df_depto = df_censo.groupby('Anio')[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
            for esp in ['Bovinos', 'Porcinos', 'Aves']:
                ajustar_modelos(df_depto['Anio'].values, df_depto[esp].values, 'DEPARTAMENTAL', 'ANTIOQUIA', esp)

            # --- A. MUNICIPALES ---
            df_mpios = df_censo.groupby(['Anio', 'mun_norm'])[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
            for mpio in df_mpios['mun_norm'].unique():
                df_t = df_mpios[df_mpios['mun_norm'] == mpio].sort_values('Anio')
                for esp in ['Bovinos', 'Porcinos', 'Aves']:
                    ajustar_modelos(df_t['Anio'].values, df_t[esp].values, 'MUNICIPAL', mpio, esp)

            # Extraemos Subregiones y CARs del Maestro
            import io
            import requests
            url_maestro = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/territorio_maestro.xlsx"
            res_m = requests.get(url_maestro, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
            df_maestro = pd.read_excel(io.BytesIO(res_m.content))
            df_censo['match_id'] = df_censo['mun_norm'].astype(str).apply(normalizar_texto)
            df_maestro['match_id'] = df_maestro['municipio'].astype(str).apply(normalizar_texto)
            df_maestro_nombres = df_maestro.drop_duplicates(subset=['match_id'])
            df_censo = df_censo.merge(df_maestro_nombres[['match_id', 'subregion', 'car']], on='match_id', how='left')
            
            mask_aburra = df_censo['subregion'].str.contains('Aburr', case=False, na=False)
            df_censo.loc[mask_aburra, 'car'] = 'Corantioquia'

            # --- B. SUBREGIONES ---
            if 'subregion' in df_censo.columns:
                df_reg = df_censo.groupby(['Anio', 'subregion'])[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
                for reg in df_reg['subregion'].dropna().unique():
                    df_t = df_reg[df_reg['subregion'] == reg].sort_values('Anio')
                    for esp in ['Bovinos', 'Porcinos', 'Aves']:
                        ajustar_modelos(df_t['Anio'].values, df_t[esp].values, 'REGIONAL', reg, esp)

            # --- C. CARs ---
            if 'car' in df_censo.columns:
                df_car = df_censo.groupby(['Anio', 'car'])[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
                for autoridad in df_car['car'].dropna().unique():
                    df_t = df_car[df_car['car'] == autoridad].sort_values('Anio')
                    for esp in ['Bovinos', 'Porcinos', 'Aves']:
                        ajustar_modelos(df_t['Anio'].values, df_t[esp].values, 'CAR', autoridad, esp)

            # --- D. CUENCAS (Dasimetría) ---
            fragmentos_pecuarios = []
            for mpio in inter_mc['mun_norm'].unique():
                df_animales_mpio = df_censo[df_censo['mun_norm'] == mpio].copy()
                if df_animales_mpio.empty: continue
                pedazos = inter_mc[inter_mc['mun_norm'] == mpio]
                for _, pedazo in pedazos.iterrows():
                    df_frag = df_animales_mpio.copy()
                    df_frag['Bovinos'] = df_frag['Bovinos'] * pedazo['peso_bovinos']
                    df_frag['Porcinos'] = df_frag['Porcinos'] * pedazo['peso_granjas']
                    df_frag['Aves'] = df_frag['Aves'] * pedazo['peso_granjas']
                    df_frag['subc_lbl'] = pedazo['subc_lbl']
                    fragmentos_pecuarios.append(df_frag)

            if fragmentos_pecuarios:
                df_hist_pecuario = pd.concat(fragmentos_pecuarios)
                df_hist_pecuario['subc_lbl'] = df_hist_pecuario['subc_lbl'].astype(str).str.strip()
                
                q_jerarquia = text("""
                    SELECT DISTINCT
                        CASE WHEN TRIM(nomah) != '' THEN TRIM(nomah) ELSE NULL END AS nomah,
                        CASE WHEN TRIM(nomzh) != '' THEN TRIM(nomzh) ELSE NULL END AS nomzh,
                        CASE WHEN TRIM(nom_szh) != '' THEN TRIM(nom_szh) ELSE NULL END AS nom_szh,
                        CASE WHEN TRIM(nom_nss1) != '' THEN TRIM(nom_nss1) ELSE NULL END AS nom_nss1,
                        CASE WHEN TRIM(nom_nss2) != '' THEN TRIM(nom_nss2) ELSE NULL END AS nom_nss2,
                        CASE WHEN TRIM(nom_nss3) != '' THEN TRIM(nom_nss3) ELSE NULL END AS nom_nss3,
                        COALESCE(
                            CASE WHEN TRIM(nom_nss3) != '' THEN TRIM(nom_nss3) || ' - (' || TRIM(CAST(nss3 AS TEXT)) || ')' ELSE NULL END,
                            CASE WHEN TRIM(nom_nss2) != '' THEN TRIM(nom_nss2) || ' - (' || TRIM(CAST(nss2 AS TEXT)) || ')' ELSE NULL END,
                            CASE WHEN TRIM(nom_nss1) != '' THEN TRIM(nom_nss1) || ' - (' || TRIM(CAST(nss1 AS TEXT)) || ')' ELSE NULL END,
                            CASE WHEN TRIM(nom_szh) != '' THEN TRIM(nom_szh) || ' - (' || TRIM(CAST(szh AS TEXT)) || ')' ELSE NULL END,
                            CASE WHEN TRIM(nomzh) != '' THEN TRIM(nomzh) || ' - (' || TRIM(CAST(zh AS TEXT)) || ')' ELSE NULL END,
                            CASE WHEN TRIM(nomah) != '' THEN TRIM(nomah) || ' - (' || TRIM(CAST(ah AS TEXT)) || ')' ELSE NULL END,
                            'Cuenca Sin Nombre'
                        ) AS subc_lbl
                    FROM cuencas
                """)
                df_arbol = pd.read_sql(q_jerarquia, engine_geo)
                for c in df_arbol.columns: df_arbol[c] = df_arbol[c].astype(str).str.strip()
                
                df_hidro_completo = pd.merge(df_hist_pecuario, df_arbol.drop_duplicates(subset=['subc_lbl']), on='subc_lbl', how='left')
                
                niveles_hidro = ['nomah', 'nomzh', 'nom_szh', 'nom_nss1', 'nom_nss2', 'subc_lbl']
                for col_nivel in niveles_hidro:
                    if col_nivel in df_hidro_completo.columns:
                        df_nivel = df_hidro_completo.dropna(subset=[col_nivel]).groupby([col_nivel, 'Anio'])[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
                        for terr in df_nivel[col_nivel].unique():
                            if terr in ["", "None", "nan", "Cuenca Sin Nombre"]: continue
                            
                            # 🚀 FIX CUENCAS: Separamos el código (ej. 2317) para crear una llave limpia
                            nombre_puro_cuenca = str(terr).split(" - (")[0].strip() if " - (" in str(terr) else str(terr).strip()
                            
                            df_t = df_nivel[df_nivel[col_nivel] == terr].sort_values('Anio')
                            for esp in ['Bovinos', 'Porcinos', 'Aves']:
                                ajustar_modelos(df_t['Anio'].values, df_t[esp].values, 'CUENCA', nombre_puro_cuenca, esp)

            df_matriz_pec = pd.DataFrame(matriz_resultados)
            st.session_state['df_matriz_pecuaria'] = df_matriz_pec 
            
            barra_progreso.progress(1.0)
            texto_progreso.success(f"✅ ¡Forja Pecuaria Integral Exitosa! {len(df_matriz_pec)} modelos blindados.")

        except Exception as e:
            st.error(f"🚨 Error en el Motor Pecuario: {e}")

    if 'df_matriz_pecuaria' in st.session_state:
        if st.button("🚀 Inyectar a Base de Datos (SQL)", use_container_width=True):
            try:
                from modules.db_manager import get_engine
                from sqlalchemy import text 
                engine_sql = get_engine()
                df_export = st.session_state['df_matriz_pecuaria'].copy()
                
                with engine_sql.begin() as conn:
                    # Nos aseguramos de que existan las columnas de la Llave Universal y las variables Lineales
                    conn.execute(text('ALTER TABLE matriz_maestra_pecuaria ADD COLUMN IF NOT EXISTS "LLAVE_UNIVERSAL" TEXT;'))
                    conn.execute(text('ALTER TABLE matriz_maestra_pecuaria ADD COLUMN IF NOT EXISTS "Lin_m" FLOAT, ADD COLUMN IF NOT EXISTS "Lin_b" FLOAT, ADD COLUMN IF NOT EXISTS "Lin_R2" FLOAT;'))
                    conn.execute(text("DELETE FROM matriz_maestra_pecuaria;"))
                    
                df_export.to_sql('matriz_maestra_pecuaria', engine_sql, if_exists='append', index=False)
                st.success(f"✅ ¡Inyección Exitosa! Registros blindados en PostgreSQL con Llave Universal.")
            except Exception as e:
                st.error(f"Error SQL: {e}")