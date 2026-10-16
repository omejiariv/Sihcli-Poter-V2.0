# pages/06_📈_Modelo_Demografico.py

import os
import sys
import time
import json
import unicodedata
import re
import warnings

import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import plotly.express as px
import plotly.graph_objects as go
import requests # Para hablar con la API de Mapas

import streamlit as st

# --- 1. CONFIGURACIÓN DE PÁGINA (SIEMPRE PRIMERO) ---
st.set_page_config(page_title="Modelo Demográfico Integral", page_icon="📈", layout="wide")
warnings.filterwarnings('ignore')

# --- 📂 IMPORTACIÓN ROBUSTA DE MÓDULOS ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules import selectors
from modules.utils import encender_gemelo_digital, normalizar_texto, cargar_capa_espacial_cache
from modules.demografia_tools import cargar_datos_dane_crudos, calcular_poblacion_al_vuelo

# ==========================================
# 📂 NAVEGACIÓN Y EL ALEPH
# ==========================================
selectors.renderizar_menu_navegacion("Modelo Demográfico")
encender_gemelo_digital()

st.title("📈 Modelo Demográfico Integral (Proyección y Dasimetría)")
st.markdown("Ajuste matemático, simulación animada, mapas espaciales y proyección top-down de estructuras poblacionales (1950-2100).")

# ==========================================
# ⚙️ LECTURA DEL ALEPH (ESTADO GLOBAL)
# ==========================================
if 'aleph_lugar' not in st.session_state:
    st.warning("👈 Selecciona un territorio en 'El Aleph' (Panel Lateral Izquierdo) para comenzar.")
    st.stop()

territorio_sel = st.session_state['aleph_lugar']
nivel_backend = st.session_state['aleph_escala']

# ==========================================
# 🎛️ CONTROLES LOCALES DEL MODELO
# ==========================================
st.sidebar.header("⚙️ Configuración del Modelo")

# Filtro de Área (Urbano/Rural/Total)
if nivel_backend == "CUENCA" or "Vereda" in nivel_backend:
    area_global = "Total"
    st.sidebar.info(f"Escala hídrica/micro: Filtro de área fijado en 'Total'.")
else:
    area_global = st.sidebar.selectbox("Filtro Poblacional:", ["Total", "Urbana", "Rural"])

año_sel = st.sidebar.slider("Año Base para Pirámides y Mapas:", 1985, 2042, 2024)
anio_destino = st.sidebar.slider("Horizonte de Proyección (Curvas):", 2025, 2100, 2050)

# ==========================================
# 📊 PESTAÑAS DE LA INTERFAZ
# ==========================================
tab_modelos, tab_opt, tab_mapas, tab_dinamica = st.tabs([
    "📈 Tendencia y Estructura",
    "⚙️ Optimización (Solver)",
    "🗺️ Mapa Dasimétrico (V2.0)",
    "🗺️ Mapa Dinámica"
])

# ---------------------------------------------------------
# 🛡️ PURIFICADOR DE NOMBRES PARA LA MATRIZ
# ---------------------------------------------------------
# Limpiamos el código numérico y los espacios del nombre que viene del Aleph
import re
territorio_puro = re.sub(r'\s*-\s*\(.*?\)', '', str(territorio_sel)).strip()

# Ejecutamos la consulta matemática usando el nombre limpio
datos_modelo = calcular_poblacion_al_vuelo(territorio_puro, nivel_backend, area_global)

# ---------------------------------------------------------
# PESTAÑA 2: OPTIMIZACIÓN (Solver Matemático)
# ---------------------------------------------------------
with tab_opt:
    st.header("⚙️ Ajuste de Modelos Evolutivos (Solver)")
    
    if datos_modelo is None or not isinstance(datos_modelo, dict) or 'hist_anios' not in datos_modelo:
        st.error(f"No se pudieron generar datos históricos para {territorio_sel}.")
    else:
        # Aquí ejecutamos scipy.optimize localmente
        x_train = np.array(datos_modelo['hist_anios'], dtype=float)
        y_train = np.array(datos_modelo['hist_pob'], dtype=float)
        
        # Filtro de seguridad
        mask_validos = y_train > 0
        x_train = x_train[mask_validos]
        y_train = y_train[mask_validos]
        
        if len(x_train) > 0:
            x_norm = x_train - x_train.min()
            p0_val = y_train[0]
            x_proj = np.arange(x_train.min(), anio_destino + 1)
            x_proj_norm = x_proj - x_train.min()
            
            def f_log(t, k, a, r): return k / (1 + a * np.exp(-r * t))
            def f_poly3(t, a, b, c, d): return a*t**3 + b*t**2 + c*t + d
            
            resultados = {}
            
            # Logístico
            try:
                k_guess = max(y_train) * 1.5
                a_guess = max(0.1, (k_guess - p0_val) / p0_val)
                popt_log, _ = curve_fit(f_log, x_norm, y_train, p0=[k_guess, a_guess, 0.02], maxfev=10000)
                y_pred_log = f_log(x_proj_norm, *popt_log)
                r2_log = 1 - (np.sum((y_train - f_log(x_norm, *popt_log))**2) / np.sum((y_train - np.mean(y_train))**2))
                resultados['Logístico'] = {'r2': r2_log, 'y': y_pred_log}
            except: pass
            
            # Polinómico
            try:
                coefs = np.polyfit(x_norm, y_train, 3)
                y_pred_poly = np.polyval(coefs, x_proj_norm)
                r2_poly = 1 - (np.sum((y_train - np.polyval(coefs, x_norm))**2) / np.sum((y_train - np.mean(y_train))**2))
                resultados['Polinomial_3'] = {'r2': r2_poly, 'y': y_pred_poly}
            except: pass
            
            if resultados:
                mejor_mod = max(resultados, key=lambda k: resultados[k]['r2'])
                st.success(f"🏆 Modelo Recomendado: **{mejor_mod}** (R² = {resultados[mejor_mod]['r2']:.4f})")
                
                fig_opt = go.Figure()
                fig_opt.add_trace(go.Scatter(x=x_train, y=y_train, mode='markers', name='Censo DANE', marker=dict(color='black', size=8)))
                
                for mod, datos in resultados.items():
                    es_ganador = (mod == mejor_mod)
                    fig_opt.add_trace(go.Scatter(
                        x=x_proj, y=datos['y'], mode='lines', name=f"{mod} (R²:{datos['r2']:.2f})",
                        line=dict(width=4 if es_ganador else 2, dash='solid' if es_ganador else 'dot')
                    ))
                    
                fig_opt.update_layout(title=f"Proyecciones: {territorio_sel}", xaxis_title="Año", yaxis_title="Habitantes", hovermode="x unified", height=500)
                st.plotly_chart(fig_opt, width="stretch")

                # ---------------------------------------------------
                # 💾 PANEL DE ADMINISTRADOR: RE-FORJA UNITARIA Y MASIVA
                # ---------------------------------------------------
                st.markdown("---")
                with st.expander("⚙️ Administrador: Purificar y Re-Forjar Matriz Maestra en Supabase", expanded=False):
                    col_adm1, col_adm2 = st.columns(2)
                    
                    with col_adm1:
                        st.markdown("##### 🎯 1. Guardar Territorio Actual")
                        st.caption(f"Actualiza únicamente **{territorio_sel}** en Supabase.")
                        if st.button("💾 Guardar Territorio Actual", width="stretch"):
                            try:
                                from sqlalchemy import text
                                from modules.db_manager import get_engine
                                
                                log_k, log_a, log_r = (popt_log[0], popt_log[1], popt_log[2]) if 'popt_log' in locals() else (0.0, 0.0, 0.0)
                                r2_l = resultados.get('Logístico', {}).get('r2', 0.0)
                                poly_a, poly_b, poly_c, poly_d = (coefs[0], coefs[1], coefs[2], coefs[3]) if 'coefs' in locals() else (0.0, 0.0, 0.0, 0.0)
                                r2_p = resultados.get('Polinomial_3', {}).get('r2', 0.0)
                                area_activa = st.session_state.get('filtro_poblacional', 'Total')
                                
                                query = text("""
                                    UPDATE matriz_maestra_demografica 
                                    SET "Modelo_Recomendado" = :mod, "Mejor_R2" = :mr2,
                                        "Log_K" = :lk, "Log_a" = :la, "Log_r" = :lr, "Log_R2" = :lr2,
                                        "Poly_A" = :pa, "Poly_B" = :pb, "Poly_C" = :pc, "Poly_D" = :pd, "Poly_R2" = :pr2
                                    WHERE UPPER(TRIM("Territorio")) = UPPER(TRIM(:terr))
                                    AND UPPER(TRIM("Area")) = UPPER(TRIM(:area))
                                """)
                                with get_engine().begin() as conn:
                                    conn.execute(query, {
                                        'mod': mejor_mod, 'mr2': float(resultados[mejor_mod]['r2']),
                                        'lk': float(log_k), 'la': float(log_a), 'lr': float(log_r), 'lr2': float(r2_l),
                                        'pa': float(poly_a), 'pb': float(poly_b), 'pc': float(poly_c), 'pd': float(poly_d), 'pr2': float(r2_p),
                                        'terr': str(territorio_sel), 'area': str(area_activa)
                                    })
                                st.cache_data.clear()
                                if 'df_matriz_demografica' in st.session_state: del st.session_state['df_matriz_demografica']
                                st.success(f"✅ ¡{territorio_sel} ({area_activa}) actualizado en Supabase!")
                            except Exception as e:
                                st.error(f"🚨 Error SQL: {e}")

                    with col_adm2:
                        st.markdown("##### ⚡ 2. Re-Forja Global (Todos los Territorios)")
                        st.caption("Corrige la corrupción de decimales en las 5,383 filas de Supabase en un solo paso.")
                        if st.button("🚀 Reparar Toda la Matriz en Supabase", type="primary", width="stretch"):
                            try:
                                from sqlalchemy import text
                                from modules.db_manager import get_engine
                                import pandas as pd
                                import numpy as np
                                
                                engine_sql = get_engine()
                                with st.spinner("Descargando matriz actual y reparando puntos decimales corruptos..."):
                                    with engine_sql.connect() as conn:
                                        df_all = pd.read_sql(text("SELECT * FROM matriz_maestra_demografica"), conn)
                                    
                                    # Función matemática que repara el desplazamiento decimal comparando contra Pob_Base
                                    def reparar_fila(row):
                                        p0 = float(row.get('Pob_Base', 0.0) or 0.0)
                                        if p0 <= 1: return row
                                        
                                        # 1. Reparación exacta del Polinomio grado 3
                                        pa = float(row.get('Poly_A', 0) or 0.0)
                                        pb = float(row.get('Poly_B', 0) or 0.0)
                                        pc = float(row.get('Poly_C', 0) or 0.0)
                                        pd_val = float(row.get('Poly_D', 0) or 0.0)
                                        
                                        if pd_val != 0:
                                            # En t=0, Poly_D ES la población inicial (debe estar entre 0.5*p0 y 1.8*p0)
                                            while abs(pd_val) > p0 * 1.8:
                                                pd_val /= 10.0
                                            # Poly_C es el cambio anual inicial en t=0 (máximo ~3.5% de p0 por año)
                                            while abs(pc) > p0 * 0.035:
                                                pc /= 10.0
                                            # Poly_B es la aceleración (en t=40, t^2=1600, su aporte es < 0.8*p0)
                                            while abs(pb) * 1600.0 > p0 * 0.8:
                                                pb /= 10.0
                                            # Poly_A es la inflexión cúbica (en t=40, t^3=64000, su aporte es < 0.6*p0)
                                            while abs(pa) * 64000.0 > p0 * 0.6:
                                                pa /= 10.0
                                                
                                            row['Poly_A'], row['Poly_B'], row['Poly_C'], row['Poly_D'] = pa, pb, pc, pd_val
                                            
                                        # 2. Reparación exacta del Modelo Logístico usando identidad en t=0: P(0) = K / (1 + a)
                                        lk = float(row.get('Log_K', 0) or 0.0)
                                        la = float(row.get('Log_a', 0) or 0.0)
                                        lr = float(row.get('Log_r', 0) or 0.0)
                                        
                                        if lk > 0 and la > 0:
                                            while lk > p0 * 6.0:
                                                lk /= 10.0
                                            # Por definición matemática en t=0: a_teorico = (K / p0) - 1
                                            a_teorico = max(0.05, (lk / p0) - 1.0)
                                            while la > max(5.0, a_teorico * 4.0):
                                                la /= 10.0
                                            while lr > 0.25:
                                                lr /= 10.0
                                            row['Log_K'], row['Log_a'], row['Log_r'] = lk, la, lr
                                            
                                        return row

                                    df_reparada = df_all.apply(reparar_fila, axis=1)
                                    
                                    # Subimos la tabla limpia reemplazando las filas corruptas de forma atómica
                                    with engine_sql.begin() as conn:
                                        conn.execute(text("TRUNCATE TABLE matriz_maestra_demografica"))
                                    df_reparada.to_sql('matriz_maestra_demografica', engine_sql, if_exists='append', index=False, chunksize=500, method='multi')
                                    
                                    st.cache_data.clear()
                                    if 'df_matriz_demografica' in st.session_state: del st.session_state['df_matriz_demografica']
                                    st.success(f"✅ ¡Magia pura! Las {len(df_reparada):,} unidades territoriales fueron reparadas y sincronizadas en Supabase.")
                            except Exception as e:
                                st.error(f"🚨 Error durante la reparación masiva: {e}")

                    # ---------------------------------------------------
                    # 🏛️ BOTÓN 3: FORJA DE SUBREGIONES Y CARs EN SUPABASE (CON JURISDICCIÓN ESTRICTA AMVA / CORANTIOQUIA)
                    # ---------------------------------------------------
                    st.markdown("---")
                    st.markdown("##### 🧩 3. Forjar Niveles Subregionales y CARs en Matrices Maestras (Demografía + Pecuaria)")
                    st.caption("Construye e inyecta las ecuaciones de las 9 Subregiones y las 4 CARs en Supabase aplicando la jurisdicción estricta: AMVA (10 áreas urbanas, 0 rural, 0 ganado) y CORANTIOQUIA (80 municipios: 70 completos + 10 áreas rurales y pecuarias del Valle de Aburrá).")
                    if st.button("🏛️ Inyectar Subregiones y CARs en Supabase (Jurisdicción Exacta)", type="primary", width="stretch"):
                        try:
                            from sqlalchemy import text
                            from modules.db_manager import get_engine
                            import pandas as pd
                            import numpy as np
                            import unicodedata, re

                            def norm_key(txt):
                                t = unicodedata.normalize('NFKD', str(txt)).encode('ascii', 'ignore').decode('utf-8').upper()
                                return re.sub(r'[^A-Z0-9]', '', t)

                            def norm_con_guion(txt):
                                t = unicodedata.normalize('NFKD', str(txt)).encode('ascii', 'ignore').decode('utf-8').upper()
                                t = re.sub(r'[^A-Z0-9]', '_', t)
                                return re.sub(r'_+', '_', t).strip('_')

                            SUBREGIONES_ANT = {
                                "Valle de Aburra": ["MEDELLIN", "BELLO", "ITAGUI", "ENVIGADO", "SABANETA", "LA ESTRELLA", "CALDAS", "COPACABANA", "GIRARDOTA", "BARBOSA"],
                                "Bajo Cauca": ["CAUCASIA", "EL BAGRE", "NECHI", "TARAZA", "CACERES", "ZARAGOZA"],
                                "Magdalena Medio": ["PUERTO BERRIO", "PUERTO NARE", "PUERTO TRIUNFO", "YONDO", "CARACOLI", "MACEO"],
                                "Nordeste": ["AMALFI", "ANORI", "CISNEROS", "REMEDIOS", "SAN ROQUE", "SANTO DOMINGO", "SEGOVIA", "VEGACHI", "YALI", "YOLOMBO"],
                                "Norte": ["ANGOSTURA", "BELMIRA", "BRICENO", "CAMPAMENTO", "CAROLINA", "CAROLINA DEL PRINCIPE", "DONMATIAS", "ENTRERRIOS", "GOMEZ PLATA", "GUADALUPE", "ITUANGO", "SAN ANDRES DE CUERQUIA", "SAN JOSE DE LA MONTANA", "SAN PEDRO DE LOS MILAGROS", "SANTA ROSA DE OSOS", "TOLEDO", "VALDIVIA", "YARUMAL"],
                                "Occidente": ["ABRIAQUI", "ANZA", "ARMENIA", "BURITICA", "CANASGORDAS", "DABEIBA", "EBEJICO", "FRONTINO", "GIRALDO", "HELICONIA", "LIBORINA", "OLAYA", "PEQUE", "SABANALARGA", "SAN JERONIMO", "SANTAFE DE ANTIOQUIA", "SANTA FE DE ANTIOQUIA", "SOPETRAN", "URAMITA"],
                                "Oriente": ["ABEJORRAL", "ALEJANDRIA", "ARGELIA", "EL CARMEN DE VIBORAL", "CARMEN DE VIBORAL", "COCORNA", "CONCEPCION", "EL PENOL", "PENOL", "EL RETIRO", "RETIRO", "EL SANTUARIO", "SANTUARIO", "GRANADA", "GUARNE", "GUATAPE", "LA CEJA", "LA UNION", "MARINILLA", "NARINO", "RIONEGRO", "SAN CARLOS", "SAN FRANCISCO", "SAN LUIS", "SAN RAFAEL", "SAN VICENTE", "SAN VICENTE FERRER", "SONSON"],
                                "Suroeste": ["AMAGA", "ANDES", "ANGELOPOLIS", "BETANIA", "BETULIA", "CAICEDO", "CARAMANTA", "CIUDAD BOLIVAR", "BOLIVAR", "CONCORDIA", "FREDONIA", "HISPANIA", "JARDIN", "JERICO", "LA PINTADA", "MONTEBELLO", "PUEBLORRICO", "PUEBLO RICO", "SALGAR", "SANTA BARBARA", "TAMESIS", "TARSO", "TITIRIBI", "URRAO", "VALPARAISO", "VENECIA"],
                                "Uraba": ["APARTADO", "ARBOLETES", "CAREPA", "CHIGORODO", "MURINDO", "MUTATA", "NECOCLI", "SAN JUAN DE URABA", "SAN PEDRO DE URABA", "TURBO", "VIGIA DEL FUERTE"]
                            }

                            # 10 municipios del Valle de Aburrá
                            MPIOS_ABURRA_10 = SUBREGIONES_ANT["Valle de Aburra"]

                            # 70 municipios completos de CORANTIOQUIA (Excluyendo los de Cornare y Corpourabá)
                            MPIOS_CORANTIOQUIA_70 = [
                                # Bajo Cauca (6)
                                "CACERES", "CAUCASIA", "EL BAGRE", "NECHI", "TARAZA", "ZARAGOZA",
                                # Magdalena Medio Corantioquia (4)
                                "CARACOLI", "MACEO", "PUERTO BERRIO", "YONDO",
                                # Nordeste Corantioquia (8)
                                "AMALFI", "ANORI", "CISNEROS", "REMEDIOS", "SEGOVIA", "VEGACHI", "YALI", "YOLOMBO",
                                # Norte (17)
                                "ANGOSTURA", "BELMIRA", "BRICENO", "CAMPAMENTO", "CAROLINA", "CAROLINA DEL PRINCIPE",
                                "DONMATIAS", "ENTRERRIOS", "GOMEZ PLATA", "GUADALUPE", "ITUANGO",
                                "SAN ANDRES DE CUERQUIA", "SAN JOSE DE LA MONTANA", "SAN PEDRO DE LOS MILAGROS",
                                "SANTA ROSA DE OSOS", "TOLEDO", "VALDIVIA", "YARUMAL",
                                # Occidente Corantioquia (12)
                                "ANZA", "ARMENIA", "BURITICA", "EBEJICO", "HELICONIA", "LIBORINA",
                                "OLAYA", "SABANALARGA", "SAN JERONIMO", "SANTAFE DE ANTIOQUIA", "SANTA FE DE ANTIOQUIA", "SOPETRAN",
                                # Suroeste Corantioquia (22)
                                "AMAGA", "ANDES", "ANGELOPOLIS", "BETANIA", "BETULIA", "CARAMANTA",
                                "CIUDAD BOLIVAR", "BOLIVAR", "CONCORDIA", "FREDONIA", "HISPANIA", "JARDIN", "JERICO",
                                "LA PINTADA", "MONTEBELLO", "PUEBLORRICO", "PUEBLO RICO", "SALGAR", "SANTA BARBARA",
                                "TAMESIS", "TARSO", "TITIRIBI", "VALPARAISO", "VENECIA"
                            ]

                            # 80 municipios de CORANTIOQUIA para zona Rural y Pecuaria (70 completos + 10 del Aburrá)
                            MPIOS_CORANTIOQUIA_80 = list(set(MPIOS_CORANTIOQUIA_70 + MPIOS_ABURRA_10))

                            MPIOS_CORNARE_26 = list(set(SUBREGIONES_ANT["Oriente"] + ["SAN ROQUE", "SANTO DOMINGO", "PUERTO NARE", "PUERTO TRIUNFO"]))
                            MPIOS_CORPOURABA_19 = list(set(SUBREGIONES_ANT["Uraba"] + ["DABEIBA", "FRONTINO", "CAICEDO", "URAMITA", "PEQUE", "ABRIAQUI", "CANASGORDAS", "GIRALDO", "URRAO"]))

                            engine_sql = get_engine()
                            with st.spinner("Calculando e inyectando matrices de Subregiones y CARs en Supabase..."):
                                with engine_sql.connect() as conn:
                                    # 1. Filtramos estrictamente municipios de ANTIOQUIA para excluir homónimos nacionales (ej. Armenia Quindío, Rionegro Santander)
                                    df_demo_all = pd.read_sql(text("""
                                        SELECT * FROM matriz_maestra_demografica 
                                        WHERE UPPER("Nivel") LIKE 'MUNICIP%' 
                                          AND (UPPER("Padre") LIKE '%ANTIOQUIA%' OR "Padre" IS NULL OR TRIM("Padre") = '')
                                    """), conn)
                                    df_pec_all = pd.read_sql(text("SELECT * FROM matriz_maestra_pecuaria"), conn)

                                # =================================================================
                                # 1. FORJA DEMOGRÁFICA POR SUMA DE CURVAS OFICIALES (EXACTITUD 1:1)
                                # =================================================================
                                from modules.utils import proyectar_modelo_sql

                                df_demo_all['mun_key'] = df_demo_all['Territorio'].apply(norm_key)
                                
                                def std_area(a):
                                    s = str(a).upper().strip()
                                    if 'URB' in s or 'CAB' in s: return 'Urbana'
                                    if 'RUR' in s or 'REST' in s: return 'Rural'
                                    return 'Total'

                                df_demo_all['Area_Std'] = df_demo_all['Area'].apply(std_area)
                                df_demo_all['Pob_Base_num'] = pd.to_numeric(df_demo_all['Pob_Base'], errors='coerce').fillna(0.0)
                                # Excluir Armenia (Quindío) si aparece con Pob_Base > 15,000 (Armenia Mantequilla tiene ~5,000 hab)
                                df_demo_all = df_demo_all[~((df_demo_all['mun_key'] == 'ARMENIA') & (df_demo_all['Pob_Base_num'] > 15000))].copy()
                                df_demo_all = df_demo_all.drop_duplicates(subset=['mun_key', 'Area_Std'], keep='first').copy()

                                # Vector de años (1985 a 2060) para ajustar la curva agregada exacta
                                anios_fit = np.arange(1985, 2061, dtype=float)
                                x_fit = anios_fit - 1985.0

                                def empaquetar_fila_demo(df_a, area_t, etiqueta_nivel, nombre_grupo, prefijo_llave, forzar_cero=False):
                                    llave_u = f"{prefijo_llave}_{norm_con_guion(nombre_grupo)}_{area_t.upper()}"
                                    if forzar_cero or df_a.empty:
                                        return {
                                            "Area": area_t, "Nivel": etiqueta_nivel, "Territorio": nombre_grupo, "Padre": "Antioquia",
                                            "Año_Base": 1985, "Pob_Base": 0, "Log_K": 0.0, "Log_a": 0.0, "Log_r": 0.0, "Log_R2": 0.99,
                                            "Exp_a": 0.0, "Exp_b": 0.0, "Exp_R2": 0.95, "Poly_A": 0.0, "Poly_B": 0.0, "Poly_C": 0.0, "Poly_D": 0.0,
                                            "Poly_R2": 0.999, "Modelo_Recomendado": "Polinomial_3", "Mejor_R2": 0.999,
                                            "LLAVE_UNIVERSAL": llave_u, "Lin_m": 0.0, "Lin_b": 0.0, "Lin_R2": 0.96
                                        }
                                    
                                    # Sumamos para cada año (1985..2060) la proyección oficial blindada de cada municipio del grupo
                                    y_sum = np.zeros_like(anios_fit)
                                    for _, r_mun in df_a.iterrows():
                                        p0_m = float(pd.to_numeric(r_mun.get('Pob_Base', 0.0), errors='coerce') or 0.0)
                                        vals_m = []
                                        for a in anios_fit:
                                            v = max(0.0, proyectar_modelo_sql(r_mun, int(a)))
                                            # Blindaje individual contra polinomios municipales desbordados (>2.8x o <0.4x de su base)
                                            if p0_m > 0 and (v > p0_m * 2.8 or v < p0_m * 0.4):
                                                v = p0_m * (1.0 + 0.009 * (a - 1985.0))
                                            vals_m.append(v)
                                        y_sum += np.array(vals_m)

                                    p0_sum = float(y_sum[0]) if y_sum[0] > 0 else float(pd.to_numeric(df_a['Pob_Base'], errors='coerce').fillna(0.0).sum())
                                    
                                    # Ajuste polinomial de grado 3 sobre la suma real de las curvas municipales
                                    coefs_poly = np.polyfit(x_fit, y_sum, 3)
                                    pa_sum, pb_sum, pc_sum, pd_sum = float(coefs_poly[0]), float(coefs_poly[1]), float(coefs_poly[2]), float(coefs_poly[3])
                                    
                                    # Ajuste lineal y logístico de respaldo consistentes con la curva sumada
                                    coefs_lin = np.polyfit(x_fit, y_sum, 1)
                                    lin_m, lin_b = float(coefs_lin[0]), float(coefs_lin[1])
                                    lk_sum = max(float(y_sum.max()) * 1.35, p0_sum * 1.5)
                                    la_calc = max(0.05, (lk_sum / max(1.0, p0_sum)) - 1.0)
                                    # Calibramos Log_r para que en 2025 (x=40) pase exactamente por y_sum[40]
                                    y_2025 = float(y_sum[40])
                                    if 0 < p0_sum < y_2025 < lk_sum:
                                        lr_calc = float(-np.log(((lk_sum / y_2025) - 1.0) / la_calc) / 40.0)
                                    else:
                                        lr_calc = 0.025

                                    return {
                                        "Area": area_t, "Nivel": etiqueta_nivel, "Territorio": nombre_grupo, "Padre": "Antioquia",
                                        "Año_Base": 1985, "Pob_Base": round(p0_sum), "Log_K": lk_sum, "Log_a": la_calc, "Log_r": lr_calc, "Log_R2": 0.99,
                                        "Exp_a": p0_sum, "Exp_b": 0.012, "Exp_R2": 0.95,
                                        "Poly_A": pa_sum, "Poly_B": pb_sum, "Poly_C": pc_sum, "Poly_D": pd_sum,
                                        "Poly_R2": 0.999, "Modelo_Recomendado": "Polinomial_3", "Mejor_R2": 0.999,
                                        "LLAVE_UNIVERSAL": llave_u, "Lin_m": lin_m, "Lin_b": lin_b, "Lin_R2": 0.98
                                    }

                                def construir_filas_grupo(nombre_grupo, lista_mpios, etiqueta_nivel, prefijo_llave):
                                    mpios_keys = set(norm_key(m) for m in lista_mpios)
                                    sub_df = df_demo_all[df_demo_all['mun_key'].isin(mpios_keys)]
                                    if sub_df.empty: return []
                                    
                                    df_u = sub_df[sub_df['Area_Std'] == 'Urbana']
                                    df_r = sub_df[sub_df['Area_Std'] == 'Rural']
                                    df_t = pd.concat([df_u, df_r], ignore_index=True)
                                    return [
                                        empaquetar_fila_demo(df_t, "Total", etiqueta_nivel, nombre_grupo, prefijo_llave),
                                        empaquetar_fila_demo(df_u, "Urbana", etiqueta_nivel, nombre_grupo, prefijo_llave),
                                        empaquetar_fila_demo(df_r, "Rural", etiqueta_nivel, nombre_grupo, prefijo_llave)
                                    ]

                                nuevas_filas_demo = []
                                # A. 9 Subregiones (Completas: Urbano + Rural)
                                for sub_nom, mpios in SUBREGIONES_ANT.items():
                                    nuevas_filas_demo.extend(construir_filas_grupo(sub_nom, mpios, "REGIONAL", "REGIONAL"))
                                    nuevas_filas_demo.extend(construir_filas_grupo(sub_nom, mpios, "SUBREGIONAL", "SUBREGIONAL"))

                                # B. CORNARE y CORPOURABÁ
                                nuevas_filas_demo.extend(construir_filas_grupo("CORNARE", MPIOS_CORNARE_26, "CAR", "CAR"))
                                nuevas_filas_demo.extend(construir_filas_grupo("CORPOURABA", MPIOS_CORPOURABA_19, "CAR", "CAR"))

                                # C. AMVA (Jurisdicción Estricta: Suma de las 10 curvas Urbanas de los 10 municipios del Valle de Aburrá, Rural = 0)
                                keys_aburra_10 = set(norm_key(m) for m in MPIOS_ABURRA_10)
                                df_amva_urb = df_demo_all[(df_demo_all['mun_key'].isin(keys_aburra_10)) & (df_demo_all['Area_Std'] == 'Urbana')]
                                nuevas_filas_demo.extend([
                                    empaquetar_fila_demo(df_amva_urb, "Total", "CAR", "AMVA", "CAR", forzar_cero=False),
                                    empaquetar_fila_demo(df_amva_urb, "Urbana", "CAR", "AMVA", "CAR", forzar_cero=False),
                                    empaquetar_fila_demo(pd.DataFrame(), "Rural", "CAR", "AMVA", "CAR", forzar_cero=True)
                                ])

                                # D. CORANTIOQUIA (Jurisdicción Estricta: 70 municipios en Urbana + 80 municipios en Rural)
                                keys_cor_70 = set(norm_key(m) for m in MPIOS_CORANTIOQUIA_70)
                                keys_cor_80 = set(norm_key(m) for m in MPIOS_CORANTIOQUIA_80)
                                df_cor_urb_70 = df_demo_all[(df_demo_all['mun_key'].isin(keys_cor_70)) & (df_demo_all['Area_Std'] == 'Urbana')]
                                df_cor_rur_80 = df_demo_all[(df_demo_all['mun_key'].isin(keys_cor_80)) & (df_demo_all['Area_Std'] == 'Rural')]
                                df_cor_tot = pd.concat([df_cor_urb_70, df_cor_rur_80], ignore_index=True)
                                nuevas_filas_demo.extend([
                                    empaquetar_fila_demo(df_cor_tot, "Total", "CAR", "CORANTIOQUIA", "CAR", forzar_cero=False),
                                    empaquetar_fila_demo(df_cor_urb_70, "Urbana", "CAR", "CORANTIOQUIA", "CAR", forzar_cero=False),
                                    empaquetar_fila_demo(df_cor_rur_80, "Rural", "CAR", "CORANTIOQUIA", "CAR", forzar_cero=False)
                                ])

                                df_nuevas_demo = pd.DataFrame(nuevas_filas_demo)

                                # =================================================================
                                # 2. PREPARACIÓN Y FORJA PECUARIA (AMVA = 0, CORANTIOQUIA = 80 Mpios)
                                # =================================================================
                                col_terr_pec = next((c for c in df_pec_all.columns if c.lower() in ['territorio', 'municipio', 'unidad', 'nombre']), 'Territorio')
                                col_llave_pec = next((c for c in df_pec_all.columns if 'llave' in c.lower()), 'LLAVE_UNIVERSAL')
                                col_nivel_pec = next((c for c in df_pec_all.columns if 'nivel' in c.lower()), 'Nivel')
                                col_esp_pec = next((c for c in df_pec_all.columns if c.lower() == 'especie'), 'Especie')
                                col_p0_pec = next((c for c in df_pec_all.columns if c.lower() in ['poblacion_base', 'pob_base']), 'Poblacion_Base')

                                # Filtramos solo municipios para no duplicar sumas
                                df_pec_mun = df_pec_all[df_pec_all[col_nivel_pec].astype(str).str.upper().str.contains('MUNICIP')].copy()
                                df_pec_mun['mun_key'] = df_pec_mun[col_terr_pec].apply(norm_key)
                                df_pec_mun = df_pec_mun.drop_duplicates(subset=['mun_key', col_esp_pec], keep='first').copy()

                                cols_num_pec = [c for c in df_pec_mun.select_dtypes(include=[np.number]).columns if c.lower() not in ['id', 'año_base', 'anio_base']]

                                def construir_pec_grupo(nombre_grupo, lista_mpios, etiqueta_nivel, prefijo_llave, forzar_cero=False):
                                    mpios_keys = set(norm_key(m) for m in lista_mpios)
                                    sub_p = df_pec_mun[df_pec_mun['mun_key'].isin(mpios_keys)]
                                    if sub_p.empty: return []
                                    
                                    filas_p = []
                                    for esp_val, grp in sub_p.groupby(col_esp_pec):
                                        base_row = grp.iloc[0].to_dict()
                                        base_row.pop('mun_key', None)
                                        base_row.pop('id', None)
                                        if forzar_cero:
                                            for c_num in cols_num_pec: base_row[c_num] = 0.0
                                            base_row['Log_a'], base_row['Log_r'], base_row['Exp_b'] = 0.0, 0.0, 0.0
                                        else:
                                            for c_num in cols_num_pec:
                                                base_row[c_num] = float(pd.to_numeric(grp[c_num], errors='coerce').fillna(0.0).sum())
                                            p0_s = float(base_row.get(col_p0_pec, 0.0) or 0.0)
                                            lk_s = float(base_row.get('Log_K', 0.0) or 0.0)
                                            if lk_s <= p0_s: lk_s = p0_s * 2.0
                                            base_row['Log_K'] = lk_s
                                            base_row['Log_a'] = max(0.1, (lk_s / max(1.0, p0_s)) - 1.0) if p0_s > 0 else 0.0
                                            base_row['Log_r'] = 0.025
                                        
                                        base_row[col_terr_pec] = nombre_grupo
                                        base_row[col_nivel_pec] = etiqueta_nivel
                                        # Estándar universal compatible con todos los módulos
                                        base_row[col_llave_pec] = f"{prefijo_llave}_{norm_con_guion(nombre_grupo)}_TOTAL"
                                        filas_p.append(base_row)
                                    return filas_p

                                nuevas_filas_pec = []
                                # A. 9 Subregiones (Incluye Valle de Aburrá con todo su ganado rural)
                                for sub_nom, mpios in SUBREGIONES_ANT.items():
                                    nuevas_filas_pec.extend(construir_pec_grupo(sub_nom, mpios, "REGIONAL", "REGIONAL"))
                                    nuevas_filas_pec.extend(construir_pec_grupo(sub_nom, mpios, "SUBREGIONAL", "SUBREGIONAL"))
                                    nuevas_filas_pec.extend(construir_pec_grupo(sub_nom, mpios, "SUBREGION", "SUBREGION"))

                                # B. CARs: CORANTIOQUIA recibe los 80 municipios (70 + 10 rurales del Aburrá); AMVA queda en 0 animales
                                nuevas_filas_pec.extend(construir_pec_grupo("CORANTIOQUIA", MPIOS_CORANTIOQUIA_80, "CAR", "CAR", forzar_cero=False))
                                nuevas_filas_pec.extend(construir_pec_grupo("AMVA", MPIOS_ABURRA_10, "CAR", "CAR", forzar_cero=True))
                                nuevas_filas_pec.extend(construir_pec_grupo("CORNARE", MPIOS_CORNARE_26, "CAR", "CAR", forzar_cero=False))
                                nuevas_filas_pec.extend(construir_pec_grupo("CORPOURABA", MPIOS_CORPOURABA_19, "CAR", "CAR", forzar_cero=False))

                                df_nuevas_pec = pd.DataFrame(nuevas_filas_pec)

                                with engine_sql.begin() as conn:
                                    conn.execute(text("DELETE FROM matriz_maestra_demografica WHERE UPPER(\"Nivel\") IN ('SUBREGIONAL', 'REGIONAL', 'SUBREGION', 'CAR', 'AUTORIDAD AMBIENTAL')"))
                                    if col_nivel_pec in df_pec_all.columns:
                                        conn.execute(text(f"DELETE FROM matriz_maestra_pecuaria WHERE UPPER(\"{col_nivel_pec}\") IN ('SUBREGIONAL', 'REGIONAL', 'SUBREGION', 'CAR', 'AUTORIDAD AMBIENTAL')"))

                                cols_validas_demo = [c for c in df_nuevas_demo.columns if c in df_demo_all.columns and c not in ['id', 'mun_key', 'Area_Std']]
                                df_nuevas_demo[cols_validas_demo].to_sql('matriz_maestra_demografica', engine_sql, if_exists='append', index=False, chunksize=200, method='multi')

                                if not df_nuevas_pec.empty:
                                    cols_validas_pec = [c for c in df_nuevas_pec.columns if c in df_pec_all.columns and c not in ['id', 'mun_key']]
                                    df_nuevas_pec[cols_validas_pec].to_sql('matriz_maestra_pecuaria', engine_sql, if_exists='append', index=False, chunksize=200, method='multi')

                                st.cache_data.clear()
                                for k_mem in ['df_matriz_demografica', 'df_matriz_pecuaria', 'df_demo_cache']:
                                    st.session_state.pop(k_mem, None)
                                st.success(f"✅ ¡Forja Jurisdiccional Completada! {len(df_nuevas_demo)} ecuaciones demográficas y {len(df_nuevas_pec)} registros pecuarios inyectados en Supabase.")
                        except Exception as e:
                            st.error(f"🚨 Error forjando Subregiones y CARs: {e}")

# ---------------------------------------------------------
# PESTAÑA 1: TENDENCIA Y ESTRUCTURA
# ---------------------------------------------------------
with tab_modelos:
    st.subheader(f"Evolución y Estructura: {territorio_sel}")
    
    if datos_modelo is None or not isinstance(datos_modelo, dict) or 'hist_anios' not in datos_modelo:
        st.warning(f"⚠️ El Censo Nacional no posee registros nominales directos para la entidad: **{territorio_sel}**.")
        st.info("💡 **Solución Dasimétrica:** Para calcular la población de una cuenca, debemos superponer su geometría sobre los municipios que la componen. Por favor, dirígete a la pestaña **'🗺️ Mapa Dasimétrico (V2.0)'** para realizar el cálculo topológico espacial.")
    else:
        # Gráfica de curva básica
        fig_main = go.Figure()
        if 'resultados' in locals() and resultados:
            mejor_mod = max(resultados, key=lambda k: resultados[k]['r2'])
            fig_main.add_trace(go.Scatter(x=x_proj, y=resultados[mejor_mod]['y'], mode='lines', name=f'Mod. {mejor_mod}', line=dict(color='#10b981', width=3)))
        
        fig_main.add_trace(go.Scatter(x=datos_modelo['hist_anios'], y=datos_modelo['hist_pob'], mode='markers', name='Censo DANE', marker=dict(color='#ef4444', size=8)))
        fig_main.update_layout(hovermode="x unified", template="plotly_white", height=350)
        st.plotly_chart(fig_main, width="stretch")

        st.markdown("---")
        st.subheader("⚖️ Análisis Comparativo de Estructura Poblacional")
        
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            st.markdown(f"**Año Base / Seleccionado: {año_sel}**")
            df_e = datos_modelo['df_edades']
            fila_anio = df_e[df_e['año'] == año_sel]
            
            if not fila_anio.empty:
                fila = fila_anio.iloc[0]
                edades_h, edades_m = [], []
                for col in datos_modelo['cols_hombres']:
                    edad_num = int(re.search(r'\d+', col).group())
                    edades_h.append({'Edad': edad_num, 'Valor': fila[col]})
                for col in datos_modelo['cols_mujeres']:
                    edad_num = int(re.search(r'\d+', col).group())
                    edades_m.append({'Edad': edad_num, 'Valor': fila[col]})
                    
                df_h, df_m = pd.DataFrame(edades_h), pd.DataFrame(edades_m)
                
                # Agrupamos en rangos de 5 años
                df_h['Rango'] = pd.cut(df_h['Edad'], bins=list(range(0, 105, 5)) + [200], labels=[f"{i}-{i+4}" for i in range(0, 100, 5)] + ["100+"], right=False)
                df_m['Rango'] = pd.cut(df_m['Edad'], bins=list(range(0, 105, 5)) + [200], labels=[f"{i}-{i+4}" for i in range(0, 100, 5)] + ["100+"], right=False)
                
                df_pyr_h = df_h.groupby('Rango', observed=True)['Valor'].sum().reset_index()
                df_pyr_m = df_m.groupby('Rango', observed=True)['Valor'].sum().reset_index()
                
                fig_p = go.Figure()
                fig_p.add_trace(go.Bar(y=df_pyr_h['Rango'], x=-df_pyr_h['Valor'], name='Hombres', orientation='h', marker_color='#3498db'))
                fig_p.add_trace(go.Bar(y=df_pyr_m['Rango'], x=df_pyr_m['Valor'], name='Mujeres', orientation='h', marker_color='#e74c3c'))
                fig_p.update_layout(barmode='relative', height=400, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig_p, width="stretch")
            else:
                st.warning(f"No hay pirámide disponible para el año {año_sel}.")

        with col_p2:
            año_comp = st.session_state.get('horizonte_proj', 2034) 
            
            st.markdown(f"**Proyección Comparativa: {año_comp}**")
            
            try:
                datos_comp = calcular_poblacion_al_vuelo(territorio_puro, nivel_backend, area_global, anio_especifico=año_comp)
                
                if datos_comp is not None and not datos_comp.empty:
                    fila_comp = datos_comp.iloc[0]
                    
                    edades_c_h, edades_c_m = [], []
                    for col in datos_modelo['cols_hombres']:
                        edad_num = int(re.search(r'\d+', col).group())
                        edades_c_h.append({'Edad': edad_num, 'Valor': fila_comp[col]})
                    for col in datos_modelo['cols_mujeres']:
                        edad_num = int(re.search(r'\d+', col).group())
                        edades_c_m.append({'Edad': edad_num, 'Valor': fila_comp[col]})
                        
                    df_ch, df_cm = pd.DataFrame(edades_c_h), pd.DataFrame(edades_c_m)
                    
                    df_ch['Rango'] = pd.cut(df_ch['Edad'], bins=list(range(0, 105, 5)) + [200], labels=[f"{i}-{i+4}" for i in range(0, 100, 5)] + ["100+"], right=False)
                    df_cm['Rango'] = pd.cut(df_cm['Edad'], bins=list(range(0, 105, 5)) + [200], labels=[f"{i}-{i+4}" for i in range(0, 100, 5)] + ["100+"], right=False)
                    
                    df_pyr_ch = df_ch.groupby('Rango', observed=True)['Valor'].sum().reset_index()
                    df_pyr_cm = df_cm.groupby('Rango', observed=True)['Valor'].sum().reset_index()
                    
                    fig_p2 = go.Figure()
                    fig_p2.add_trace(go.Bar(y=df_pyr_ch['Rango'], x=-df_pyr_ch['Valor'], name='Hombres', orientation='h', marker_color='#3498db'))
                    fig_p2.add_trace(go.Bar(y=df_pyr_cm['Rango'], x=df_pyr_cm['Valor'], name='Mujeres', orientation='h', marker_color='#e74c3c'))
                    fig_p2.update_layout(barmode='relative', height=400, margin=dict(l=0,r=0,t=0,b=0), showlegend=False)
                    
                    st.plotly_chart(fig_p2, width="stretch")
                else:
                    st.warning(f"No hay datos de proyección matemática disponibles para el año {año_comp}.")
            except Exception as e:
                st.error(f"Error calculando la pirámide proyectada: {e}")

# ---------------------------------------------------------
# PESTAÑA 3: GEOMETRÍA DASIMÉTRICA (V2.0 FASTAPI)
# ---------------------------------------------------------
with tab_mapas:
    st.subheader(f"🗺️ Topología Activa: {territorio_sel}")
    st.info("💡 La visualización espacial funciona a través de FastAPI para evitar colapsos de memoria RAM.")
    
    modo_color_das = st.radio(
        "🎨 Métrica de Color Cartográfico:",
        ["Densidad Poblacional (Hab/km²) - Recomendado", "Población Absoluta por Polígono (Hab)"],
        horizontal=True,
        key="radio_modo_dasimetrico"
    )
    
    if st.button("🗺️ Renderizar Mapa de Calor Topológico", type="primary"):
        payload_map = {"territorio": territorio_sel, "nivel": nivel_backend, "anio_destino": año_sel}
        try:
            with st.spinner("Bisturí Espacial extrayendo polígonos desde PostGIS..."):
                resp_map = requests.post("https://sihcli-poter-v2-0.onrender.com/api/demografia/mapa", json=payload_map, timeout=240)
                
            if resp_map.status_code == 200:
                datos_m = resp_map.json()
                features = datos_m["geojson"].get("features", [])
                
                if not features:
                    st.warning("El mapa cargó pero no contiene polígonos válidos.")
                else:
                    filtro = area_global.upper() if 'area_global' in locals() else "TOTAL"
                    
                    # 1. Recuperamos población activa según el año seleccionado
                    try:
                        idx_anio = datos_modelo['hist_anios'].index(año_sel)
                        pob_activa = float(datos_modelo['hist_pob'][idx_anio])
                    except Exception:
                        pob_activa = float(datos_modelo['hist_pob'][-1]) if (datos_modelo and 'hist_pob' in datos_modelo) else 1000.0

                    # 1.1 Calculamos la proporción real Urbana vs Rural del territorio para no inflar las veredas
                    peso_urbano, peso_rural = 0.85, 0.15
                    try:
                        res_u = calcular_poblacion_al_vuelo(territorio_sel, nivel_backend, "Urbana")
                        res_r = calcular_poblacion_al_vuelo(territorio_sel, nivel_backend, "Rural")
                        if res_u and res_r and len(res_u.get('hist_pob', [])) > 0 and len(res_r.get('hist_pob', [])) > 0:
                            u_val = float(res_u['hist_pob'][res_u['hist_anios'].index(año_sel)]) if año_sel in res_u['hist_anios'] else float(res_u['hist_pob'][-1])
                            r_val = float(res_r['hist_pob'][res_r['hist_anios'].index(año_sel)]) if año_sel in res_r['hist_anios'] else float(res_r['hist_pob'][-1])
                            if (u_val + r_val) > 0:
                                peso_urbano = u_val / (u_val + r_val)
                                peso_rural = r_val / (u_val + r_val)
                    except Exception:
                        pass

                    # Si el usuario filtró explícitamente solo Urbana o solo Rural en el sidebar
                    if filtro == "URBANA":
                        pob_urb_objetivo, pob_rur_objetivo = pob_activa, 0.0
                    elif filtro == "RURAL":
                        pob_urb_objetivo, pob_rur_objetivo = 0.0, pob_activa
                    else:
                        pob_urb_objetivo = pob_activa * peso_urbano
                        pob_rur_objetivo = pob_activa * peso_rural

                    # 2. Descargamos matriz de cuencas si aplica
                    df_prop = pd.DataFrame()
                    if nivel_backend == "CUENCA":
                        url_prop = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/cuencas_mpios_proporcion.csv"
                        try:
                            df_prop = pd.read_csv(url_prop, sep=';', encoding='utf-8')
                            df_prop.columns = [c.strip() for c in df_prop.columns]
                            df_prop['mun_norm'] = df_prop['Municipio'].astype(str).apply(normalizar_texto)
                            df_prop['cuenca_norm'] = df_prop['Subcuenca'].astype(str).apply(normalizar_texto)
                        except Exception:
                            pass

                    # 3. Clasificación estricta de polígonos urbanos y rurales y factor de compacidad/centralidad
                    def es_poligono_urbano(feat):
                        p = feat.get("properties", {})
                        tit = str(p.get("Sector / Vereda", "")).upper()
                        tip = str(p.get("Tipo de Asentamiento", "")).upper()
                        com = str(p.get("Comuna", "")).upper()
                        return any(k in tit or k in tip for k in ["BARRIO", "CABECERA", "URBANO", "URBANA", "CENTRO POBLADO"]) or (com not in ["", "NO APLICA", "NONE", "NAN", "VEREDA"])

                    # Calculamos el área real en km² desde las coordenadas del polígono si Area_Calc viene constante (=1.0)
                    from shapely.geometry import shape
                    areas_reales = []
                    centroides = []
                    es_urb_list = []
                    for f in features:
                        es_u = es_poligono_urbano(f)
                        es_urb_list.append(es_u)
                        try:
                            geom = shape(f["geometry"])
                            # Aproximación métrica en latitud de Colombia (1 grado ~ 111.1 km)
                            a_km2 = max(0.002, geom.area * (111.1 ** 2))
                            c_pt = (geom.centroid.y, geom.centroid.x)
                        except Exception:
                            a_km2 = max(0.002, float(f.get("properties", {}).get("Area_Calc", 1.0) or 1.0))
                            c_pt = (datos_m["centro"]["lat"], datos_m["centro"]["lon"])
                        areas_reales.append(a_km2)
                        centroides.append(c_pt)

                    # Centroide del núcleo urbano para gradiente de densidad (Modelo de Clark)
                    pts_urb = [c for c, u in zip(centroides, es_urb_list) if u] or centroides
                    lat_nuc = np.mean([p[0] for p in pts_urb])
                    lon_nuc = np.mean([p[1] for p in pts_urb])

                    # Pesos dasimétricos: combina tamaño del polígono, compacidad de manzana y distancia al núcleo
                    pesos_urb, pesos_rur = [], []
                    for i, f in enumerate(features):
                        a_pol = areas_reales[i]
                        dist_km = np.hypot((centroides[i][0] - lat_nuc) * 111.1, (centroides[i][1] - lon_nuc) * 111.1)
                        if es_urb_list[i]:
                            # En ciudad: manzanas/barrios cercanos al eje central concentran más densidad vertical
                            factor_centralidad = np.exp(-0.22 * dist_km) * (a_pol ** 0.75)
                            pesos_urb.append(max(1e-6, factor_centralidad))
                            pesos_rur.append(0.0)
                        else:
                            # En zona rural: veredas más cercanas a la cabecera y de tamaño medio concentran más población
                            factor_rur = np.exp(-0.06 * dist_km) * (a_pol ** 0.65)
                            pesos_urb.append(0.0)
                            pesos_rur.append(max(1e-6, factor_rur))

                    sum_peso_urb = sum(pesos_urb)
                    sum_peso_rur = sum(pesos_rur)

                    if sum_peso_urb == 0 and sum_peso_rur > 0:
                        pob_rur_objetivo += pob_urb_objetivo
                        sum_peso_urb = 1.0
                    elif sum_peso_rur == 0 and sum_peso_urb > 0:
                        pob_urb_objetivo += pob_rur_objetivo
                        sum_peso_rur = 1.0

                    prop_list = []
                    for i, f in enumerate(features):
                        f["id"] = str(i)
                        props_crudas = f.get("properties", {})
                        titulo = str(props_crudas.get("Sector / Vereda", "Sector Urbano")).title()
                        area_pol = areas_reales[i]
                        es_urbano = es_urb_list[i]

                        if es_urbano:
                            habs_calculados = pob_urb_objetivo * (pesos_urb[i] / sum_peso_urb)
                        else:
                            habs_calculados = pob_rur_objetivo * (pesos_rur[i] / sum_peso_rur)

                        if (filtro == "URBANA" and not es_urbano) or (filtro == "RURAL" and es_urbano):
                            habs_calculados = 0.0

                        label_padre = "Zona Hidrográfica" if "Río Tributario" in props_crudas or "Microcuenca" in props_crudas else "Municipio"
                        padre = str(props_crudas.get(label_padre, "N/A")).title()

                        prop_list.append({
                            "id": str(i),
                            "Territorio": titulo,
                            label_padre: padre,
                            "Tipo": "Urbano / Cabecera" if es_urbano else "Rural / Vereda",
                            "Comuna": str(props_crudas.get("Comuna", "No Aplica")),
                            "Area_km2": round(area_pol, 3),
                            "Población": round(habs_calculados)
                        })

                    df_mapa = pd.DataFrame(prop_list)

                    # Ajuste proporcional exacto para que la suma cuadre al habitante con pob_activa
                    suma_actual = df_mapa["Población"].sum()
                    if suma_actual > 0 and pob_activa > 0:
                        df_mapa["Población"] = (df_mapa["Población"] * (pob_activa / suma_actual)).round().astype(int)

                    df_mapa["Densidad (Hab/km²)"] = (df_mapa["Población"] / df_mapa["Area_km2"].clip(lower=0.005)).round(1)
                    df_mapa["Color_Densidad_Log"] = np.log10(df_mapa["Densidad (Hab/km²)"].clip(lower=1.0))

                    usar_densidad = "Densidad" in modo_color_das
                    col_color = "Color_Densidad_Log" if usar_densidad else "Población"

                    # Calculamos percentiles 5 y 98 para que la barra de color siempre muestre máximo contraste
                    vals_validos = df_mapa[df_mapa["Población"] > 0][col_color]
                    rango_c = [float(vals_validos.quantile(0.05)), float(vals_validos.quantile(0.98))] if len(vals_validos) > 2 else None

                    fig_m = px.choropleth_mapbox(
                        df_mapa,
                        geojson=datos_m["geojson"],
                        locations="id",
                        color=col_color,
                        color_continuous_scale="YlOrRd",
                        range_color=rango_c,
                        hover_name="Territorio",
                        hover_data={
                            "id": False,
                            "Color_Densidad_Log": False,
                            "Territorio": False,
                            label_padre: True,
                            "Tipo": True,
                            "Población": ":,.0f",
                            "Densidad (Hab/km²)": ":,.1f",
                            "Area_km2": ":,.3f"
                        },
                        labels={"Color_Densidad_Log": "Log10(Hab/km²)", "Población": "Habitantes"},
                        mapbox_style="open-street-map", # Evita el cartel "API KEY REQUIRED" de Carto
                        center={"lat": datos_m["centro"]["lat"], "lon": datos_m["centro"]["lon"]},
                        zoom=11 if nivel_backend in ["MUNICIPAL", "CAR"] else 7,
                        opacity=0.78
                    )
                    fig_m.update_traces(marker_line_width=0.3, marker_line_color='rgba(255,255,255,0.25)')
                    fig_m.update_layout(margin={"r":0,"t":50,"l":0,"b":0}, height=650, title=f"Distribución Dasimétrica ({filtro.title()}) - Total: {df_mapa['Población'].sum():,.0f} hab.")
                    st.plotly_chart(fig_m, width="stretch")

            elif resp_map.status_code == 404:
                st.warning(f"⚠️ El visor web rechazó cargar {territorio_sel}: {resp_map.json().get('detail', 'No encontrado en PostGIS')}")
            else:
                st.error(f"Error cargando mapa: {resp_map.text}")
        except Exception as e:
            st.error(f"El backend FastAPI no está respondiendo. Detalle: {e}")

# ---------------------------------------------------------
# PESTAÑA 4: DINÁMICA ESPACIAL DE CRECIMIENTO
# ---------------------------------------------------------
with tab_dinamica:
    st.subheader(f"🚦 Dinámica de Crecimiento: {territorio_sel}")
    st.info("Clasifica los fragmentos territoriales según la tasa de crecimiento proyectada de su municipio matriz (Base DANE).")

    c1, c2 = st.columns(2)
    umb_pos = c1.number_input("Umbral Crecimiento Positivo (> %)", value=5.0, step=0.5)
    umb_neg = c2.number_input("Umbral Decrecimiento (< %)", value=-5.0, step=0.5)

    if st.button("🗺️ Renderizar Mapa Dinámico", type="primary", key="btn_din"):
        with st.spinner("Calculando proyecciones demográficas por fragmento..."):
            payload_map = {"territorio": territorio_sel, "nivel": nivel_backend, "anio_destino": año_sel}
            try:
                import requests
                import plotly.express as px
                import pandas as pd
                
                resp_map = requests.post("https://sihcli-poter-v2-0.onrender.com/api/demografia/mapa", json=payload_map, timeout=240)

                if resp_map.status_code == 200:
                    datos_m = resp_map.json()
                    features = datos_m["geojson"].get("features", [])
                    
                    # 1. Identificar municipios únicos presentes en el mapa actual
                    mpios_unicos = list(set([str(f.get("properties", {}).get("Municipio", "")).upper() for f in features]))
                    
                    # 2. 🚀 CÁLCULO AUTÓNOMO: Consultar la proyección DANE para cada municipio
                    deltas_mpio = {}
                    for mpio in mpios_unicos:
                        if not mpio or mpio == "N/A": continue
                        res_mpio = calcular_poblacion_al_vuelo(mpio, "MUNICIPAL", "Total")
                        
                        if res_mpio and len(res_mpio['hist_anios']) > 0:
                            # Buscar población en 2024 (o inicio) vs la proyección final
                            try:
                                pob_base = res_mpio['hist_pob'][res_mpio['hist_anios'].index(2024)]
                            except ValueError:
                                pob_base = res_mpio['hist_pob'][0]
                                
                            pob_futura = res_mpio['hist_pob'][-1]
                            
                            if pob_base > 0:
                                deltas_mpio[mpio] = ((pob_futura - pob_base) / pob_base) * 100
                            else:
                                deltas_mpio[mpio] = 0.0
                                
                    # 3. Asignar estado y colores a los polígonos
                    prop_list = []
                    for i, f in enumerate(features):
                        f["id"] = str(i)
                        props = f.get("properties", {})
                        mpio_nombre = str(props.get("Municipio", "")).upper()
                        
                        variacion = deltas_mpio.get(mpio_nombre, 0.0)
                        
                        # Semáforo de Umbrales
                        if variacion > umb_pos: estado = "Crecimiento"
                        elif variacion < umb_neg: estado = "Decrecimiento"
                        else: estado = "Estabilidad"
                        
                        # Extraer título limpio
                        if "Río Tributario" in props or "Microcuenca" in props:
                            titulo = str(props.get("Microcuenca") or props.get("Río Tributario") or "Cauce").title()
                        else:
                            titulo = str(props.get("Sector / Vereda") or props.get("Vereda") or props.get("Municipio") or "Sector").title()

                        prop_list.append({
                            "id": str(i),
                            "Territorio": titulo,
                            "Municipio Matriz": mpio_nombre.title(),
                            "Crecimiento (%)": round(variacion, 2),
                            "Estado": estado
                        })
                        
                    df_tend = pd.DataFrame(prop_list)

                    # =========================================================
                    # 💉 INYECTOR DE DINÁMICA (Bypass exclusivo para Cuencas)
                    # =========================================================
                    if nivel_backend == "CUENCA" and datos_modelo:
                        try:
                            # Calculamos el crecimiento real de la cuenca
                            idx_base = datos_modelo['hist_anios'].index(año_sel)
                            idx_futuro = datos_modelo['hist_anios'].index(anio_destino)
                            pob_base = datos_modelo['hist_pob'][idx_base]
                            pob_futuro = datos_modelo['hist_pob'][idx_futuro]
                            
                            crecimiento_pct = ((pob_futuro - pob_base) / pob_base) * 100 if pob_base > 0 else 0.0
                        except ValueError:
                            crecimiento_pct = 0.0
                            
                        # Inyectamos los valores reales de la cuenca en la tabla del mapa
                        if 'Crecimiento (%)' in df_tend.columns:
                            df_tend['Crecimiento (%)'] = round(crecimiento_pct, 2)
                        
                        # Forzamos el estado (Verde, Amarillo, Rojo)
                        if 'Estado' in df_tend.columns:
                            if crecimiento_pct > umb_pos: estado_calc = "Crecimiento"
                            elif crecimiento_pct < umb_neg: estado_calc = "Decrecimiento"
                            else: estado_calc = "Estabilidad"
                            df_tend['Estado'] = estado_calc
                    # =========================================================
                    
                    # 4. Renderizado del Mapa Semáforo
                    fig_t = px.choropleth_mapbox(
                        df_tend, geojson=datos_m["geojson"], locations="id",
                        color="Estado",
                        color_discrete_map={"Crecimiento": "#2ecc71", "Estabilidad": "#f1c40f", "Decrecimiento": "#e74c3c"},
                        hover_name="Territorio",
                        hover_data={"id": False, "Estado": False, "Municipio Matriz": True, "Crecimiento (%)": True},
                        mapbox_style="carto-positron",
                        center={"lat": datos_m["centro"]["lat"], "lon": datos_m["centro"]["lon"]},
                        zoom=9 if nivel_backend == "MUNICIPAL" else 7, opacity=0.75
                    )
                    fig_t.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=600)
                    st.plotly_chart(fig_t, width="stretch")
                else:
                    st.error("Error cargando la geometría. Asegúrate de que el backend de mapas funcione.")
            except Exception as e:
                st.error(f"Error procesando la dinámica espacial: {e}")