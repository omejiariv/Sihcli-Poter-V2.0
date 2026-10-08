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
    from modules.utils import cargar_capa_espacial_cache, encender_gemelo_digital
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules import selectors
    from modules.utils import cargar_capa_espacial_cache, encender_gemelo_digital

selectors.renderizar_menu_navegacion("Modelo Pecuario")
encender_gemelo_digital()

# ====================================================================
# 🗝️ MOTOR GENERADOR DE LLAVES
# ====================================================================
def generar_llave_maestra(escala, territorio):
    e = str(escala).upper().strip()
    if "NACION" in e: e = "NACIONAL"
    elif "DEPARTAMENTO" in e or "DEPARTAMENTAL" in e: e = "DEPARTAMENTAL"
    elif "MUNICIP" in e: e = "MUNICIPAL"
    elif "REGION" in e or "SUBREGION" in e: e = "REGIONAL"
    elif "CAR" in e or "AUTORIDAD" in e: e = "CAR"
    elif "CUENCA" in e or "NSS" in e or "SZH" in e or "ZH" in e or "AH" in e: e = "CUENCA"
    
    t = str(territorio).split(" - (")[0].strip()
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode('utf-8').upper()
    t = re.sub(r'[^A-Z0-9]', '_', t) 
    t = re.sub(r'_+', '_', t).strip('_') 
    
    return f"{e}_{t}_TOTAL"

def limpiar_fuerte(texto):
    if not texto or pd.isna(texto): return ""
    t = str(texto).upper()
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9]', '', t)

# ====================================================================
# 🧽 ESTADO GLOBAL Y LECTURA DEL ALEPH (EXORCISMO DE FANTASMAS)
# ====================================================================
if 'aleph_lugar' not in st.session_state:
    st.warning("👈 Selecciona un territorio en 'El Aleph' (Panel Lateral Izquierdo) para comenzar.")
    st.stop()

territorio_sel = st.session_state['aleph_lugar']
nivel_backend = st.session_state['aleph_escala']

st.title("🐄 Modelo Pecuario (Proyección Demográfica Animal)")
st.markdown("Proyecciones matemáticas de inventarios bovinos, porcinos y avícolas conectadas a la dinámica espacial de la cuenca.")

st.sidebar.header("⚙️ Configuración del Modelo")
anio_destino = st.sidebar.slider("Horizonte de Proyección:", 2024, 2050, 2030)

@st.cache_data(ttl=3600)
def cargar_historico_pecuario():
    import pandas as pd
    
    url_aves = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/Censo_Maestro_Aves.csv"
    url_bov = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/Censo_Maestro_Bovinos.csv"
    url_porc = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/Censo_Maestro_Porcinos.csv"
    
    def leer_csv_seguro(url):
        try:
            return pd.read_csv(url, sep=None, engine='python', encoding='utf-8-sig')
        except Exception:
            try:
                return pd.read_csv(url, sep=';', encoding='latin1')
            except Exception as e:
                st.error(f"Error leyendo {url}: {e}")
                return pd.DataFrame()

    df_a = leer_csv_seguro(url_aves)
    df_b = leer_csv_seguro(url_bov)
    df_p = leer_csv_seguro(url_porc)
    
    def col(df, keywords, default):
        for c in df.columns:
            for k in keywords:
                if k in c.upper(): return c
        return default

    # 1. Armonizar BOVINOS
    if not df_b.empty:
        df_b = df_b[[col(df_b, ['AÑO','ANIO'], 'AÑO'), 'CODIGO_MUNICIPIO', 'MUNICIPIO', 'TOTAL_BOVINOS', 'TOTAL_FINCAS_BOVINOS']].rename(
            columns={col(df_b, ['AÑO','ANIO'], 'AÑO'): 'Anio', 'TOTAL_BOVINOS': 'Bovinos', 'TOTAL_FINCAS_BOVINOS': 'Fincas_Bovinos'}
        )
    
    # 2. Armonizar PORCINOS
    if not df_p.empty:
        c_p = col(df_p, ['CERDO','PORC'], 'TOTAL_CERDOS')
        c_f = col(df_p, ['PREDIO','FINCA'], 'TOTAL_PREDIOS_PORCICOLAS')
        df_p = df_p[[col(df_p, ['AÑO','ANIO'], 'AÑO'), 'CODIGO_MUNICIPIO', c_p, c_f]].rename(
            columns={col(df_p, ['AÑO','ANIO'], 'AÑO'): 'Anio', c_p: 'Porcinos', c_f: 'Fincas_Porcinos'}
        )
        
    # 3. Armonizar AVES
    if not df_a.empty:
        c_a = col(df_a, ['AVE'], 'TOTAL_AVES')
        c_g = col(df_a, ['PREDIO','GRANJA','FINCA'], 'TOTAL_PREDIOS_AVICOLAS')
        df_a = df_a[[col(df_a, ['AÑO','ANIO'], 'AÑO'), 'CODIGO_MUNICIPIO', c_a, c_g]].rename(
            columns={col(df_a, ['AÑO','ANIO'], 'AÑO'): 'Anio', c_a: 'Aves', c_g: 'Fincas_Aves'}
        )
        
    dfs = [df for df in [df_b, df_p, df_a] if not df.empty]
    
    if dfs:
        from functools import reduce
        df_final = reduce(lambda l, r: pd.merge(l, r, on=['Anio', 'CODIGO_MUNICIPIO'], how='outer'), dfs)
        
        col_muns = [c for c in df_final.columns if 'MUNICIPIO' in c and c != 'CODIGO_MUNICIPIO']
        df_final['Municipio_Norm'] = df_final[col_muns].bfill(axis=1).iloc[:, 0]
        
        # 🚀 LA CURA DE LA SUBVALORACIÓN (Bisturí Inteligente)
        cols_num = ['Bovinos', 'Porcinos', 'Aves', 'Fincas_Bovinos', 'Fincas_Porcinos', 'Fincas_Aves']
        for c in cols_num:
            if c in df_final.columns:
                # Si Pandas ya lo reconoce como número (ej: 424881.0), lo dejamos quieto y lo pasamos a entero
                if pd.api.types.is_numeric_dtype(df_final[c]):
                    df_final[c] = df_final[c].fillna(0).astype(int)
                else:
                    # Si Pandas lo lee como texto con puntos (ej: "3.283.821"), quitamos los puntos y convertimos a número
                    df_final[c] = df_final[c].astype(str).str.replace('.', '', regex=False).str.replace(',', '', regex=False)
                    df_final[c] = pd.to_numeric(df_final[c], errors='coerce').fillna(0).astype(int)
            else:
                df_final[c] = 0
                
        return df_final
        
    return pd.DataFrame()

df_pecuario = cargar_historico_pecuario()

# =====================================================================
# 🔬 PERFIL VISUAL Y SINCRONIZACIÓN AL ALEPH
# =====================================================================
if 'df_matriz_pecuaria' in st.session_state:
    df_mat = st.session_state['df_matriz_pecuaria']
    st.subheader(f"📊 Perfil Pecuario: {territorio_sel}")
    
    def crear_firma(t):
        if not isinstance(t, str) or pd.isna(t): return ""
        t_limpio = re.sub(r'[^A-Z0-9]', '', str(t).upper())
        return re.sub(r'[AEIOU]', '', t_limpio)
        
    t_puro = str(territorio_sel).split(" - (")[0].strip()
    t_puro = t_puro.replace(' - NSS', '').replace('- NSS', '').strip()
    t_puro = ''.join(c for c in unicodedata.normalize('NFD', t_puro) if unicodedata.category(c) != 'Mn')
    
    excepciones_antioquia = {
        "PUEBLO RICO": "PUEBLORRICO",
        "SAN VICENTE": "SAN VICENTE FERRER",
        "EL PENOL": "PENOL",
        "EL RETIRO": "RETIRO",
        "CAROLINA DEL PRINCIPE": "CAROLINA", 
        "SAN ANDRES DE CUERQUIA": "SAN ANDRES",
        "SAN JOSE DE LA MONTANA": "SAN JOSE",
        "SAN PEDRO DE LOS MILAGROS": "SAN PEDRO"
    }
    if t_puro.upper() in excepciones_antioquia:
        t_puro = excepciones_antioquia[t_puro.upper()]

    firma_buscada = crear_firma(t_puro)
    df_filtrado = pd.DataFrame()

    if 'Nivel' in df_mat.columns:
        if "CUENCA" in str(nivel_backend).upper():
            df_nivel = df_mat[df_mat['Nivel'].str.contains("NSS|SZH|ZH|AH|CUE", regex=True, na=False)].copy()
        else:
            niv_corto = "MUNI" if "MUNICIP" in nivel_backend else ("CAR" if "CAR" in nivel_backend else ("REGIO" if "REGION" in nivel_backend else nivel_backend[:3]))
            df_nivel = df_mat[df_mat['Nivel'].str.upper().str.contains(niv_corto, na=False)].copy()
    else:
        df_nivel = df_mat.copy()

    def obtener_todas_las_especies(df, col_firma, f_buscada):
        mask = df[col_firma].str.contains(f_buscada, na=False)
        if mask.any():
            firma_exacta_bd = df.loc[mask, col_firma].iloc[0]
            return df[df[col_firma] == firma_exacta_bd]
        return pd.DataFrame()

    if not df_nivel.empty:
        if 'LLAVE_UNIVERSAL' in df_nivel.columns:
            df_nivel['Firma_DB'] = df_nivel['LLAVE_UNIVERSAL'].apply(crear_firma)
            df_filtrado = obtener_todas_las_especies(df_nivel, 'Firma_DB', firma_buscada)
            
        if df_filtrado.empty and 'Territorio' in df_nivel.columns:
            df_nivel['Firma_DB'] = df_nivel['Territorio'].apply(crear_firma)
            df_filtrado = obtener_todas_las_especies(df_nivel, 'Firma_DB', firma_buscada)
            
        if df_filtrado.empty and len(firma_buscada) > 3:
            df_filtrado = obtener_todas_las_especies(df_nivel, 'Firma_DB', firma_buscada[:-1])

    if df_filtrado.empty:
        llave_busqueda = generar_llave_maestra(nivel_backend, territorio_sel)
        st.warning(f"⚠️ No hay modelos entrenados para **{territorio_sel}**. Despliega el 'Entrenador de Modelos' abajo para forjarlo.")
    else:
        st.toast("🔗 Conexión inteligente pecuaria activada", icon="🧠")
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
                mejor_modelo = fila_terr.get('Modelo_Recomendado', 'Lineal')
                r2_mejor = fila_terr.get('Mejor_R2', 0.0)
                
                x_offset = fila_terr.get('Año_Base', 2018)
                x_pred = np.arange(x_offset, anio_destino + 1)
                x_norm_pred = x_pred - x_offset
                
                lin_m = fila_terr.get('Lin_m', 0)
                lin_b = fila_terr.get('Lin_b', 0)
                
                if pd.isna(lin_m): lin_m = 0
                if pd.isna(lin_b) or lin_b == 0: 
                    lin_b = fila_terr.get('Poblacion_Base', 0)
                    if pd.isna(lin_b): lin_b = 0
                    
                y_lin = lin_m * x_norm_pred + lin_b
                
                y_log = np.zeros_like(x_pred, dtype=float)
                if fila_terr.get('Log_K', 0) > 0:
                    y_log = fila_terr['Log_K'] / (1 + fila_terr['Log_a'] * np.exp(-fila_terr['Log_r'] * x_norm_pred))
                
                if mejor_modelo == 'Logístico' and fila_terr.get('Log_K', 0) > 0:
                    y_ganador = y_log
                else:
                    y_ganador = y_lin
                    
                valor_futuro = max(0.0, float(y_ganador[-1]))
                resultados_calculados[especie] = valor_futuro
                
                c_graf, c_info = st.columns([3, 1.2])
                
                with c_graf:
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(x=x_pred, y=y_lin, mode='lines', name=f"Ajuste Lineal (R²={fila_terr.get('Lin_R2', 0):.2f})", line=dict(color='#3498db', width=2, dash='dot'), visible=True if mejor_modelo == 'Lineal' else 'legendonly'))
                    
                    if fila_terr.get('Log_K', 0) > 0:
                        fig.add_trace(go.Scatter(x=x_pred, y=y_log, mode='lines', name=f"Ajuste Logístico (R²={fila_terr.get('Log_R2', 0):.2f})", line=dict(color='#9b59b6', width=2, dash='dot'), visible=True if mejor_modelo == 'Logístico' else 'legendonly'))
                    
                    año_corte = 2025
                    mask_hist = x_pred <= año_corte
                    mask_proj = x_pred >= año_corte
                    
                    fig.add_trace(go.Scatter(x=x_pred[mask_hist], y=y_ganador[mask_hist], mode='lines', name=f"Tendencia Modelada ({mejor_modelo})", line=dict(color='#27ae60', width=4)))
                    fig.add_trace(go.Scatter(x=x_pred[mask_proj], y=y_ganador[mask_proj], mode='lines', name="Proyección Futura", line=dict(color='#27ae60', width=4, dash='dash')))
                    
                    pob_base = fila_terr.get('Poblacion_Base', 0)
                    fig.add_trace(go.Scatter(x=[x_offset], y=[pob_base], mode='markers', name='Ancla Censo Base', marker=dict(color='#e74c3c', size=10, symbol='diamond')))

                    fig.update_layout(
                        title=f"Evolución {especie} | Base: {x_offset} ➔ Destino: {anio_destino}", 
                        xaxis_title="Año", yaxis_title="Cabezas / Aves", hovermode="x unified", height=450,
                        margin=dict(l=20, r=20, t=50, b=20),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    st.success(f"📈 Proyección **{anio_destino}**: **{int(valor_futuro):,}** {especie.lower()}.")
                    
                with c_info:
                    st.markdown("### 🔬 Auditoría del Modelo")
                    st.info(f"**🏆 Ganador:** {mejor_modelo}\n\n**🎯 Precisión (R²):** {r2_mejor:.4f}")
                    st.caption("El motor matemático evalúa múltiples funciones y selecciona la que mejor explica la tendencia histórica.")
                    
                    df_tabla = pd.DataFrame({
                        'Año': x_pred,
                        'Oficial': np.maximum(0, y_ganador).astype(int),
                        'Lineal': np.maximum(0, y_lin).astype(int),
                        'Logístico': np.maximum(0, y_log).astype(int) if fila_terr.get('Log_K', 0) > 0 else 0
                    })
                    
                    if 'MUNICIP' in str(nivel_backend).upper():
                        col_fincas = f"Fincas_{especie}"
                        if col_fincas in df_pecuario.columns:
                            territorio_puro = limpiar_fuerte(fila_terr.get('Territorio', ''))
                            df_mun_real = df_pecuario[df_pecuario['Municipio_Norm'].apply(limpiar_fuerte) == territorio_puro]
                            
                            if not df_mun_real.empty:
                                mapa_fincas = dict(zip(df_mun_real['Anio'], df_mun_real[col_fincas]))
                                df_tabla['Nº Predios'] = df_tabla['Año'].map(mapa_fincas).fillna(0).astype(int)
                                cols_ordenadas = ['Año', 'Nº Predios', 'Oficial', 'Lineal', 'Logístico']
                                df_tabla = df_tabla[cols_ordenadas]
                    
                    st.markdown("#### 📄 Datos de Proyección")
                    st.dataframe(df_tabla, use_container_width=True, hide_index=True, height=200)
                    
                    csv = df_tabla.to_csv(index=False).encode('utf-8')
                    st.download_button(f"📥 Descargar CSV ({especie})", csv, f"proyeccion_{especie.lower()}.csv", "text/csv", key=f"btn_{especie}")

        st.session_state['ica_bovinos_calc_met'] = resultados_calculados.get('Bovinos', 0.0)
        st.session_state['ica_porcinos_calc_met'] = resultados_calculados.get('Porcinos', 0.0)
        st.session_state['ica_aves_calc_met'] = resultados_calculados.get('Aves', 0.0)

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("🐄 Carga Bovina", f"{int(resultados_calculados.get('Bovinos', 0)):,}", "Lista para Calidad del Agua")
        c2.metric("🐖 Carga Porcina", f"{int(resultados_calculados.get('Porcinos', 0)):,}", "Lista para Calidad del Agua")
        c3.metric("🐔 Carga Avícola", f"{int(resultados_calculados.get('Aves', 0)):,}", "Lista para Calidad del Agua")

# =====================================================================
# 🛠️ ENTRENADOR DE MODELOS PECUTARIOS (FORJA SQL AUTOMÁTICA)
# =====================================================================
st.markdown("---")
with st.expander("🛠️ Entrenador de Modelos Pecuarios (Forja Automática a SQL)", expanded=False):
    
    # 🚀 LA CURA FINAL: Al presionar este botón, se calcula y se inyecta directamente a la Base de Datos. No hay que pulsar otro botón.
    if st.button("⚙️ Iniciar Forja Pecuaria Integral e Inyectar a la Nube", type="primary"):
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

            texto_progreso.info("📍 Fase 1/3: Descargando Raster de Usos del Suelo (2022)...")
            URL_RASTER = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/rasters/Cob2026_Actualizada.tif"
            tmp_raster = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
            urllib.request.urlretrieve(URL_RASTER, tmp_raster.name)
            raster_path = tmp_raster.name

            texto_progreso.info("🗺️ Fase 1/3: Cruzando cartografía espacial (Alineando Coordenadas)...")
            q_mun = "SELECT * FROM municipios WHERE geometry IS NOT NULL"
            gdf_mun = cargar_capa_espacial_cache(q_mun, geom_col="geometry")
            if gdf_mun is not None and not gdf_mun.empty: gdf_mun = gdf_mun.to_crs(epsg=4326)
            
            q_cue = "SELECT COALESCE(CASE WHEN TRIM(nom_nss3) != '' THEN TRIM(nom_nss3) || ' - (' || TRIM(CAST(nss3 AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nom_nss2) != '' THEN TRIM(nom_nss2) || ' - (' || TRIM(CAST(nss2 AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nom_nss1) != '' THEN TRIM(nom_nss1) || ' - (' || TRIM(CAST(nss1 AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nom_szh) != '' THEN TRIM(nom_szh) || ' - (' || TRIM(CAST(szh AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nomzh) != '' THEN TRIM(nomzh) || ' - (' || TRIM(CAST(zh AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nomah) != '' THEN TRIM(nomah) || ' - (' || TRIM(CAST(ah AS TEXT)) || ')' ELSE NULL END, 'Cuenca Sin Nombre') AS subc_lbl, geometry FROM cuencas WHERE geometry IS NOT NULL"
            gdf_cue = cargar_capa_espacial_cache(q_cue, geom_col="geometry")
            if gdf_cue is not None and not gdf_cue.empty: gdf_cue = gdf_cue.to_crs(epsg=4326)

            col_mun = next((c for c in ['nombre_municipio', 'mpio_cnmbr', 'MPIO_CNMBR', 'municipio'] if c in gdf_mun.columns), 'municipio')
            gdf_mun['mun_norm'] = gdf_mun[col_mun].apply(limpiar_fuerte)
            
            gdf_mun['geometry'] = gdf_mun.geometry.buffer(0)
            gdf_cue['geometry'] = gdf_cue.geometry.buffer(0)
            
            inter_mc = gpd.overlay(gdf_mun[['mun_norm', 'geometry']], gdf_cue[['subc_lbl', 'geometry']], how='intersection')
            inter_mc = inter_mc[inter_mc.geometry.area > 0.000001].copy()
            inter_mc['area_geo_frag'] = inter_mc.to_crs(epsg=3116).geometry.area
            
            del gdf_mun, gdf_cue; gc.collect()

            texto_progreso.info("🌱 Fase 1/3: Escaneando usos del suelo (Matriz Dasimétrica 2026)...")
            import rasterio
            with rasterio.open(raster_path) as src:
                raster_crs = src.crs
            
            inter_mc_raster = inter_mc.to_crs(raster_crs)
            stats = zonal_stats(inter_mc_raster, raster_path, categorical=True, nodata=0)
            
            clases_encontradas = set()
            for stat in stats: 
                if stat: clases_encontradas.update(stat.keys())
            
            if 30 in clases_encontradas or 40 in clases_encontradas:
                CLASES_BOVINOS = [30] 
                CLASES_GRANJAS = [40, 50, 60]
            elif 7 in clases_encontradas:
                CLASES_BOVINOS = [7] 
                CLASES_GRANJAS = [2, 3, 4, 5, 6, 8]
            else:
                CLASES_BOVINOS = [2] 
                CLASES_GRANJAS = [3, 5, 6]
                
            inter_mc['pixeles_bovinos'] = [sum(stat.get(c, 0) for c in CLASES_BOVINOS) if stat else 0 for stat in stats]
            inter_mc['pixeles_granjas'] = [sum(stat.get(c, 0) for c in CLASES_GRANJAS) if stat else 0 for stat in stats]

            texto_progreso.info("⚖️ Fase 1/3: Calculando pesos dasimétricos definitivos...")
            bovinos_municipio = inter_mc.groupby('mun_norm')['pixeles_bovinos'].transform('sum')
            granjas_municipio = inter_mc.groupby('mun_norm')['pixeles_granjas'].transform('sum')
            area_geo_municipio = inter_mc.groupby('mun_norm')['area_geo_frag'].transform('sum')

            inter_mc['peso_bovinos'] = np.where(bovinos_municipio > 0, inter_mc['pixeles_bovinos'] / bovinos_municipio, inter_mc['area_geo_frag'] / area_geo_municipio)
            inter_mc['peso_granjas'] = np.where(granjas_municipio > 0, inter_mc['pixeles_granjas'] / granjas_municipio, inter_mc['area_geo_frag'] / area_geo_municipio)

            try:
                os.remove(raster_path) 
            except Exception: pass 
                
            barra_progreso.progress(0.4)

            # =================================================================
            # 🧠 MOTOR MATEMÁTICO UNIVERSAL
            # =================================================================
            texto_progreso.info("🧠 Fase 2/3: Entrenando modelos matemáticos multiescala...")
            
            matriz_resultados = []
            
            def ajustar_modelos(x_in, y_in, nivel, territorio, especie):
                x = pd.to_numeric(x_in, errors='coerce')
                y = pd.to_numeric(y_in, errors='coerce')
                
                mask = ~np.isnan(y) & ~np.isnan(x)
                x_clean = x[mask]
                y_clean = y[mask]
                
                if len(x_clean) == 0: return 
                
                x_offset = int(x_clean[0])
                x_norm = x_clean - x_offset
                p0_val = max(0, y_clean[0])
                max_y = max(y_clean)
                es_creciente = y_clean[-1] >= p0_val
                
                log_k, log_a, log_r, log_r2 = 0, 0, 0, 0
                lin_m, lin_b, lin_r2 = 0, float(y_clean[-1]), 1.0 
                mejor_modelo = 'Lineal'
                mejor_r2 = 1.0

                if len(x_clean) >= 3 and max_y > 0:
                    def calcular_r2(y_real, y_pred):
                        ss_tot = np.sum((y_real - np.mean(y_real)) ** 2)
                        return 1 - (np.sum((y_real - y_pred) ** 2) / ss_tot) if ss_tot > 0 else 0

                    def f_log(t, k, a, r): return k / (1 + a * np.exp(-r * t))
                    
                    try:
                        k_max = max_y * 1.5 if es_creciente else max_y * 1.1
                        k_guess = max_y * 1.2 if es_creciente else (y_clean[-1] * 0.9 if y_clean[-1] > 0 else max_y)
                        a_guess = (k_guess - p0_val) / p0_val if p0_val > 0 else 1
                        r_guess = 0.05 if es_creciente else -0.05
                        limites = ([max_y*0.8 if es_creciente else max_y*0.1, 0, -0.2], [k_max, np.inf, 0.3])
                        popt_log, _ = curve_fit(f_log, x_norm, y_clean, p0=[k_guess, a_guess, r_guess], bounds=limites, maxfev=50000)
                        log_k, log_a, log_r = popt_log
                        log_r2 = calcular_r2(y_clean, f_log(x_norm, *popt_log))
                    except Exception: pass

                    try:
                        coefs_lin = np.polyfit(x_norm, y_clean, 1)
                        lin_m, lin_b = coefs_lin
                        lin_r2 = calcular_r2(y_clean, np.polyval(coefs_lin, x_norm))
                    except Exception: pass

                    dic_modelos = {'Logístico': log_r2, 'Lineal': lin_r2}
                    mejor_modelo = max(dic_modelos, key=dic_modelos.get)
                    mejor_r2 = dic_modelos[mejor_modelo]

                terr_visual = " ".join(str(territorio).split()) 
                llave_u = generar_llave_maestra(nivel, territorio)

                matriz_resultados.append({
                    'Especie': especie, 'Nivel': llave_u.split('_')[0], 'Territorio': terr_visual, 
                    'LLAVE_UNIVERSAL': llave_u, 'Año_Base': int(x_offset), 'Poblacion_Base': round(p0_val, 0),
                    'Log_K': log_k, 'Log_a': log_a, 'Log_r': log_r, 'Log_R2': round(log_r2, 4),
                    'Lin_m': lin_m, 'Lin_b': lin_b, 'Lin_R2': round(lin_r2, 4), 
                    'Modelo_Recomendado': mejor_modelo, 'Mejor_R2': round(mejor_r2, 4)
                })

            df_censo = df_pecuario.copy()
            
            import io
            import requests
            url_maestro = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/territorio_maestro.xlsx"
            res_m = requests.get(url_maestro, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
            df_maestro = pd.read_excel(io.BytesIO(res_m.content))
            
            df_maestro['match_id'] = df_maestro['municipio'].astype(str).apply(limpiar_fuerte)
            df_maestro_nombres = df_maestro.drop_duplicates(subset=['match_id'])
            dic_nombres = dict(zip(df_maestro_nombres['match_id'], df_maestro_nombres['municipio']))

            correcciones = {
                'ELCARMENDEVIBORAL': 'CARMENDEVIBORAL', 'SANVICENTEFERRER': 'SANVICENTE',
                'SANANDRESDECUERQUIA': 'SANANDRES', 'SANTAFEDEANTIOQUIA': 'SANTAFE',
                'SANJOSEDELAMONTANA': 'SANJOSE', 'CAROLINADELPRINCIPE': 'CAROLINA',
                'PUEBLORICO': 'PUEBLORRICO', 'ELPENOL': 'PENOL', 'LAPINTADA': 'PINTADA'
            }
            if 'Municipio_Norm' in df_censo.columns:
                df_censo['mun_norm'] = df_censo['Municipio_Norm'].apply(limpiar_fuerte)
                df_censo['mun_norm'] = df_censo['mun_norm'].replace(correcciones)

            df_censo = df_censo.merge(df_maestro_nombres[['match_id', 'subregion', 'car']], left_on='mun_norm', right_on='match_id', how='left')
            df_censo['subregion'] = df_censo['subregion'].astype(str).str.upper().str.strip()
            df_censo['car'] = df_censo['car'].astype(str).str.upper().str.strip()

            # --- NACIONAL ---
            df_nacional = df_censo.groupby('Anio')[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
            for esp in ['Bovinos', 'Porcinos', 'Aves']:
                ajustar_modelos(df_nacional['Anio'].values, df_nacional[esp].values, 'NACIONAL', 'COLOMBIA', esp)

            # --- DEPARTAMENTAL ---
            df_depto = df_censo.groupby('Anio')[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
            for esp in ['Bovinos', 'Porcinos', 'Aves']:
                ajustar_modelos(df_depto['Anio'].values, df_depto[esp].values, 'DEPARTAMENTAL', 'ANTIOQUIA', esp)

            # --- MUNICIPALES ---
            df_mpios = df_censo.groupby(['Anio', 'mun_norm'])[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
            for mpio in df_mpios['mun_norm'].unique():
                df_t = df_mpios[df_mpios['mun_norm'] == mpio].sort_values('Anio')
                nombre_visual = dic_nombres.get(mpio, mpio).upper()
                for esp in ['Bovinos', 'Porcinos', 'Aves']:
                    ajustar_modelos(df_t['Anio'].values, df_t[esp].values, 'MUNICIPAL', nombre_visual, esp)

            # --- SUBREGIONES ---
            # 🚀 FIX: Mapeo forzoso de subregiones para evitar que el Bajo Cauca se pierda
            mapa_subregiones = {
                'MEDELLIN': 'VALLE DE ABURRA', 'BELLO': 'VALLE DE ABURRA', 'ITAGUI': 'VALLE DE ABURRA', 'ENVIGADO': 'VALLE DE ABURRA', 'SABANETA': 'VALLE DE ABURRA', 'COPACABANA': 'VALLE DE ABURRA', 'LA ESTRELLA': 'VALLE DE ABURRA', 'GIRARDOTA': 'VALLE DE ABURRA', 'CALDAS': 'VALLE DE ABURRA', 'BARBOSA': 'VALLE DE ABURRA',
                'CAUCASIA': 'BAJO CAUCA', 'EL BAGRE': 'BAJO CAUCA', 'NECHI': 'BAJO CAUCA', 'TARAZA': 'BAJO CAUCA', 'CACERES': 'BAJO CAUCA', 'ZARAGOZA': 'BAJO CAUCA',
                'APARTADO': 'URABA', 'TURBO': 'URABA', 'CHIGORODO': 'URABA', 'CAREPA': 'URABA', 'NECOCLI': 'URABA', 'ARBOLETES': 'URABA', 'SAN JUAN DE URABA': 'URABA', 'SAN PEDRO DE URABA': 'URABA', 'MUTATA': 'URABA', 'MURINDO': 'URABA', 'VIGIA DEL FUERTE': 'URABA',
                'RIONEGRO': 'ORIENTE', 'MARINILLA': 'ORIENTE', 'GUARNE': 'ORIENTE', 'LA CEJA': 'ORIENTE', 'EL CARMEN DE VIBORAL': 'ORIENTE', 'RETIRO': 'ORIENTE', 'SANTUARIO': 'ORIENTE', 'GUATAPE': 'ORIENTE', 'PENOL': 'ORIENTE', 'SAN VICENTE': 'ORIENTE', 'SONSON': 'ORIENTE', 'ABEJORRAL': 'ORIENTE'
            }
            # Asignamos la subregión forzada si está vacía
            df_censo['subregion_forzada'] = df_censo['mun_norm'].map(mapa_subregiones).fillna(df_censo['subregion'])
            
            df_reg = df_censo.groupby(['Anio', 'subregion_forzada'])[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
            for reg in df_reg['subregion_forzada'].unique():
                if pd.isna(reg) or str(reg).strip() in ["", "NAN", "NONE"]: continue
                df_t = df_reg[df_reg['subregion_forzada'] == reg].sort_values('Anio')
                for esp in ['Bovinos', 'Porcinos', 'Aves']:
                    ajustar_modelos(df_t['Anio'].values, df_t[esp].values, 'REGIONAL', reg, esp)

            # --- CARs ---
            df_censo['car'] = df_censo['car'].replace({
                'ÁREA METROPOLITANA DEL VALLE DE ABURRÁ': 'AMVA',
                'AREA METROPOLITANA DEL VALLE DE ABURRA': 'AMVA',
                'AREA METROPOLITANA': 'AMVA',
                'CORPOURABÁ': 'CORPOURABA'
            })
            
            df_car = df_censo.groupby(['Anio', 'car'])[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
            cars_entrenadas = set()
            
            for autoridad in df_car['car'].unique():
                if autoridad in ["", "NAN", "NONE"]: continue
                df_t = df_car[df_car['car'] == autoridad].sort_values('Anio')
                for esp in ['Bovinos', 'Porcinos', 'Aves']:
                    ajustar_modelos(df_t['Anio'].values, df_t[esp].values, 'CAR', autoridad, esp)
                cars_entrenadas.add(autoridad)

            cars_esperadas = {'AMVA', 'CORPOURABA', 'CORNARE', 'CORANTIOQUIA'}
            x_cero = np.array([2018, 2022, 2023, 2024, 2025])
            y_cero = np.array([0, 0, 0, 0, 0])
            
            for car_faltante in (cars_esperadas - cars_entrenadas):
                for esp in ['Bovinos', 'Porcinos', 'Aves']:
                    ajustar_modelos(x_cero, y_cero, 'CAR', car_faltante, esp)

            # --- CUENCAS (Dasimetría) ---
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
                    
            cuencas_entrenadas = set()

            if fragmentos_pecuarios:
                df_hist_pecuario = pd.concat(fragmentos_pecuarios)
                df_hist_pecuario['subc_lbl'] = df_hist_pecuario['subc_lbl'].astype(str).str.strip()
                
                q_jerarquia = text("SELECT DISTINCT CASE WHEN TRIM(nomah) != '' THEN TRIM(nomah) ELSE NULL END AS nomah, CASE WHEN TRIM(nomzh) != '' THEN TRIM(nomzh) ELSE NULL END AS nomzh, CASE WHEN TRIM(nom_szh) != '' THEN TRIM(nom_szh) ELSE NULL END AS nom_szh, CASE WHEN TRIM(nom_nss1) != '' THEN TRIM(nom_nss1) ELSE NULL END AS nom_nss1, CASE WHEN TRIM(nom_nss2) != '' THEN TRIM(nom_nss2) ELSE NULL END AS nom_nss2, CASE WHEN TRIM(nom_nss3) != '' THEN TRIM(nom_nss3) ELSE NULL END AS nom_nss3, COALESCE(CASE WHEN TRIM(nom_nss3) != '' THEN TRIM(nom_nss3) || ' - (' || TRIM(CAST(nss3 AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nom_nss2) != '' THEN TRIM(nom_nss2) || ' - (' || TRIM(CAST(nss2 AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nom_nss1) != '' THEN TRIM(nom_nss1) || ' - (' || TRIM(CAST(nss1 AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nom_szh) != '' THEN TRIM(nom_szh) || ' - (' || TRIM(CAST(szh AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nomzh) != '' THEN TRIM(nomzh) || ' - (' || TRIM(CAST(zh AS TEXT)) || ')' ELSE NULL END, CASE WHEN TRIM(nomah) != '' THEN TRIM(nomah) || ' - (' || TRIM(CAST(ah AS TEXT)) || ')' ELSE NULL END, 'Cuenca Sin Nombre') AS subc_lbl FROM cuencas")
                df_arbol = pd.read_sql(q_jerarquia, engine_geo)
                for c in df_arbol.columns: df_arbol[c] = df_arbol[c].astype(str).str.strip()
                
                df_hidro_completo = pd.merge(df_hist_pecuario, df_arbol.drop_duplicates(subset=['subc_lbl']), on='subc_lbl', how='left')
                
                niveles_hidro = ['nomah', 'nomzh', 'nom_szh', 'nom_nss1', 'nom_nss2', 'nom_nss3', 'subc_lbl']
                for col_nivel in niveles_hidro:
                    if col_nivel in df_hidro_completo.columns:
                        df_nivel = df_hidro_completo.dropna(subset=[col_nivel]).groupby([col_nivel, 'Anio'])[['Bovinos', 'Porcinos', 'Aves']].sum().reset_index()
                        for terr in df_nivel[col_nivel].unique():
                            if terr in ["", "None", "nan", "Cuenca Sin Nombre"]: continue
                            
                            nombre_puro_cuenca = str(terr).split(" - (")[0].strip() if " - (" in str(terr) else str(terr).strip()
                            nombre_puro_cuenca = re.sub(r'\s*-?\s*NSS\b', '', nombre_puro_cuenca, flags=re.IGNORECASE).strip()
                            
                            df_t = df_nivel[df_nivel[col_nivel] == terr].sort_values('Anio')
                            for esp in ['Bovinos', 'Porcinos', 'Aves']:
                                ajustar_modelos(df_t['Anio'].values, df_t[esp].values, 'CUENCA', nombre_puro_cuenca, esp)
                            cuencas_entrenadas.add(nombre_puro_cuenca)

                cuencas_totales = set(df_arbol['nomah'].dropna()) | set(df_arbol['nomzh'].dropna()) | set(df_arbol['nom_szh'].dropna()) | set(df_arbol['nom_nss1'].dropna()) | set(df_arbol['nom_nss2'].dropna()) | set(df_arbol['nom_nss3'].dropna()) | set(df_arbol['subc_lbl'].dropna())

                # 🚀 FIX: Aseguramos que TODAS las cuencas del archivo maestro entren al modelo
                cuencas_totales_norm = set()
                for c in cuencas_totales:
                    if pd.notna(c) and str(c).strip() not in ["", "None", "nan", "Cuenca Sin Nombre"]:
                        c_str = str(c)
                        c_norm = c_str.split(" - (")[0].strip() if " - (" in c_str else c_str.strip()
                        c_norm = re.sub(r'\s*-?\s*NSS\b', '', c_norm, flags=re.IGNORECASE).strip()
                        cuencas_totales_norm.add(c_norm)
                        
                cuencas_faltantes = cuencas_totales_norm - cuencas_entrenadas
                
                # Modelos de Cero Absoluto para las cuencas que no cruzaron con el ráster
                x_cero = np.array([2018, 2022, 2023, 2024, 2025])
                y_cero = np.array([0, 0, 0, 0, 0])
                
                for nombre_puro_cuenca in cuencas_faltantes:
                    if len(str(nombre_puro_cuenca).strip()) > 2:  # 🚀 FIX: Ignorar vacíos
                        for esp in ['Bovinos', 'Porcinos', 'Aves']:
                            ajustar_modelos(x_cero, y_cero, 'CUENCA', nombre_puro_cuenca, esp)

                # =================================================================
                # 🧠 ASIGNAR A MEMORIA RAM
                # =================================================================
                df_matriz_pec = pd.DataFrame(matriz_resultados)
                st.session_state['df_matriz_pecuaria'] = df_matriz_pec 
                
                barra_progreso.progress(1.0)
                texto_progreso.success(f"✅ ¡Cálculos finalizados! {len(df_matriz_pec)} modelos forjados en RAM. Ahora presiona el Botón Azul para inyectar a Supabase.")

        except Exception as e:
            st.error(f"🚨 Error Crítico en la Forja: {e}")

        # 🚀 FASE 3: EL BOTÓN AZUL (INYECCIÓN A SUPABASE)
        if 'df_matriz_pecuaria' in st.session_state and not st.session_state['df_matriz_pecuaria'].empty:
            st.markdown("### 💾 Guardado Definitivo en la Nube")
            st.info("💡 **Diagnóstico:** El sistema centralizado requiere que los datos existan como una Tabla SQL. Al inyectar, se creará la tabla maestra.")
            
            df_export = st.session_state['df_matriz_pecuaria'].copy()
            
            # 🚀 FIX 1: Limpieza Numérica Final Estricta
            cols_num = ['Log_K', 'Log_a', 'Log_r', 'Lin_m', 'Lin_b', 'Poblacion_Base', 'Año_Base', 'Log_R2', 'Lin_R2', 'Mejor_R2']
            for c in cols_num:
                if c in df_export.columns:
                    df_export[c] = pd.to_numeric(df_export[c].astype(str).str.replace(',', '').str.replace(r'\.(?=.*\.)', '', regex=True), errors='coerce').fillna(0.0)
            
            # 🚀 FIX 2: Forzar texto limpio para evitar bloqueos de SQLAlchemy
            cols_txt = ['Especie', 'Nivel', 'Territorio', 'LLAVE_UNIVERSAL', 'Modelo_Recomendado']
            for c in cols_txt:
                if c in df_export.columns:
                    df_export[c] = df_export[c].astype(str)

            col_b1, col_b2 = st.columns(2)
            
            with col_b1:
                csv_export = df_export.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 1. Descargar Respaldo (CSV Local)",
                    data=csv_export,
                    file_name="Matriz_Maestra_Pecuaria.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True
                )
            
            with col_b2:
                if st.button("🚀 2. Inyectar a Base de Datos SQL (Supabase)", use_container_width=True):
                    with st.spinner("Inyectando datos con Modo Autocommit activado..."):
                        try:
                            from modules.db_manager import get_engine
                            from sqlalchemy import text
                            engine_sql = get_engine()
                            
                            # Usamos una sola conexión blindada con AUTOCOMMIT para TODO
                            with engine_sql.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                                # 1. Vaciamos la tabla
                                conn.execute(text("TRUNCATE TABLE matriz_maestra_pecuaria;"))
                                
                                # 2. Inyectamos usando esa misma conexión para que Supabase no bloquee la transacción
                                df_export.to_sql('matriz_maestra_pecuaria', conn, if_exists='append', index=False, chunksize=500, method='multi')
                            
                            st.success("✅ ¡Inyección SQL exitosa! Los datos ya viven en Supabase.")
                            st.balloons()
                        except Exception as e:
                            st.error(f"❌ Falló la inyección SQL. Error: {e}")

# =====================================================================
# 🗺️ EXPLORADOR ESPACIAL PECUARIO (DENSIDAD Y TENDENCIAS)
# =====================================================================
st.markdown("---")
st.markdown("### 🗺️ Radiografía Espacial Pecuaria (Antioquia)")
st.info("Explora la distribución actual de cargas animales y las proyecciones de crecimiento para identificar los focos de presión territorial.")

especie_mapa = st.radio("🔍 Selecciona la especie a visualizar en los mapas:", ["Bovinos", "Porcinos", "Aves"], horizontal=True)

tab_mapa1, tab_mapa2 = st.tabs(["📍 Densidad Actual (Semáforo)", "📈 Tendencia de Crecimiento (Proyección)"])

with st.spinner(f"Renderizando inteligencia espacial para {especie_mapa}..."):
    try:
        import json
        import plotly.express as px
        
        q_mun_mapa = "SELECT * FROM municipios"
        gdf_mun_mapa = cargar_capa_espacial_cache(q_mun_mapa, geom_col="geometry")
        
        if gdf_mun_mapa is not None:
            if 'dpto_cnmbr' in gdf_mun_mapa.columns:
                gdf_mun_mapa = gdf_mun_mapa[gdf_mun_mapa['dpto_cnmbr'].str.contains('ANTIOQUIA', case=False, na=False)]
            col_m = next((c for c in ['nombre_municipio', 'mpio_cnmbr', 'MPIO_CNMBR', 'municipio'] if c in gdf_mun_mapa.columns), 'municipio')
            gdf_mun_mapa['mun_norm'] = gdf_mun_mapa[col_m].apply(limpiar_fuerte)
            
            # ==========================================
            # MAPA 1: DENSIDAD ACTUAL (ÚLTIMO CENSO)
            # ==========================================
            ultimo_anio = df_pecuario['Anio'].max()
            df_censo_mapa = df_pecuario[df_pecuario['Anio'] == ultimo_anio].copy()
            
            if 'Municipio_Norm' in df_censo_mapa.columns:
                df_censo_mapa['mun_norm'] = df_censo_mapa['Municipio_Norm'].apply(limpiar_fuerte)
                df_agrupado = df_censo_mapa.groupby('mun_norm')[especie_mapa].sum().reset_index()
                
                gdf_densidad = gdf_mun_mapa.merge(df_agrupado, on='mun_norm', how='left')
                gdf_densidad[especie_mapa] = gdf_densidad[especie_mapa].fillna(0)
                gdf_densidad = gdf_densidad.to_crs(epsg=4326).set_index('mun_norm')
                
                geojson_densidad = json.loads(gdf_densidad.to_json())
                
                fig_mapa1 = px.choropleth_mapbox(
                    gdf_densidad, geojson=geojson_densidad, locations=gdf_densidad.index,
                    color=especie_mapa, hover_name=col_m, hover_data={especie_mapa: ':,.0f'},
                    color_continuous_scale=["#27ae60", "#f1c40f", "#e74c3c"],
                    mapbox_style="carto-positron", zoom=6.2, center={"lat": 6.55, "lon": -75.3},
                    opacity=0.75, labels={especie_mapa: f"Cabezas ({ultimo_anio})"}
                )
                fig_mapa1.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
                
                with tab_mapa1:
                    st.plotly_chart(fig_mapa1, use_container_width=True)

            # ==========================================
            # MAPA 2: TENDENCIAS DE CRECIMIENTO
            # ==========================================
            df_mat = st.session_state.get('df_matriz_pecuaria', pd.DataFrame())
            
            with tab_mapa2:
                if not df_mat.empty:
                    def col(nombre):
                        return next((c for c in df_mat.columns if c.lower() == nombre.lower()), None)
                        
                    c_nivel = col('Nivel')
                    c_especie = col('Especie')
                    c_terr = col('Territorio')
                    
                    if c_nivel and c_especie:
                        df_mun_modelos = df_mat[(df_mat[c_nivel].str.upper().str.strip() == 'MUNICIPAL') & 
                                                (df_mat[c_especie].str.upper().str.strip() == especie_mapa.upper())].copy()
                        
                        if not df_mun_modelos.empty:
                            def calc_proy(row, destino):
                                x_norm = destino - row.get(col('Año_Base') or 'Año_Base', 2018)
                                mod_rec = row.get(col('Modelo_Recomendado') or 'Modelo_Recomendado', 'Lineal')
                                
                                if mod_rec == 'Logístico' and row.get(col('Log_K') or 'Log_K', 0) > 0:
                                    v = row[col('Log_K') or 'Log_K'] / (1 + row.get(col('Log_a') or 'Log_a', 1) * np.exp(-row.get(col('Log_r') or 'Log_r', 0) * x_norm))
                                else:
                                    v = row.get(col('Lin_m') or 'Lin_m', 0) * x_norm + row.get(col('Lin_b') or 'Lin_b', 0)
                                if pd.isna(v): v = 0
                                return max(0, v)
                            
                            if c_terr:
                                df_mun_modelos['mun_norm'] = df_mun_modelos[c_terr].apply(limpiar_fuerte)
                            else:
                                c_llave = col('LLAVE_UNIVERSAL')
                                if c_llave:
                                    df_mun_modelos['mun_norm'] = df_mun_modelos[c_llave].apply(lambda x: str(x).split('_')[1] if len(str(x).split('_'))>1 else str(x))
                                else:
                                    df_mun_modelos['mun_norm'] = df_mun_modelos.iloc[:, 2].apply(limpiar_fuerte)
                                
                            df_mun_modelos['Proyeccion'] = df_mun_modelos.apply(lambda r: calc_proy(r, anio_destino), axis=1)
                            
                            c_pob = col('Poblacion_Base') or 'Poblacion_Base'
                            df_mun_modelos['Pob_Base_Segura'] = df_mun_modelos.get(c_pob, 0)
                            
                            df_mun_modelos['Delta'] = df_mun_modelos['Proyeccion'] - df_mun_modelos['Pob_Base_Segura']
                            df_mun_modelos['Delta_Pct'] = np.where(df_mun_modelos['Pob_Base_Segura'] > 0, (df_mun_modelos['Delta'] / df_mun_modelos['Pob_Base_Segura']) * 100, 0)
                            
                            condiciones = [df_mun_modelos['Delta_Pct'] > 2.5, df_mun_modelos['Delta_Pct'] < -2.5]
                            opciones = ['📈 Crecimiento (Mayor Presión)', '📉 Decrecimiento (Alivio Hídrico)']
                            df_mun_modelos['Tendencia'] = np.select(condiciones, opciones, default='⚖️ Estable')
                            
                            gdf_tendencia = gdf_mun_mapa.merge(df_mun_modelos[['mun_norm', 'Proyeccion', 'Delta', 'Delta_Pct', 'Tendencia']], on='mun_norm', how='inner')
                            
                            if not gdf_tendencia.empty:
                                gdf_tendencia = gdf_tendencia.to_crs(epsg=4326).set_index('mun_norm')
                                geojson_tend = json.loads(gdf_tendencia.to_json())
                                
                                color_discrete_map = {
                                    '📈 Crecimiento (Mayor Presión)': '#e74c3c', 
                                    '📉 Decrecimiento (Alivio Hídrico)': '#27ae60', 
                                    '⚖️ Estable': '#f1c40f'
                                }
                                
                                fig_mapa2 = px.choropleth_mapbox(
                                    gdf_tendencia, geojson=geojson_tend, locations=gdf_tendencia.index, color='Tendencia',
                                    hover_name=col_m,
                                    hover_data={'Tendencia': True, 'Proyeccion': ':,.0f', 'Delta': ':,.0f', 'Delta_Pct': ':.1f%'},
                                    color_discrete_map=color_discrete_map,
                                    mapbox_style="carto-positron", zoom=6.2, center={"lat": 6.55, "lon": -75.3}, opacity=0.75
                                )
                                fig_mapa2.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                                
                                st.plotly_chart(fig_mapa2, use_container_width=True)
                            else:
                                st.warning("⚠️ No se logró sincronizar la geometría con las predicciones. Intenta recargar la página.")
                        else:
                            st.info("⚠️ No hay modelos municipales entrenados para calcular tendencias en esta especie.")
                    else:
                        st.error("⚠️ La matriz no tiene el formato esperado. Por favor, forja e inyecta de nuevo los modelos.")
                else:
                    st.warning("⚠️ No hay modelos en memoria. Usa el 'Entrenador de Modelos' para iniciar el análisis.")

    except Exception as e:
        st.error(f"Error generando el motor espacial: {e}")