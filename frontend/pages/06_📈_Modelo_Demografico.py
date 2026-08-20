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
try:
    from modules import selectors
    from modules.utils import encender_gemelo_digital, normalizar_texto, cargar_capa_espacial_cache
except ImportError:
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
st.sidebar.markdown("---")
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

# Ejecutamos la consulta matemática central (V1 Local)
datos_modelo = calcular_poblacion_al_vuelo(territorio_sel, nivel_backend, area_global)

# ---------------------------------------------------------
# PESTAÑA 2: OPTIMIZACIÓN (Solver Matemático)
# ---------------------------------------------------------
with tab_opt:
    st.header("⚙️ Ajuste de Modelos Evolutivos (Solver)")
    
    if datos_modelo is None:
        st.error(f"No se pudieron generar datos históricos para {territorio_sel}.")
    else:
        # Aquí ejecutamos scipy.optimize localmente como en la V1
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
        # PESTAÑA 1: TENDENCIA Y ESTRUCTURA (Pirámides V1 y Comparativa)
        # ---------------------------------------------------------
        with tab_modelos:
            st.subheader(f"Evolución y Estructura: {territorio_sel}")
            
            if datos_modelo is not None and len(datos_modelo['hist_anios']) > 0:
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
                    año_comp = st.slider("Seleccionar Horizonte Comparativo:", min_value=1985, max_value=2050, value=2050, key="slider_comp")
                    st.markdown(f"**Proyección Comparativa: {año_comp}**")
                    
                    # 🚀 CIRUGÍA: En lugar de llamar a la API (que aún no sabe de cuencas),
                    # usamos nuestra función local que SÍ sabe calcular cualquier escala y año.
                    try:
                        # Extraemos los datos para el año de comparación al vuelo
                        datos_comp = calcular_poblacion_al_vuelo(territorio_sel, nivel_backend, area_global, anio_especifico=año_comp)
                        
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
                            st.warning(f"No hay datos disponibles para el año {año_comp}.")
                    except Exception as e:
                        st.error(f"Error calculando la segunda pirámide: {e}")

# ---------------------------------------------------------
# PESTAÑA 3: GEOMETRÍA DASIMÉTRICA (V2.0 FASTAPI)
# ---------------------------------------------------------
with tab_mapas:
    st.subheader(f"🗺️ Topología Activa: {territorio_sel}")
    st.info("💡 La visualización espacial funciona a través de FastAPI para evitar colapsos de memoria RAM.")
    
    if st.button("🗺️ Renderizar Mapa de Calor Topológico", type="primary"):
        # Hablamos con el Cerebro (FastAPI) SOLAMENTE para dibujar el mapa
        payload_map = {"territorio": territorio_sel, "nivel": nivel_backend, "anio_destino": año_sel}
        try:
            import plotly.express as px
            import pandas as pd
            import numpy as np
            import requests
            
            with st.spinner("Bisturí Espacial extrayendo polígonos desde PostGIS/GeoJSON..."):
                resp_map = requests.post("http://127.0.0.1:8000/api/demografia/mapa", json=payload_map, timeout=60)
                
            if resp_map.status_code == 200:
                datos_m = resp_map.json()
                features = datos_m["geojson"].get("features", [])
                
                if not features:
                    st.warning("El mapa cargó pero no contiene polígonos válidos.")
                else:
                    # 1. Rescate de población total del modelo para distribuir (Dasimetría al vuelo)
                    pob_total = datos_modelo['hist_pob'][-1] if (datos_modelo and 'hist_pob' in datos_modelo) else 1000
                    
                    # 🚀 Sumamos la nueva Area_Calc exacta del Backend
                    areas = [float(f.get("properties", {}).get("Area_Calc", 1.0)) for f in features]
                    suma_areas = sum(areas) if sum(areas) > 0 else 1.0

                    # 🚀 CIRUGÍA DASIMÉTRICA REAL: Conectando el Filtro y la Densidad
                    # Asumimos que la variable de tu sidebar se llama filtro_poblacional
                    filtro = area_global.upper()
                    
                    # 1. Obtener poblaciones exactas para el año proyectado
                    try:
                        idx_anio = datos_modelo['hist_anios'].index(año_sel)
                        pob_activa = datos_modelo['hist_pob'][idx_anio]
                    except:
                        pob_activa = datos_modelo['hist_pob'][-1] if datos_modelo else 1000

                    pob_urb_total = 0
                    pob_rur_total = 0

                    if filtro == "TOTAL":
                        try:
                            # 🧠 Extraemos el split exacto usando tu función del frontend
                            res_urb = calcular_poblacion_al_vuelo(territorio_sel, nivel_backend, "Urbana")
                            res_rur = calcular_poblacion_al_vuelo(territorio_sel, nivel_backend, "Rural")
                            
                            idx_u = res_urb['hist_anios'].index(año_sel)
                            idx_r = res_rur['hist_anios'].index(año_sel)
                            
                            pob_urb_total = res_urb['hist_pob'][idx_u]
                            pob_rur_total = res_rur['hist_pob'][idx_r]
                        except:
                            # Fallback por seguridad
                            pob_urb_total = pob_activa * 0.70
                            pob_rur_total = pob_activa * 0.30
                    elif filtro == "URBANA":
                        pob_urb_total = pob_activa
                    elif filtro == "RURAL":
                        pob_rur_total = pob_activa

                    # 2. Separar las áreas disponibles según topología
                    area_urb_sum = 0.0
                    area_rur_sum = 0.0
                    
                    for f in features:
                        props = f.get("properties", {})
                        titulo = props.get("Sector / Vereda", "")
                        tipo = props.get("Tipo de Asentamiento", "")
                        area = float(props.get("Area_Calc", 1.0))
                        
                        if "Barrio" in titulo or "Cabecera" in tipo:
                            area_urb_sum += area
                        else:
                            area_rur_sum += area
                            
                    if area_urb_sum == 0: area_urb_sum = 1.0
                    if area_rur_sum == 0: area_rur_sum = 1.0

                    # 3. Asignación poblacional a cada polígono
                    prop_list = []
                    for i, f in enumerate(features):
                        f["id"] = str(i) 
                        props_crudas = f.get("properties", {})
                        
                        titulo = str(props_crudas.get("Sector / Vereda", "Sector Urbano")).title()
                        tipo = str(props_crudas.get("Tipo de Asentamiento", "")).title()
                        area_pol = float(props_crudas.get("Area_Calc", 1.0))
                        
                        es_urbano = "Barrio" in titulo or "Cabecera" in tipo
                        
                        # Cálculo Dasimétrico Real (Urbano a urbano, Rural a rural)
                        if es_urbano:
                            habs = int(pob_urb_total * (area_pol / area_urb_sum))
                        else:
                            habs = int(pob_rur_total * (area_pol / area_rur_sum))

                        # 👁️ Silenciar polígonos que no corresponden al filtro seleccionado
                        if (filtro == "URBANA" and not es_urbano) or (filtro == "RURAL" and es_urbano):
                            habs = 0

                        if "Río Tributario" in props_crudas or "Microcuenca" in props_crudas:
                            padre = str(props_crudas.get("Zona Hidrográfica", "N/A")).title()
                            label_padre = "Zona Hidrográfica"
                        else:
                            padre = str(props_crudas.get("Municipio") or "N/A").title()
                            label_padre = "Municipio"

                        props_limpias = {
                            "id": str(i),
                            "Territorio": titulo,
                            label_padre: padre,
                            "Tipo": str(props_crudas.get("Tipo de Asentamiento", "N/A")),
                            "Comuna": str(props_crudas.get("Comuna", "No Aplica")),
                            "Subregión": str(props_crudas.get("Subregión", "N/A")),
                            "Territorial": str(props_crudas.get("Dir. Territorial", "N/A")),
                            "CAR": str(props_crudas.get("Autoridad Ambiental (CAR)", "N/A")),
                            "Población": habs
                        }
                        prop_list.append(props_limpias)

                    df_mapa = pd.DataFrame(prop_list)

                    # 4. 🗺️ CONSTRUIMOS EL MAPA TÉRMICO
                    fig_m = px.choropleth_mapbox(
                        df_mapa,
                        geojson=datos_m["geojson"],
                        locations="id",
                        color="Población", 
                        color_continuous_scale="YlOrRd", 
                        hover_name="Territorio", 
                        hover_data={
                            "id": False, 
                            "Territorio": False, 
                            label_padre: True,
                            "Subregión": True,
                            "Territorial": True,
                            "CAR": True,
                            "Tipo": True,
                            "Comuna": True,
                            "Población": True
                        },
                        mapbox_style="carto-positron",
                        center={"lat": datos_m["centro"]["lat"], "lon": datos_m["centro"]["lon"]},
                        zoom=9 if nivel_backend == "MUNICIPAL" else 7,
                        opacity=0.75
                    )
                    
                    # 🚀 MAGIA ANTI-BORDES: Eliminamos las líneas de contorno de los polígonos
                    fig_m.update_traces(marker_line_width=0, marker_line_color='rgba(0,0,0,0)')
                    
                    # 🎨 Estiramos el contraste ignorando los ceros para que la leyenda sea perfecta
                    pob_valida = df_mapa[df_mapa["Población"] > 0]["Población"]
                    cmin = pob_valida.quantile(0.05) if not pob_valida.empty else 0
                    cmax = pob_valida.quantile(0.95) if not pob_valida.empty else 100
                    
                    fig_m.update_coloraxes(colorscale="YlOrRd", cmin=cmin, cmax=cmax)
                    fig_m.update_layout(
                        title=f"Distribución Dasimétrica ({filtro.title()}) | Base: 2024 ➔ Proyección: {año_sel}",
                        title_font=dict(size=18, color="#2c3e50"),
                        margin={"r":0,"t":50,"l":0,"b":0},
                        height=650,
                        coloraxis_showscale=True
                    )
                    
                    st.plotly_chart(fig_m, use_container_width=True)
                    
            elif resp_map.status_code == 404:
                st.warning(f"⚠️ El visor web rechazó cargar {territorio_sel} porque es un territorio muy pesado (Ej: Colombia entera) o no se encontró en PostGIS.")
            else:
                st.error(f"Error cargando mapa: {resp_map.text}")
        except Exception as e:
            st.error(f"El backend FastAPI no está respondiendo. ¿Está encendido el servidor uvicorn? Detalle: {e}")

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
                
                resp_map = requests.post("http://127.0.0.1:8000/api/demografia/mapa", json=payload_map)

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