# frontend/app.py

import os
import sys

# =====================================================================
# 🚀 ÁRBITRO FORENSE: Sincronización del motor geoespacial (GDAL/PROJ)
# =====================================================================
try:
    import rasterio
    import pyproj
    
    # Buscamos la base de datos moderna incrustada en rasterio
    rasterio_proj = os.path.join(os.path.dirname(rasterio.__file__), "proj_data")
    pyproj_proj = pyproj.datadir.get_data_dir()
    
    # Obligamos a TODO el sistema a usar la base de datos moderna
    if os.path.exists(rasterio_proj):
        os.environ["PROJ_DATA"] = rasterio_proj  # Para PROJ >= 9.1
        os.environ["PROJ_LIB"] = rasterio_proj   # Para PROJ < 9.1
        pyproj.datadir.set_data_dir(rasterio_proj)
    else:
        os.environ["PROJ_DATA"] = pyproj_proj
        os.environ["PROJ_LIB"] = pyproj_proj
except Exception:
    pass
# =====================================================================

import streamlit as st
import plotly.express as px
import pandas as pd

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="SIHCLI-POTER | Centro de Comando",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 📂 IMPORTACIÓN ROBUSTA DE MÓDULOS ---
try:
    from modules import selectors
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules import selectors

# ==========================================
# 📂 MENÚ DE NAVEGACIÓN PERSONALIZADO
# ==========================================
selectors.renderizar_menu_navegacion("Inicio")

# --- ESTILOS CSS PERSONALIZADOS (MEJORADOS) ---
st.markdown("""
    <style>
    .metric-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #3498db;
        border-top: 1px solid #e0e6ed;
        border-right: 1px solid #e0e6ed;
        border-bottom: 1px solid #e0e6ed;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 12px rgba(0,0,0,0.1);
    }
    .main-header {
        font-size: 2.8rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0px;
        letter-spacing: -0.02em;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #64748b;
        margin-bottom: 25px;
        font-weight: 500;
    }
    .aleph-triad {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
        padding: 18px 22px;
        border-radius: 12px;
        border-left: 5px solid #38bdf8;
        margin-bottom: 16px;
        box-shadow: 0 8px 20px -4px rgba(15, 23, 42, 0.25);
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. ENCABEZADO Y KPIS ---
st.markdown('<p class="main-header">🌊 SIHCLI-POTER</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Sistema de Información Hidroclimática Integrada | Gemelo Digital Territorial</p>', unsafe_allow_html=True)

# Panel de Métricas Globales (Dashboard)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Módulos Analíticos", "17 Especializados", "100% Operativos") 
col2.metric("Resolución Temporal", "1950 - 2070", "Historia + Tiempo Real + Proyecciones")
col3.metric("Cobertura Geográfica", "Región Andina", "Cuencas, Municipios, CARs y Embalses")
col4.metric("Motores de Decisión", "NOAA CPC / WRI / AHP / GEE", "Estándares Globales")

st.divider()

# --- 3. PESTAÑAS PRINCIPALES ---
tab_dashboard, tab_arquitectura, tab_aleph = st.tabs([
    "🎛️ Centro de Comando (Módulos)", 
    "🏗️ Arquitectura del Sistema", 
    "📖 Filosofía (El Aleph)"
])

# =====================================================================
# PESTAÑA 1: CENTRO DE COMANDO (GRID DE NAVEGACIÓN COMPLETO - 17 MÓDULOS)
# =====================================================================
with tab_dashboard:
    # --- EJE 1: SOPORTE BIOFÍSICO ---
    st.markdown("### 🌍 EJE 1: Soporte Biofísico y Observación de la Tierra (Condiciones Base)")
    st.caption("Módulos dedicados a la lectura y modelación del clima global (NOAA CPC), hidrología superficial, subsuelo, embalses y teledetección satelital.")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.page_link("pages/01_🌦️_Clima_e_Hidrologia.py", label="**Clima e Hidrología**", icon="🌦️")
        st.markdown("<small>Tablero telemétrico (IDEAM/SIATA), variabilidad climática, pronósticos NOAA CPC en vivo y proyecciones XGBoost/Prophet.</small>", unsafe_allow_html=True)
    with c2:
        st.page_link("pages/02_💧_Aguas_Subterraneas.py", label="**Aguas Subterráneas**", icon="💧")
        st.markdown("<small>Modelación de recarga potencial de acuíferos, flujo base y resiliencia hidrogeológica (Turc / BFI).</small>", unsafe_allow_html=True)
    with c3:
        st.page_link("pages/03_🗺️_Isoyetas_HD.py", label="**Isoyetas HD y Espacialización**", icon="🗺️")
        st.markdown("<small>Visor SIG sincronizado: Interpolación geoestadística (Kriging/RBF), campos de precipitación y anomalías ENSO.</small>", unsafe_allow_html=True)
        
    c4, c5, c6 = st.columns(3)
    with c4:
        st.page_link("pages/04_🍃_Biodiversidad.py", label="**Biodiversidad**", icon="🍃")
        st.markdown("<small>Monitor de especies (GBIF), conectividad riparia multi-anillo y valoración de servicios ecosistémicos.</small>", unsafe_allow_html=True)
    with c5:
        st.page_link("pages/05_🏔️_Geomorfologia.py", label="**Geomorfología**", icon="🏔️")
        st.markdown("<small>Modelos Digitales de Elevación (DEM), curvas hipsométricas, orden de Strahler y morfometría de cuencas.</small>", unsafe_allow_html=True)
    with c6:
        st.page_link("pages/07_☀️_Evaporacion.py", label="**Evaporación en Embalses y SUDS**", icon="☀️")
        st.markdown("<small>Termodinámica Penman-Monteith en lámina libre, telemetría XM, Día Cero, tecnologías flotantes y contraste financiero SUDS.</small>", unsafe_allow_html=True)

    c_rad1, c_rad2, c_rad3 = st.columns(3)
    with c_rad1:
        st.page_link("pages/14_🌍_Satelite_Terrestre.py", label="**Satélite Terrestre (GEE)**", icon="🌍")
        st.markdown("<small>Conexión en vivo a Google Earth Engine para monitoreo de coberturas Dynamic World a 10m de resolución.</small>", unsafe_allow_html=True)
    with c_rad2:
        st.page_link("pages/17_🛰️_Radar_Meteorologico.py", label="**Radar Meteorológico**", icon="🛰️")
        st.markdown("<small>Observación atmosférica en tiempo real: reflectividad, precipitaciones y corrientes de viento (ECMWF).</small>", unsafe_allow_html=True)
    with c_rad3:
        st.empty()

    st.markdown("<hr style='margin: 12px 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)
    
    # --- EJE 2: METABOLISMO TERRITORIAL ---
    st.markdown("### ⚙️ EJE 2: Metabolismo Territorial (Presiones Antrópicas y Redes)")
    st.caption("Módulos enfocados en la dinámica demográfica, pecuaria, concesiones RURH, vertimientos y topología de sistemas hídricos.")
    
    c7, c8, c8b = st.columns(3)
    with c7:
        st.page_link("pages/06_📈_Modelo_Demografico.py", label="**Modelo Demográfico (Humanos)**", icon="📈")
        st.markdown("<small>Proyecciones poblacionales (DANE) urbanas y rurales multimodelo con inyección a la Memoria Global.</small>", unsafe_allow_html=True)
        st.write("") 
        st.page_link("pages/06_🐄_Modelo_Pecuario.py", label="**Modelo Pecuario (Animales)**", icon="🐄")
        st.markdown("<small>Proyecciones de crecimiento (ICA) para Bovinos, Porcinos y Aves en escalas municipales e hidrográficas.</small>", unsafe_allow_html=True)
        
    with c8:
        st.page_link("pages/07_💧_Calidad_y_Vertimientos.py", label="**Calidad y Vertimientos**", icon="🧪")
        st.markdown("<small>Modelación de cargas contaminantes DBO5, cinética de autodepuración (Streeter-Phelps) y presión por nutrientes.</small>", unsafe_allow_html=True)
        st.write("") 
        st.page_link("pages/08_🔗_Sistemas_Hidricos_Territoriales.py", label="**Sistemas Hídricos Territoriales**", icon="🔗")
        st.markdown("<small>Topología de redes de abastecimiento y generación, diagramas de Sankey y huella hídrica regional.</small>", unsafe_allow_html=True)

    with c8b:
        st.page_link("pages/16_🏭_Inyeccion_RURH.py", label="**Inyección y Presiones RURH**", icon="🏭")
        st.markdown("<small>Motor ETL geoespacial: consolida concesiones superficiales/subterráneas y usuarios del recurso hídrico en la nube.</small>", unsafe_allow_html=True)

    st.markdown("<hr style='margin: 12px 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

    # --- EJE 3: SÍNTESIS Y ESTRATEGIA (DSS) ---
    st.markdown("### 🧠 EJE 3: Síntesis y Estrategia (Sistemas de Soporte a la Decisión - DSS)")
    st.caption("Plataformas gerenciales para planeación integrada (Pasado-Presente-Futuro), balance WEAP, optimización financiera y priorización predial.")
    
    c9, c10, c10b = st.columns(3)
    with c9:
        st.page_link("pages/09_🧠_Toma_de_Decisiones.py", label="**Toma de Decisiones (El Aleph)**", icon="🧠")
        st.markdown("<small>Tablero Maestro: Velocímetros ISHI, portafolios WRI (VWBA), optimizador ROI, Análisis Costo-Beneficio y priorización predial 3D.</small>", unsafe_allow_html=True)
    with c10:
        st.page_link("pages/10_⚖️_Simulador_Integral.py", label="**Simulador Integral (Hidro-WEAP)**", icon="⚖️")
        st.markdown("<small>Balance biofísico mensual, efecto esponja subterráneo, gestión hipsométrica 3D y estrés hidrosocial acoplado al ONI en vivo.</small>", unsafe_allow_html=True)
    with c10b:
        st.page_link("pages/10_👑_Panel_Administracion.py", label="**Panel de Administración**", icon="👑")
        st.markdown("<small>Gobernanza de datos, aduana SIG y sincronización de matrices maestras en Supabase (PostgreSQL/PostGIS).</small>", unsafe_allow_html=True)

    st.markdown("<hr style='margin: 12px 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

    # --- EJE 4: SOPORTE TÉCNICO Y HERRAMIENTAS ---
    st.markdown("### 🛠️ EJE 4: Ingeniería de Datos, Quirófano SQL y Documentación")
    st.caption("Utilidades del sistema para geoprocesamiento, fusión hidrometeorológica (IDEAM/SIATA), auditoría espacial y manuales.")
    
    c11, c12, c13 = st.columns(3)
    with c11:
        st.page_link("pages/11_⚙️_Generador.py", label="**Generador y Quirófano SQL**", icon="⚙️")
        st.markdown("<small>Intersecciones espaciales, convertidor GeoJSON/SHP, puente SIATA en tiempo real y depuración profunda de Supabase.</small>", unsafe_allow_html=True)
    with c12:
        st.page_link("pages/12_📚_Ayuda_y_Docs.py", label="**Ayuda y Documentación**", icon="📚")
        st.markdown("<small>Manuales metodológicos, ecuaciones gobernantes y guía arquitectónica del gemelo digital.</small>", unsafe_allow_html=True)
    with c13:
        st.page_link("pages/13_🕵️_Detective.py", label="**Detective Espacial**", icon="🕵️")
        st.markdown("<small>Auditoría forense de bases de datos, integridad de llaves universales y diagnóstico de proyecciones (CRS).</small>", unsafe_allow_html=True)

# =====================================================================
# PESTAÑA 2: ARQUITECTURA DEL SISTEMA (SUNBURST DE 17 MÓDULOS)
# =====================================================================
with tab_arquitectura:
    st.markdown("### Mapa Topológico del Sistema (17 Módulos Integrados)")
    st.info("Visualización jerárquica de los cuatro ejes estructurales de SIHCLI-POTER y sus módulos analíticos.")
    
    ids = [
        'SIHCLI-POTER',
        'Soporte Biofísico', 'Metabolismo Territorial', 'Síntesis Estratégica', 'Herramientas',
        # Soporte Biofísico (8)
        'Clima e Hidrología', 'Aguas Subterráneas', 'Isoyetas HD', 'Biodiversidad',
        'Geomorfología', 'Evaporación y Embalses', 'Satélite Terrestre', 'Radar Meteorológico',
        # Metabolismo Territorial (5)
        'Modelo Demográfico', 'Modelo Pecuario', 'Calidad y Vertimientos', 'Sistemas Hídricos', 'Inyección RURH',
        # Síntesis Estratégica (3)
        'Toma de Decisiones', 'Simulador Integral WEAP', 'Panel Administración',
        # Herramientas (3)
        'Generador y Quirófano SQL', 'Ayuda y Docs', 'Detective Espacial'
    ]
            
    parents = [
        '',
        'SIHCLI-POTER', 'SIHCLI-POTER', 'SIHCLI-POTER', 'SIHCLI-POTER',
        # Soporte Biofísico
        'Soporte Biofísico', 'Soporte Biofísico', 'Soporte Biofísico', 'Soporte Biofísico',
        'Soporte Biofísico', 'Soporte Biofísico', 'Soporte Biofísico', 'Soporte Biofísico',
        # Metabolismo Territorial
        'Metabolismo Territorial', 'Metabolismo Territorial', 'Metabolismo Territorial', 'Metabolismo Territorial', 'Metabolismo Territorial',
        # Síntesis Estratégica
        'Síntesis Estratégica', 'Síntesis Estratégica', 'Síntesis Estratégica',
        # Herramientas
        'Herramientas', 'Herramientas', 'Herramientas'
    ]
                
    values = [
        100,
        40, 25, 23, 12,
        # Soporte Biofísico (8 x 5.0 = 40)
        5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0,
        # Metabolismo Territorial (5 x 5.0 = 25)
        5.0, 5.0, 5.0, 5.0, 5.0,
        # Síntesis Estratégica (9 + 9 + 5 = 23)
        9.0, 9.0, 5.0,
        # Herramientas (3 x 4.0 = 12)
        4.0, 4.0, 4.0
    ]

    if len(ids) == len(parents) == len(values):
        df = pd.DataFrame(dict(ids=ids, parents=parents, values=values))
        fig = px.sunburst(
            df, names='ids', parents='parents', values='values',
            branchvalues='total',
            color='parents',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig.update_layout(margin=dict(t=20, l=0, r=0, b=0), height=620, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")

# =====================================================================
# PESTAÑA 3: EL ALEPH (FILOSOFÍA DEL GEMELO DIGITAL)
# =====================================================================
with tab_aleph:
    st.markdown("### La Visión Detrás de SIHCLI-POTER: Un Aleph Hidroclimático")
    
    st.markdown("""
    <div class="aleph-triad">
        <h4 style="color: #38bdf8; margin-top: 0; margin-bottom: 8px;">🔮 El Punto donde Convergen el Pasado, el Presente y el Futuro del Agua</h4>
        <p style="margin-bottom: 0; font-size: 0.96rem; line-height: 1.55; color: #e2e8f0;">
            Inspirado en la célebre imagen literaria de <b>Jorge Luis Borges (El Aleph, 1945)</b> —aquella pequeña esfera resplandeciente desde la cual es posible contemplar simultáneamente todos los lugares y tiempos del cosmos con nitidez y sin que se confundan—, <b>SIHCLI-POTER</b> articula en un solo punto de observación la memoria histórica de las cuencas, el pulso telemétrico del presente y los escenarios prospectivos que guiarán las decisiones del futuro.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c_aleph1, c_aleph2, c_aleph3 = st.columns(3)
    
    with c_aleph1:
        st.markdown("""
        #### ⏪ 1. El Pasado (La Memoria)
        * **Series Históricas (1950–2026):** Más de un millón de registros depurados de precipitación (IDEAM/SIATA) e índices oceánicos globales.
        * **Geología y Morfometría:** El relieve esculpido de los Andes, sus cañones, acuíferos y zonas de vida.
        * **Huella de Conservación:** El inventario geoespacial de cada predio y hectárea ya restaurada en el territorio.
        """)
        
    with c_aleph2:
        st.markdown("""
        #### ⏺️ 2. El Presente (El Latido Activo)
        * **Telemetría Oceánica y Atmosférica:** Conexión directa con el Climate Prediction Center de la NOAA (ONI, SST Niño 3.4, SOI, IOD) y radares meteorológicos.
        * **Metabolismo Territorial:** La presión viva de la población, las actividades productivas, las concesiones (RURH) y las cargas orgánicas.
        * **Termodinámica de Embalses:** El balance diario entre caudales de entrada, evaporación de lámina libre y niveles operativos (XM).
        """)

    with c_aleph3:
        st.markdown("""
        #### ⏩ 3. El Futuro (El Oráculo y la Acción)
        * **Modelación Predictiva:** Proyecciones autoregresivas (XGBoost, Prophet, Plumas NOAA) y curvas de cambio climático a 2050.
        * **Simulación Hidrosocial (WEAP):** Identificación anticipada del Día Cero y de los cuellos de botella entre oferta neta y demanda.
        * **Decisión Multicriterio (WRI / AHP):** Portafolios óptimos que combinan infraestructura verde (SbN), gris (PTAR/SUDS) y flotante (control de evaporación).
        """)

# --- FOOTER ---
st.caption("© 2026 omejia CV | SIHCLI-POTER v3.0 | Un Aleph Hidroclimático: Plataforma de Inteligencia Territorial")
st.caption("💧 SIHCLI-POTER | Sistema de Información Hídrica y Climática Integrada")