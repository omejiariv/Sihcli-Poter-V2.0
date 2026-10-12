import streamlit as st
import pyeto
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import os
import sys

# -----------------------------------------
# Configuración e Integración al Sistema
# -----------------------------------------
st.set_page_config(page_title="Piloto Piedras Blancas - Plan de Choque", page_icon="🚨", layout="wide")

try:
    from modules import selectors
    from modules.utils import encender_gemelo_digital
    selectors.renderizar_menu_navegacion("Evaporación")
    encender_gemelo_digital()
except Exception:
    pass

# -----------------------------------------
# Motor Termodinámico Penman-Monteith (Sincronizado con 07_Evaporacion.py)
# -----------------------------------------
def calcular_penman_piedras_blancas(alt, lat, dia, tmax, tmin, rh, viento, rad_sol, albedo):
    lat_rad = pyeto.deg2rad(lat)
    t_media = (tmax + tmin) / 2.0
    P_atm = pyeto.atm_pressure(alt)
    gamma_const = pyeto.psy_const(P_atm)
    delta_svp = pyeto.delta_svp(t_media)
    
    es_tmax = pyeto.svp_from_t(tmax)
    es_tmin = pyeto.svp_from_t(tmin)
    es_val = (es_tmax + es_tmin) / 2.0
    ea_val = pyeto.avp_from_rhmean(es_tmin, es_tmax, rh)
    vpd_val = es_val - ea_val

    rns_val = pyeto.net_in_sol_rad(rad_sol, albedo=albedo)
    sol_dec_val = pyeto.sol_dec(dia)
    sha_val = pyeto.sunset_hour_angle(lat_rad, sol_dec_val)
    ird_val = pyeto.inv_rel_dist_earth_sun(dia)
    ra_val = pyeto.et_rad(lat_rad, sol_dec_val, sha_val, ird_val)
    rso_val = pyeto.cs_rad(alt, ra_val)
    
    rnl_val = pyeto.net_out_lw_rad(tmin, tmax, rad_sol, rso_val, ea_val)
    rn_val = rns_val - rnl_val

    term_rad = (0.408 * delta_svp * rn_val) / (delta_svp + gamma_const)
    E_a_val = 2.626 * (1 + 0.536 * viento) * vpd_val
    term_aero = (gamma_const * E_a_val) / (delta_svp + gamma_const)
    evap_total_dia = term_rad + term_aero
    
    return evap_total_dia, term_rad, term_aero, vpd_val, rn_val, P_atm

# --- CABEZOTE INSTITUCIONAL DE LOGOS ---
col_l1, col_l2, col_l3, col_espacio = st.columns([1.2, 1.2, 1.2, 4])
with col_l1:
    st.image("CuencaVerdeLogo_V1.JPG", use_container_width=True)
with col_l2:
    st.image("logo_epm.png", use_container_width=True)
with col_l3:
    st.image("logo_distritoMedellin.png", use_container_width=True)

# -----------------------------------------
# Encabezado Ejecutivo
# -----------------------------------------
st.title("🚨 Plan de Choque Socio-Hidroclimático: Proyecto Piloto Embalse Piedras Blancas")
st.markdown("""
**Alerta Temprana para Tomadores de Decisiones (Octubre 2026):** Aprovechamiento estratégico de las lluvias remanentes de **octubre y noviembre de 2026** mediante tecnologías de control evaporativo para mitigar el déficit de abastecimiento proyectado para **diciembre 2026 y el primer trimestre de 2027 (Ene-Mar)** bajo el fenómeno de **El Niño**.
""")

# Métricas de Contexto de Piedras Blancas
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📍 Ubicación", "Santa Elena, Medellín", "6.29° N, -75.49° W")
c2.metric("📦 Volumen Reserva", "0.50 Mm³", "Alta sensibilidad", delta_color="inverse")
c3.metric("🌊 Espejo de Agua", "~20.0 ha", "Morfología 'Bandeja'")
c4.metric("⛰️ Altitud y Zona Vida", "2,350 msnm", "bmh-MB (Holdridge)")
c5.metric("⏳ Ventana de Acción", "Oct - Nov 2026", "Recarga + Sellado")

st.markdown("---")

tab_ciclo, tab_fisica, tab_piloto, tab_ruta = st.tabs([
    "🔄 1. Ciclo Hidrológico y Gobernabilidad",
    "☀️ 2. Física de la Evaporación y Tecnologías",
    "🧮 3. Simulador Proyecto Piloto (Dic 26 - Mar 27)",
    "🚀 4. Hoja de Ruta Crítica (Oct 2026 - 1T 2027)"
])

# -----------------------------------------
# TAB 1: Ciclo Hidrológico e Intervención Humana
# -----------------------------------------
with tab_ciclo:
    st.subheader("¿Dónde tenemos verdadera capacidad de maniobra humana antes de Diciembre 2026?")
    st.markdown("""
    En el contexto del fenómeno de **El Niño**, el sistema de Piedras Blancas sufre un efecto tijera: caen las entradas por lluvia y se disparan las salidas por evaporación y demanda. Al analizar las tres variables troncales del ciclo hidrológico, queda en evidencia por qué **intervenir la evaporación es la única decisión con impacto inmediato**:
    """)
    
    col_p, col_q, col_e = st.columns(3)
    with col_p:
        st.error("🌧️ **1. Precipitación ($P$) — Control: NULO (~0%)**")
        st.markdown("""
        * **Naturaleza:** Gobernada por anomalías macroclimáticas del Pacífico (ENSO) y la ZCIT.
        * **Posibilidad de Intervención:** Nula a escala operativa. La siembra de nubes es ineficaz en condiciones de subsidencia atmosférica seca de El Niño.
        * **Estrategia Oct-Nov:** Capturar pasivamente cada milímetro de las lluvias de octubre y noviembre antes de que se cierre la temporada húmeda.
        """)
    with col_q:
        st.warning("🌲 **2. Caudales Base ($Q_b$) — Control: LENTO (5-15 años)**")
        st.markdown("""
        * **Naturaleza:** Regulación hídrica subsuperficial del bosque altoandino (bmh-MB) y suelos orgánicos de Santa Elena.
        * **Posibilidad de Intervención:** Alta a **largo plazo** vía Soluciones Basadas en la Naturaleza (SbN), restauración ecológica y conservación predial.
        * **Limitación en la Crisis:** Indispensable estructuralmente, pero sembrar hoy no generará nuevos caudales base para enero de 2027.
        """)
    with col_e:
        st.success("☀️ **3. Evaporación ($E$) — Control: INMEDIATO (50% al 85%)**")
        st.markdown("""
        * **Naturaleza:** Pérdida física concentrada en una superficie acotada y accesible: las ~20 ha del espejo de agua de Piedras Blancas.
        * **Posibilidad de Intervención:** **Directa, modular e inmediata.** Cubrir parcialmente el espejo de agua bloquea la radiación y el viento desde el primer día.
        * **Estrategia Oct-Nov:** Es la única llave de ingeniería que podemos cerrar en semanas para retener el agua almacenada.
        """)

    df_gov = pd.DataFrame({
        "Variable del Ciclo": ["1. Precipitación (Lluvias)", "2. Caudales Base (Restauración SbN)", "3. Evaporación (Coberturas Flotantes)"],
        "Capacidad de Control Humano (%)": [2, 50, 85],
        "Efectividad para la Crisis Dic 2026 - Mar 2027 (%)": [0, 10, 95]
    })
    fig_gov = px.bar(
        df_gov, y="Variable del Ciclo", x=["Capacidad de Control Humano (%)", "Efectividad para la Crisis Dic 2026 - Mar 2027 (%)"],
        barmode="group", orientation="h", title="Comparativa de Gobernabilidad y Respuesta Operativa",
        color_discrete_sequence=["#38bdf8", "#10b981"]
    )
    fig_gov.update_layout(height=320, margin=dict(t=40, b=10, l=10, r=10), xaxis_title="Porcentaje (%)")
    st.plotly_chart(fig_gov, use_container_width=True)

# -----------------------------------------
# TAB 2: Mecanismos Físicos y Tecnologías
# -----------------------------------------
with tab_fisica:
    st.subheader("Mecanismos Termodinámicos en Piedras Blancas (2,350 msnm)")
    col_rad, col_vie = st.columns(2)
    with col_rad:
        st.info("☀️ **Motor Radiativo (Energía Solar Neta - $R_n$)**")
        st.markdown("""
        * **Bajo Albedo ($\alpha \\approx 0.08$):** El agua libre absorbe el 92% de la energía solar incidente.
        * **Rompimiento del Manto Nuboso:** Piedras Blancas suele estar protegido por la niebla del Bosque Muy Húmedo Montano Bajo. Durante **El Niño**, los cielos despejados a 2,350 msnm disparan la radiación de onda corta, calentando la capa superficial y elevando la presión de saturación de vapor ($e_s$).
        """)
    with col_vie:
        st.info("💨 **Motor Aerodinámico (Viento y Déficit de Presión de Vapor - $VPD$)**")
        st.markdown("""
        * **La 'Sed' Atmosférica ($VPD = e_s - e_a$):** Con menor humedad relativa en El Niño, el aire seco succiona humedad continuamente.
        * **Arrastre Turbulento ($u_2$):** Los vientos alisios de diciembre a marzo barren la capa límite de humedad sobre las 20 hectáreas tipo 'bandeja' de Piedras Blancas, renovando el aire seco e impidiendo el equilibrio higrométrico.
        """)
    
    st.markdown("---")
    st.subheader("Matriz Científica y Tecnológica de Control Evaporativo para Piedras Blancas")
    df_tech = pd.DataFrame({
        "Tecnología": [
            "⭐ Piloto Híbrido (Solar FPV + HexaCovers)",
            "☀️ Paneles Solares Flotantes (FPV)",
            "⬡ Módulos Hexagonales (HexaCovers)",
            "🌑 Esferas Flotantes Confinadas (Shade Balls)",
            "🧪 Monocapas Químicas Biodegradables"
        ],
        "Mecanismo Físico": [
            "Doble barrera: Generación eléctrica + sello modular",
            "Sombra fotovoltaica + refrigeración del panel (+10% efic.)",
            "Barrera mecánica auto-ensamblable (90% cobertura local)",
            "Reflexión fotónica y bloqueo de interfaz aire-agua",
            "Película de alcohol graso de 1 molécula de espesor"
        ],
        "Reducción Evap. (en área cubierta)": ["70% - 80%", "60% - 70%", "80% - 90%", "80% - 85%", "15% - 30%"],
        "Tiempo de Despliegue": ["4 a 8 semanas (por fases)", "6 a 10 semanas", "2 a 3 semanas (Inmediato)", "2 semanas (con Booms)", "48 horas (requiere redosificar)"],
        "Retorno Financiero (ROI)": ["3.5 - 4.2 Años", "2.5 - 4.0 Años (Ley 1715)", "7.0 - 9.0 Años", "5.5 - 7.5 Años", "Gasto operativo (OPEX)"]
    })
    st.dataframe(df_tech, use_container_width=True, hide_index=True)

# -----------------------------------------
# TAB 3: Simulador del Proyecto Piloto en Piedras Blancas
# -----------------------------------------
with tab_piloto:
    st.subheader("🎛️ Simulador Termodinámico y Financiero: Estiaje Dic 2026 - Mar 2027 (120 Días)")
    
    col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
    with col_cfg1:
        area_pb_ha = st.slider("🌊 Espejo de Agua Piedras Blancas (ha)", 12.0, 26.0, 20.0, 1.0)
        pct_cobertura = st.slider("🛡️ Cobertura del Proyecto Piloto (%)", 15, 70, 40, 5)
    with col_cfg2:
        tech_piloto = st.selectbox("🔧 Configuración Tecnológica", [
            "⭐ Piloto Híbrido (50% FPV Solar + 50% HexaCovers)",
            "☀️ 100% Solares Flotantes (Floatovoltaics - FPV)",
            "⬡ 100% Módulos Hexagonales (Despliegue Rápido)",
            "🌑 100% Esferas de Sombra Confinadas"
        ])
        escenario_nino = st.selectbox("🔥 Intensidad El Niño (Dic 26 - Mar 27)", [
            "El Niño Moderado-Fuerte (+2°C, -12% HR, +3 MJ/m²)",
            "El Niño Severo + Vientos Alisios (+3°C, -18% HR, +4.5 MJ/m²)",
            "Condición Histórica Media (Altiplano Santa Elena)"
        ])
    with col_cfg3:
        consumo_l_hab = st.number_input("🚰 Dotación Neta (L/hab-día)", 100, 250, 150, 10)
        dias_crisis = st.slider("📅 Ventana Crítica (Dic 2026 - Mar 2027)", 60, 150, 120, 15)

    # Parámetros climáticos base Santa Elena / Piedras Blancas (2,350 msnm)
    tmax_b, tmin_b, rh_b, u2_b, rs_b = 21.5, 11.5, 78.0, 2.2, 17.5
    if "Moderado-Fuerte" in escenario_nino:
        tmax_b += 2.0; rh_b -= 12.0; rs_b += 3.0; u2_b += 0.6
    elif "Severo" in escenario_nino:
        tmax_b += 3.0; rh_b -= 18.0; rs_b += 4.5; u2_b += 1.2

    evap_dia_mm, t_rad, t_aero, vpd_kpa, rn_mj, patm = calcular_penman_piedras_blancas(
        2350.0, 6.29, 15, tmax_b, tmin_b, rh_b, u2_b, rs_b, 0.08
    )

    if "Híbrido" in tech_piloto:
        eff_local, mwp_ha, capex_ha = 0.75, 0.625, 0.36
    elif "Solares" in tech_piloto:
        eff_local, mwp_ha, capex_ha = 0.65, 1.25, 0.56
    elif "Hexagonales" in tech_piloto:
        eff_local, mwp_ha, capex_ha = 0.85, 0.0, 0.19
    else:
        eff_local, mwp_ha, capex_ha = 0.82, 0.0, 0.13

    area_intervenida_ha = area_pb_ha * (pct_cobertura / 100.0)
    factor_reduccion_total = (pct_cobertura / 100.0) * eff_local

    perdida_sin_piloto_m3_dia = evap_dia_mm * area_pb_ha * 10.0
    perdida_con_piloto_m3_dia = perdida_sin_piloto_m3_dia * (1.0 - factor_reduccion_total)
    agua_salvada_m3_dia = perdida_sin_piloto_m3_dia - perdida_con_piloto_m3_dia
    agua_salvada_periodo = agua_salvada_m3_dia * dias_crisis

    personas_abastecidas = (agua_salvada_periodo * 1000.0) / (consumo_l_hab * dias_crisis)
    mwp_instalados = area_intervenida_ha * mwp_ha
    capex_estimado = area_intervenida_ha * capex_ha

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("💧 Evap. Sin Piloto", f"{evap_dia_mm:.2f} mm/día", f"{perdida_sin_piloto_m3_dia:,.0f} m³/día", delta_color="inverse")
    m2.metric("🛡️ Agua Salvada Total", f"{agua_salvada_periodo:,.0f} m³", f"En {dias_crisis} días críticos")
    m3.metric("🏊‍♂️ Escala Física", f"{agua_salvada_periodo/2500:.1f} Piscinas", "Olímpicas retenidas")
    m4.metric("👥 Población Protegida", f"{personas_abastecidas:,.0f} Hab", f"Durante {dias_crisis} días")
    m5.metric("💰 CAPEX Neto Est.", f"${capex_estimado:.2f}M USD", f"{mwp_instalados:.1f} MWp Solar" if mwp_instalados > 0 else "100% Barrera Física")

# -----------------------------------------
# TAB 4: Hoja de Ruta para Tomadores de Decisiones
# -----------------------------------------
with tab_ruta:
    st.subheader("🚀 Cronograma de Acción Proactiva: Ventana Octubre 2026 – Marzo 2027")
    st.success("""
    **Mensaje Clave para Junta Directiva y Alcaldía / EPM:** Las lluvias de **octubre y primera mitad de noviembre de 2026** llenarán el vaso de Piedras Blancas, pero si el espejo de agua queda descubierto en diciembre, la atmósfera bajo El Niño succionará decenas de miles de metros cúbicos. **El momento de contratar e instalar el piloto es AHORA.**
    """)
    st.markdown("""
    1. **Octubre 2026 (Decisiones y Contratación Express):** Aprobación presupuestal del Piloto en Piedras Blancas (8 ha de intervención inicial). Adquisición inmediata de módulos flotantes de despliegue rápido (HexaCovers/Esferas) y estructuración del bloque Solar Flotante (FPV) bajo beneficios tributarios de las Leyes 1715 y 2099.
    2. **Noviembre 2026 (Cosecha de Lluvias y Sellado Hídrico):** Cierre de compuertas / optimización operativa para alcanzar el 100% de la cota con las lluvias de noviembre y vaciado directo de los módulos flotantes sobre el espejo de agua antes del 30 de noviembre.
    3. **Diciembre 2026 (Escudo Activo e Integración Energética):** Entrada de los vientos alisios y radiación de fin de año con la barrera evaporativa ya funcionando. Reducción de floraciones algales y montaje del bloque fotovoltaico flotante.
    4. **Enero - Marzo 2027 (Resiliencia en el Pico de El Niño):** Preservación efectiva de más de **30,000 a 40,000 m³ de agua potable** en la reserva alta de Medellín y levantamiento de datos reales para escalar el proyecto al **Embalse La Fe** y **Río Grande II**.
    """)