# pages/13_🕵️_Detective.py

import os
import sys
import json
import re

import pandas as pd
import geopandas as gpd
import rasterio
from shapely.geometry import box
from sqlalchemy import create_engine, text

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from scipy import stats

# --- 1. CONFIGURACIÓN DE PÁGINA (SIEMPRE PRIMERO) ---
st.set_page_config(page_title="Centro de Diagnóstico", page_icon="🕵️", layout="wide")

# --- 📂 IMPORTACIÓN ROBUSTA DE MÓDULOS ---
try:
    from modules import selectors
    from modules.db_manager import get_engine
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules import selectors
    try:
        from modules.db_manager import get_engine
    except ImportError:
        def get_engine(): return create_engine(st.secrets["DATABASE_URL"])

st.subheader("🕵️ Radiografía de Matrices (Borrar después de usar)")

try:
    engine_sql = get_engine()
    
    q = text("""
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name IN ('matriz_maestra_demografica', 'matriz_maestra_pecuaria', 'matriz_hidro_maestra_sql')
    """)
    
    df_esquema = pd.read_sql(q, engine_sql)
    st.dataframe(df_esquema, use_container_width=True)
    
except Exception as e:
    st.error(f"Error conectando a la BD: {e}")

# ==========================================
# 📂 NUEVO: MENÚ DE NAVEGACIÓN PERSONALIZADO
# ==========================================
selectors.renderizar_menu_navegacion("Detective")

# ==============================================================================
# 🔒 MURO DE SEGURIDAD GLOBAL (ACCESO BETA)
# ==============================================================================
def muro_de_acceso_beta():
    if "beta_unlocked" not in st.session_state:
        st.session_state["beta_unlocked"] = False
        
    if not st.session_state["beta_unlocked"]:
        st.title("🔒 Sihcli-Poter: Fase de Pruebas (Beta)")
        st.info("Esta plataforma científica se encuentra en fase de acceso restringido. Por favor, ingresa la credencial proporcionada por el equipo de investigación.")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            clave_beta = st.text_input("Credencial de Acceso:", type="password")
            if st.button("Ingresar al Gemelo Digital", type="primary", use_container_width=True):
                if clave_beta == st.secrets.get("CLAVE_BETA", "AdminPoter"):
                    st.session_state["beta_unlocked"] = True
                    st.rerun() 
                else:
                    st.error("❌ Credencial incorrecta. Acceso denegado.")
        st.stop() 

muro_de_acceso_beta()

# ==============================================================================
# --- CONTENIDO DE LA PÁGINA (SOLO VISIBLE SI PASAN EL MURO) ---
# ==============================================================================
st.title("🕵️ Centro de Diagnóstico y Detective")
st.markdown("Herramientas forenses para administrador: Evaluación de coordenadas, proyecciones espaciales y auditoría de la base de datos.")
st.divider()

engine = get_engine()

# --- PESTAÑAS PARA ORGANIZAR TODO EL SISTEMA FORENSE ---
tab_coord, tab_dem, tab_bd, tab_pecuario, tab_sonda = st.tabs([
    "🏥 Salud de Coordenadas", 
    "⛰️ Diagnóstico DEM vs Cuencas", 
    "🔍 Explorador de Tablas",
    "📊 Radiografía Censo Pecuario",
    "🩻 Sonda Matriz Hidro (NUEVO)"
])

# ==============================================================================
# TAB 5: SONDA MATRIZ HIDRO (NUEVO DIAGNÓSTICO CIENTÍFICO)
# ==============================================================================
with tab_sonda:
    st.header("🩻 Escáner Profundo de Matrices SQL")
    st.info("Esta sonda analiza directamente Supabase para verificar si las tablas existen y si tienen las columnas correctas (como LLAVE_UNIVERSAL).")
    
    if st.button("🚀 Iniciar Sonda de Diagnóstico", type="primary", use_container_width=True):
        with st.spinner("Conectando con Supabase e interrogando las tablas..."):
            try:
                with engine.connect() as conn:
                    # 1. Buscar tablas candidatas
                    query_tablas = text("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND (table_name ILIKE '%hidro%' OR table_name ILIKE '%matriz%');
                    """)
                    tablas = [row[0] for row in conn.execute(query_tablas).fetchall()]
                    
                    if not tablas:
                        st.error("❌ No se encontró ninguna tabla en Supabase que contenga 'hidro' o 'matriz'.")
                    else:
                        st.success(f"📂 Tablas encontradas en Supabase: `{', '.join(tablas)}`")
                        
                        # 2. Analizar el interior de cada tabla
                        for tabla in tablas:
                            if "hidro" in tabla.lower():
                                st.markdown(f"### 🔍 Analizando tabla: `{tabla}`")
                                try:
                                    df_test = pd.read_sql(f"SELECT * FROM {tabla} LIMIT 5", engine)
                                    columnas = df_test.columns.tolist()
                                    
                                    st.write(f"**Columnas (Primeras 10):** `{columnas[:10]}...`")
                                    
                                    if 'LLAVE_UNIVERSAL' in columnas:
                                        st.success("✅ **¡ÉXITO!** La columna `LLAVE_UNIVERSAL` **SÍ** existe en esta tabla.")
                                        st.dataframe(df_test[['Jerarquia', 'Territorio', 'LLAVE_UNIVERSAL']] if 'Jerarquia' in columnas else df_test.head())
                                    else:
                                        st.error("❌ **ERROR CRÍTICO:** La columna `LLAVE_UNIVERSAL` **NO EXISTE** en esta tabla.")
                                        st.warning("La aplicación nunca encontrará los datos porque está buscando una columna que no está en la base de datos.")
                                        
                                except Exception as e:
                                    st.error(f"Error leyendo la tabla {tabla}: {e}")
                                st.divider()
                                
            except Exception as e:
                st.error(f"Fallo masivo de conexión: {e}")

# ==============================================================================
# TAB 1: BÚSQUEDA DE COORDENADAS
# ==============================================================================
with tab_coord:
    st.header("🏥 Análisis de Integridad Espacial de Estaciones")
    st.subheader("1. Conteo de Salud")
    try:
        df_count = pd.read_sql("""
            SELECT 
                COUNT(*) as total,
                COUNT(latitud) as con_latitud,
                COUNT(longitud) as con_longitud
            FROM estaciones
        """, engine)
        total = df_count.iloc[0]['total']
        validas = df_count.iloc[0]['con_latitud']
        c1, c2 = st.columns(2)
        c1.metric("Total Estaciones en BD", total)
        c2.metric("Con Coordenadas Válidas", validas)
    except Exception as e: st.error(str(e))

    st.subheader("2. Inspección de Columnas (Vista Cruda)")
    try:
        df_all = pd.read_sql("SELECT * FROM estaciones LIMIT 5", engine)
        st.dataframe(df_all)
    except Exception as e: st.error(str(e))

# ==============================================================================
# TAB 2: DIAGNÓSTICO DEM vs CUENCAS
# ==============================================================================
with tab_dem:
    st.header("🗺️ Detective Espacial: Conflicto de Proyecciones")
    PATH_DEM = "data/DemAntioquia_EPSG3116.tif"
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Análisis del DEM (Raster)")
        try:
            with rasterio.open(PATH_DEM) as src:
                st.success(f"✅ DEM Cargado: {PATH_DEM}")
                dem_crs, dem_bounds = src.crs, src.bounds
                st.code(f"CRS DEM:\n{dem_crs}")
        except Exception as e: st.error(f"Error analizando DEM: {e}")
    with c2:
        st.subheader("2. Análisis de Cuenca (Vectorial)")
        try:
            gdf_test = gpd.read_postgis("SELECT * FROM cuencas LIMIT 1", engine, geom_col="geometry")
            if not gdf_test.empty: st.success("✅ Cuenca cargada.")
        except Exception as e: st.error(f"Error consultando Cuenca: {e}")

# ==============================================================================
# TAB 3: EXPLORADOR BD
# ==============================================================================
with tab_bd:
    st.header("🔍 Explorador de Tablas de la Base de Datos")
    try:
        with engine.connect() as conn:
            tables = pd.read_sql("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'", conn)
            selected_table = st.selectbox("Selecciona la tabla a investigar:", tables['table_name'].tolist() if not tables.empty else [])
            if selected_table:
                count = pd.read_sql(text(f"SELECT count(*) as total FROM {selected_table}"), conn).iloc[0]['total']
                st.metric("Filas Totales", count)
    except Exception as e: st.error(str(e))

# ==============================================================================
# TAB 4: SONDAS DE DATOS EXTERNOS
# ==============================================================================
with tab_pecuario:
    st.header("📊 Diagnóstico Forense: Censo Pecuario ICA")
    if st.button("🚀 Ejecutar Radiografía Pecuaria", type="primary"):
        st.success("Ejecutando sonda pecuaria...")