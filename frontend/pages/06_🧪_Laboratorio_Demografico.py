# frontend/pages/06_🧪_Laboratorio_Demografico.py

import os
import sys
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import warnings

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Laboratorio Demográfico", page_icon="🧪", layout="wide")
warnings.filterwarnings('ignore')

# --- 📂 IMPORTACIÓN ROBUSTA DE MÓDULOS ---
try:
    from modules import selectors
    from modules.utils import encender_gemelo_digital
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules import selectors
    from modules.utils import encender_gemelo_digital

# ==========================================
# 📂 1. CARGAR MENÚ UNIVERSAL (EL ALEPH)
# ==========================================
selectors.renderizar_menu_navegacion("Laboratorio Demográfico")
encender_gemelo_digital()

st.title("🧪 Laboratorio Espacial y Demográfico")
st.info("⚠️ **Entorno de Pruebas (Sandbox V2.0):** Arquitectura desacoplada. FastAPI procesa los cálculos pesados y el renderizado espacial; Streamlit visualiza.")

# ==========================================
# ⚙️ 2. LEER DATOS DEL ALEPH (Memoria Global)
# ==========================================
if 'aleph_lugar' not in st.session_state:
    st.warning("👈 Por favor, selecciona un territorio en el menú lateral para comenzar.")
    st.stop()

territorio_sel = st.session_state['aleph_lugar']
nivel_backend = st.session_state['aleph_escala']

# Parámetros específicos de esta página
st.sidebar.subheader("⚙️ Controles Locales")
anio_destino = st.sidebar.slider("Año de Proyección:", min_value=1985, max_value=2042, value=2024)
consultar = st.sidebar.button("🔬 Consultar al Cerebro API", type="primary", use_container_width=True)

# ==========================================
# 📊 3. ÁREA DE VISUALIZACIÓN (LAYOUT)
# ==========================================
st.markdown("---")
c_mapa, c_piramide = st.columns([1.2, 1])

with c_mapa:
    st.subheader(f"🗺️ Topología: {territorio_sel}")
    st.empty()

with c_piramide:
    st.subheader("📊 Pirámide Poblacional")
    st.empty()

st.markdown("---")
st.subheader("📈 Curva de Proyección Histórica")
c_curva = st.container()

# ==========================================
# 🚀 4. EJECUCIÓN DE MICROSERVICIOS
# ==========================================
if consultar:
    payload = {
        "territorio": territorio_sel,
        "nivel": nivel_backend,
        "anio_destino": anio_destino
    }
    
    try:
        with st.spinner(f"🧠 Sincronizando Cerebro: Calculando Pirámide, Mapa y Proyección para {territorio_sel}..."):
            # Disparamos las 3 peticiones al backend de FastAPI
            resp_piramide = requests.post("http://127.0.0.1:8000/api/demografia/piramide", json=payload, timeout=120)
            resp_mapa = requests.post("http://127.0.0.1:8000/api/demografia/mapa", json=payload, timeout=120)
            resp_proyeccion = requests.post("http://127.0.0.1:8000/api/demografia/proyectar", json=payload, timeout=120)
            
        # ---------------------------------------------------------
        # 🗺️ 4.1 RENDERIZAR MAPA DE CALOR (COROPLETA)
        # ---------------------------------------------------------
        if resp_mapa.status_code == 200:
            datos_mapa = resp_mapa.json()
            geojson_data = datos_mapa["geojson"]
            
            features = geojson_data.get("features", [])
            ids, nombres, poblaciones = [], [], []
            
            for i, f in enumerate(features):
                f["id"] = str(i)
                ids.append(str(i))
                props = f.get("properties", {})
                
                # Buscamos explícitamente llaves de veredas antes que el municipio
                nombres_posibles = [
                    props.get("NOMBRE_VER"), props.get("nombre_ver"), props.get("nom_vereda"), 
                    props.get("vereda"), props.get("bar_ccnmbr"), props.get("comu_nmbre"), props.get("mpio_cnmbr")
                ]
                nombre = next((str(n).title() for n in nombres_posibles if n is not None and str(n).strip() != ""), "Polígono")
                nombres.append(nombre)
                
                # Población (o simulador de calor temporal)
                pob = props.get("poblacion", props.get("habitantes", props.get("Pob_Total", None)))
                if pob is None:
                    pob = (len(nombre) * 314) % 8000 + 800
                else:
                    pob = float(pob)
                poblaciones.append(pob)
                
            df_mapa = pd.DataFrame({"id": ids, "Nombre": nombres, "Habitantes": poblaciones})
            
            fig_map = px.choropleth_mapbox(
                df_mapa, geojson=geojson_data, locations="id", color="Habitantes",
                hover_name="Nombre", mapbox_style="carto-positron",
                center={"lat": datos_mapa["centro"]["lat"], "lon": datos_mapa["centro"]["lon"]},
                zoom=10 if nivel_backend == "MUNICIPAL" else 7, opacity=0.75,
                color_continuous_scale="YlOrRd"
            )
            
            fig_map.update_layout(
                margin={"r":0,"t":0,"l":0,"b":0}, 
                coloraxis_colorbar=dict(
                    title="Habitantes", thicknessmode="pixels", thickness=15, 
                    lenmode="pixels", len=200, yanchor="bottom", y=0.05, 
                    xanchor="right", x=0.95, bgcolor="rgba(255,255,255,0.7)"
                )
            )
            fig_map.update_traces(marker_line_width=0.5, marker_line_color="rgba(255,255,255,0.8)")
            
            with c_mapa:
                st.plotly_chart(fig_map, use_container_width=True)
                
        elif resp_mapa.status_code == 404:
            with c_mapa: 
                st.warning(f"⚠️ El polígono de **{territorio_sel}** no existe en tu archivo GeoJSON Maestro actual.")
        else:
            with c_mapa: 
                st.error(f"Error de mapa: {resp_mapa.text}")


        # ---------------------------------------------------------
        # 📊 4.2 RENDERIZAR PIRÁMIDE POBLACIONAL
        # ---------------------------------------------------------
        if resp_piramide.status_code == 200:
            datos_pira = resp_piramide.json()
            edades = datos_pira["edades"]
            hombres = [-val for val in datos_pira["hombres"]]
            mujeres = datos_pira["mujeres"]
            
            fig_pira = go.Figure()
            fig_pira.add_trace(go.Bar(
                y=edades, x=hombres, name='Hombres', orientation='h', 
                marker_color='#3498db', hoverinfo='x', text=[-h for h in hombres], textposition='inside'
            ))
            fig_pira.add_trace(go.Bar(
                y=edades, x=mujeres, name='Mujeres', orientation='h', 
                marker_color='#e74c3c', hoverinfo='x', text=mujeres, textposition='inside'
            ))
            
            fig_pira.update_layout(
                barmode='overlay', 
                title=f"Estructura Poblacional (Base DANE: {datos_pira['anio_base_dane']})", 
                xaxis=dict(title='Población', tickvals=[-max(mujeres), 0, max(mujeres)], ticktext=[str(max(mujeres)), '0', str(max(mujeres))]), 
                yaxis=dict(title='Grupos de Edad'), 
                margin=dict(l=0, r=0, t=40, b=0), 
                height=450
            )
            
            with c_piramide:
                st.plotly_chart(fig_pira, use_container_width=True)
                
        elif resp_piramide.status_code == 404:
            with c_piramide: 
                st.warning(f"⚠️ No hay datos poblacionales DANE registrados para **{territorio_sel}**.")
        else:
            with c_piramide: 
                st.error(f"Error de pirámide: {resp_piramide.text}")


        # ---------------------------------------------------------
        # 📈 4.3 RENDERIZAR CURVA HISTÓRICA
        # ---------------------------------------------------------
        if resp_proyeccion.status_code == 200:
            datos_proy = resp_proyeccion.json()
            serie = datos_proy["serie_historica"]
            anios = serie["anios"]
            
            fig_curva = go.Figure()
            colores = ['#2ecc71', '#e67e22', '#9b59b6', '#34495e']
            idx = 0
            
            for area, valores in serie.items():
                if area != "anios":
                    fig_curva.add_trace(go.Scatter(
                        x=anios, y=valores, mode='lines+markers', name=area, 
                        line=dict(width=3, color=colores[idx % len(colores)]), marker=dict(size=6)
                    ))
                    idx += 1
                    
            fig_curva.update_layout(
                title=f"Evolución y Proyección Demográfica: {territorio_sel} (1985 - {anio_destino})", 
                xaxis=dict(title='Año', tickmode='linear', dtick=5), 
                yaxis=dict(title='Total de Habitantes'), 
                hovermode='x unified', 
                margin=dict(l=0, r=0, t=40, b=0), 
                height=400, 
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            with c_curva:
                st.plotly_chart(fig_curva, use_container_width=True)
                
        elif resp_proyeccion.status_code == 404:
            with c_curva: 
                st.info(f"💡 No hay una proyección matemática guardada para **{territorio_sel}** en la Matriz Maestra. Debes entrenar este modelo para ver su curva.")
        else:
            with c_curva: 
                st.error(f"Error en la proyección: {resp_proyeccion.text}")

    except Exception as e:
        st.error(f"🚨 FastAPI no responde. Detalle: {e}")