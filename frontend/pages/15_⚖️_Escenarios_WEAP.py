# pages/15_⚖️_Escenarios_WEAP.py

import sys
import os
import streamlit as st
import pandas as pd

# 1. RUTA Y MÓDULOS
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path: sys.path.append(ROOT_DIR)

from modules import selectors, escenarios_weap

st.set_page_config(page_title="SIHCLI | Simulador WEAP", page_icon="⚖️", layout="wide")
selectors.renderizar_menu_navegacion("Escenarios WEAP")

# ==============================================================================
# 🧠 SELECTOR ESPACIAL (TOPOLOGÍA Y GEOMETRÍA)
# ==============================================================================
try:
    _, nombre_zona_raw, _, gdf_zona_raw, nivel_jerarquico_raw = selectors.render_selector_espacial(modo_firma="weap")
except Exception as e:
    st.error(f"Error en selector: {e}"); st.stop()

nombre_zona = st.session_state.get('aleph_lugar', nombre_zona_raw)
nivel_jerarquico = st.session_state.get('aleph_escala', nivel_jerarquico_raw)

if not nombre_zona or str(nombre_zona).strip() in ["", "None", "-- Seleccione --"]:
    st.info("👈 Seleccione un Territorio (Cuenca o Municipio) para iniciar.")
    st.stop()

# Recuperar geometría en caché
gdf_zona = st.session_state.get('aleph_poligono', gdf_zona_raw)

# Extraer parámetros base de la memoria del Aleph para inyectarlos al módulo
territorio_str = nombre_zona[0] if isinstance(nombre_zona, list) else nombre_zona

st.sidebar.markdown("### ⏳ Prospectiva Demográfica")
anio_simulacion = st.sidebar.number_input("Año de Análisis DANE:", min_value=1950, max_value=2100, value=2024, step=1)

# Extracción de la población real desde la nueva BD Dasimétrica
pob_calculada = 150000.0
try:
    from modules.demografia_tools import calcular_poblacion_al_vuelo
    import re
    t_puro = re.sub(r'\s*-\s*\(.*?\)', '', str(territorio_str)).strip()
    df_pob = calcular_poblacion_al_vuelo(t_puro, nivel_jerarquico, "Total", anio_especifico=anio_simulacion)
    if df_pob is not None and not df_pob.empty:
        pob_calculada = float(df_pob['Total'].iloc[0])
except Exception: pass

# ==============================================================================
# 🚀 INYECCIÓN AL MOTOR WEAP
# ==============================================================================
# Variables de rescate si fallan los queries internos
rurh_base = float(st.session_state.get('aleph_concesiones_m3s', 0.0))
oferta_base = float(st.session_state.get('aleph_oferta_m3s', 1.2))

# Llamamos a la super-función del módulo
escenarios_weap.renderizar_motor_escenarios_weap(
    territorio=territorio_str, 
    gdf_zona=gdf_zona, 
    pob_base_sugerida=pob_calculada, 
    anio_simulacion=anio_simulacion,
    rurh_base_m3s=rurh_base,
    oferta_media_sugerida=oferta_base
)