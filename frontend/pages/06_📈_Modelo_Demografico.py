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
                st.plotly_chart(fig_opt, use_container_width=True)

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
        st.plotly_chart(fig_main, use_container_width=True)

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
                st.plotly_chart(fig_p, use_container_width=True)
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
                    
                    st.plotly_chart(fig_p2, use_container_width=True)
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
    
    if st.button("🗺️ Renderizar Mapa de Calor Topológico", type="primary"):
        payload_map = {"territorio": territorio_sel, "nivel": nivel_backend, "anio_destino": año_sel}
        try:
            with st.spinner("Bisturí Espacial extrayendo polígonos desde PostGIS..."):
                resp_map = requests.post("https://sihcli-poter-v2-0.onrender.com/api/demografia/mapa", json=payload_map, timeout=60)
                
            if resp_map.status_code == 200:
                datos_m = resp_map.json()
                features = datos_m["geojson"].get("features", [])
                
                if not features:
                    st.warning("El mapa cargó pero no contiene polígonos válidos.")
                else:
                    # 🚀 FIX CRÍTICO: Declaramos el filtro explícitamente
                    filtro = area_global.upper() if 'area_global' in locals() else "TOTAL"
                    
                    # 1. Recuperamos población activa
                    try:
                        idx_anio = datos_modelo['hist_anios'].index(año_sel)
                        pob_activa = datos_modelo['hist_pob'][idx_anio]
                    except:
                        pob_activa = datos_modelo['hist_pob'][-1] if (datos_modelo and 'hist_pob' in datos_modelo) else 1000

                    # 2. Descargamos matriz de cuencas
                    df_prop = pd.DataFrame()
                    if nivel_backend == "CUENCA":
                        url_prop = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/cuencas_mpios_proporcion.csv"
                        try:
                            df_prop = pd.read_csv(url_prop, sep=';', encoding='utf-8')
                            df_prop.columns = [c.strip() for c in df_prop.columns]
                            df_prop['mun_norm'] = df_prop['Municipio'].astype(str).apply(normalizar_texto)
                            df_prop['cuenca_norm'] = df_prop['Subcuenca'].astype(str).apply(normalizar_texto)
                        except: pass

                    # 3. Sumas de áreas y asignación
                    area_urb_sum = sum(float(f.get("properties", {}).get("Area_Calc", 1.0)) for f in features if "Barrio" in str(f.get("properties", {}).get("Sector / Vereda", "")).title() or "Cabecera" in str(f.get("properties", {}).get("Tipo de Asentamiento", "")).title())
                    area_rur_sum = sum(float(f.get("properties", {}).get("Area_Calc", 1.0)) for f in features if not ("Barrio" in str(f.get("properties", {}).get("Sector / Vereda", "")).title() or "Cabecera" in str(f.get("properties", {}).get("Tipo de Asentamiento", "")).title()))
                    
                    if area_urb_sum == 0: area_urb_sum = 1.0
                    if area_rur_sum == 0: area_rur_sum = 1.0

                    prop_list = []
                    for i, f in enumerate(features):
                        f["id"] = str(i) 
                        props_crudas = f.get("properties", {})
                        
                        titulo = str(props_crudas.get("Sector / Vereda", "Sector Urbano")).title()
                        tipo = str(props_crudas.get("Tipo de Asentamiento", "")).title()
                        area_pol = float(props_crudas.get("Area_Calc", 1.0))
                        es_urbano = "Barrio" in titulo or "Cabecera" in tipo
                        habs_calculados = 0
                        
                        if nivel_backend == "CUENCA" and not df_prop.empty:
                            municipio = normalizar_texto(props_crudas.get("Municipio", ""))
                            nombre_cuenca = normalizar_texto(territorio_sel)
                            match = df_prop[(df_prop['mun_norm'] == municipio) & (df_prop['cuenca_norm'] == nombre_cuenca)]
                            
                            if not match.empty:
                                pct_str = str(match['Porcentaje'].values[0]).replace('.', '')
                                pct_float = float(pct_str[:-2] + '.' + pct_str[-2:]) if len(pct_str) > 2 else float(pct_str)
                                pct_real = pct_float / 100.0 if pct_float > 1 else pct_float
                                
                                res_mpio = calcular_poblacion_al_vuelo(municipio, "MUNICIPAL", "Total")
                                if res_mpio and len(res_mpio['hist_anios']) > 0:
                                    try: pob_mpio = res_mpio['hist_pob'][res_mpio['hist_anios'].index(año_sel)]
                                    except: pob_mpio = res_mpio['hist_pob'][-1]
                                    habs_calculados = int(pob_mpio * pct_real * (area_pol / (area_urb_sum if es_urbano else area_rur_sum)))
                        else:
                            if es_urbano: habs_calculados = int(pob_activa * (area_pol / area_urb_sum))
                            else: habs_calculados = int(pob_activa * (area_pol / area_rur_sum))

                        # Silenciar polígonos fuera del filtro
                        if (filtro == "URBANA" and not es_urbano) or (filtro == "RURAL" and es_urbano):
                            habs_calculados = 0

                        label_padre = "Zona Hidrográfica" if "Río Tributario" in props_crudas or "Microcuenca" in props_crudas else "Municipio"
                        padre = str(props_crudas.get(label_padre, "N/A")).title()

                        prop_list.append({
                            "id": str(i), "Territorio": titulo, label_padre: padre, "Tipo": tipo,
                            "Comuna": str(props_crudas.get("Comuna", "No Aplica")),
                            "Población": habs_calculados
                        })

                    df_mapa = pd.DataFrame(prop_list)

                    # =========================================================
                    # 💉 INYECTOR DE POBLACIÓN (Bypass para Cuencas)
                    # =========================================================
                    if nivel_backend == "CUENCA" and datos_modelo:
                        try:
                            # Extraemos la población calculada para el año seleccionado en el slider
                            idx_anio = datos_modelo['hist_anios'].index(año_sel)
                            pob_exacta = datos_modelo['hist_pob'][idx_anio]
                        except ValueError:
                            pob_exacta = datos_modelo['hist_pob'][-1]
                        
                        # Detectamos cómo se llama la columna de población en tu DataFrame
                        col_pob = next((c for c in df_mapa.columns if c.lower() in ['total', 'poblacion', 'población', 'pob', 'valor']), 'Población')
                        
                        # Inyectamos el valor al mapa
                        df_mapa[col_pob] = pob_exacta
                    # =========================================================
                    
                    # 4. Renderizamos el Mapa
                    fig_m = px.choropleth_mapbox(
                        df_mapa, geojson=datos_m["geojson"], locations="id", color="Población", 
                        color_continuous_scale="YlOrRd", hover_name="Territorio", 
                        hover_data={"id": False, "Territorio": False, label_padre: True, "Tipo": True, "Población": True},
                        mapbox_style="carto-positron", center={"lat": datos_m["centro"]["lat"], "lon": datos_m["centro"]["lon"]},
                        zoom=9 if nivel_backend == "MUNICIPAL" else 7, opacity=0.75
                    )
                    fig_m.update_traces(marker_line_width=0, marker_line_color='rgba(0,0,0,0)')
                    fig_m.update_layout(margin={"r":0,"t":50,"l":0,"b":0}, height=650, title=f"Distribución Dasimétrica ({filtro.title()})")
                    st.plotly_chart(fig_m, use_container_width=True)

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
                
                resp_map = requests.post("https://sihcli-poter-v2-0.onrender.com/api/demografia/mapa", json=payload_map, timeout=60)

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
                    st.plotly_chart(fig_t, use_container_width=True)
                else:
                    st.error("Error cargando la geometría. Asegúrate de que el backend de mapas funcione.")
            except Exception as e:
                st.error(f"Error procesando la dinámica espacial: {e}")