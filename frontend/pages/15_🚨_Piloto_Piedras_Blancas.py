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

# Estilos CSS ejecutivos inspirados en presentacion_piedras_blancas.html
st.markdown("""
<style>
    .exec-card {
        background: linear-gradient(145deg, #0f172a, #1e293b);
        color: #f8fafc;
        padding: 18px 20px;
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.22);
        margin-bottom: 12px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.25);
    }
    .exec-card h4 {
        color: #ffffff !important;
        margin-top: 0;
        margin-bottom: 6px;
        font-size: 1.05rem;
    }
    .exec-card p {
        color: #cbd5e1;
        font-size: 0.88rem;
        margin-bottom: 0;
        line-height: 1.45;
    }
    .border-sky { border-left: 5px solid #38bdf8 !important; }
    .border-amber { border-left: 5px solid #f59e0b !important; }
    .border-rose { border-left: 5px solid #f43f5e !important; }
    .border-emerald { border-left: 5px solid #10b981 !important; }
    .border-purple { border-left: 5px solid #a855f7 !important; }
    .formula-box {
        background-color: #020617;
        color: #38bdf8;
        font-family: monospace;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #1e293b;
        margin-top: 8px;
        font-size: 0.86rem;
    }
    .badge-exec {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 999px;
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.45);
        color: #d97706;
        font-weight: 700;
        font-size: 0.78rem;
        letter-spacing: 0.04em;
    }
</style>
""", unsafe_allow_html=True)

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

# --- CABEZOTE INSTITUCIONAL DE LOGOS (Conectado a Supabase Storage) ---
URL_BASE_LOGOS = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/imagenes"

col_logos, col_espacio = st.columns([1.4, 1.6])
with col_logos:
    st.markdown(f"""
    <div style="display: inline-flex; align-items: center; gap: 18px; background: rgba(255, 255, 255, 0.96); padding: 8px 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12); border: 1px solid #e2e8f0;">
        <img src="{URL_BASE_LOGOS}/CuencaVerdeLogo_V1.JPG" alt="CuencaVerde" style="height: 44px; width: auto; object-fit: contain;">
        <div style="height: 28px; width: 1px; background-color: #cbd5e1;"></div>
        <img src="{URL_BASE_LOGOS}/logo_epm.png" alt="EPM" style="height: 36px; width: auto; object-fit: contain;">
        <div style="height: 28px; width: 1px; background-color: #cbd5e1;"></div>
        <img src="{URL_BASE_LOGOS}/logo_distritoMedellin.png" alt="Alcaldía de Medellín" style="height: 44px; width: auto; object-fit: contain;">
    </div>
    """, unsafe_allow_html=True)

with col_espacio:
    st.markdown("""
    <div style="text-align: right; padding-top: 14px;">
        <span class="badge-exec">🛡️ ALIANZA POR LA SEGURIDAD HÍDRICA • DOCUMENTO DE DECISIÓN EJECUTIVA (OCTUBRE 2026)</span>
    </div>
    """, unsafe_allow_html=True)

# -----------------------------------------
# Encabezado Ejecutivo
# -----------------------------------------
st.title("🚨 Blindaje Evaporativo del Embalse Piedras Blancas ante El Niño (2026–2027)")
st.markdown("""
**Proyecto Piloto de Adaptación Hidroclimática Inmediata:** Estrategia proactiva para cosechar las lluvias remanentes de **octubre y noviembre de 2026** y sellar la lámina de agua mediante tecnologías flotantes, mitigando el riesgo de desabastecimiento y eutrofización en **diciembre de 2026 y el 1T de 2027 (Ene–Mar)**.
""")

# Métricas de Contexto de Piedras Blancas
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📍 Ubicación", "Santa Elena, Medellín", "6.29° N, -75.49° W")
c2.metric("📦 Volumen Reserva", "0.50 Mm³ (500,000 m³)", "Acueducto EPM (Sin XM)", delta_color="inverse")
c3.metric("🌊 Espejo de Agua", "~20.0 ha", "Ratio: 0.025 Mm³/ha ('Bandeja')")
c4.metric("⛰️ Altitud y Zona Vida", "2,350 msnm", "bmh-MB (~76.5 kPa)")
c5.metric("⏳ Ventana de Acción", "Oct - Nov 2026", "Recarga + Sellado")

st.markdown("---")

tab_diag, tab_fisica, tab_piloto, tab_cobeneficios, tab_ruta = st.tabs([
    "🏔️ 1. Diagnóstico Territorial y Gobernabilidad",
    "☀️ 2. Física Penman-Monteith y Tecnologías",
    "🧮 3. Simulador Proyecto Piloto y Caso de Negocio",
    "💎 4. Co-Beneficios Multidimensionales (PTAP / Arví)",
    "🚀 5. Hoja de Ruta Crítica y Presentación 16:9"
])

# -----------------------------------------
# TAB 1: Diagnóstico Territorial y Ciclo Hidrológico
# -----------------------------------------
with tab_diag:
    st.subheader("1.1 La Vulnerabilidad de Piedras Blancas: Asimetría en el Sistema de Reservas (EPM)")
    col_asim, col_fact = st.columns([1.05, 1.35])
    
    with col_asim:
        st.markdown("""
        A diferencia de los grandes embalses del sistema interconectado y de acueducto metropolitano, **Piedras Blancas** posee una capacidad volumétrica reducida y una geometría altamente expuesta:
        """)
        df_embalses = pd.DataFrame({
            "Embalse": ["Río Grande II", "La Fe (El Retiro)", "Piedras Blancas (Medellín)"],
            "Volumen Útil (Mm³)": [138.8, 11.1, 0.5],
            "Espejo de Agua (ha)": [1100.0, 145.0, 20.0],
            "Ratio Profundidad (Mm³/ha)": [0.126, 0.077, 0.025]
        })
        fig_emb = px.bar(
            df_embalses, x="Volumen Útil (Mm³)", y="Embalse", orientation="h",
            text="Volumen Útil (Mm³)", color="Embalse",
            color_discrete_sequence=["#38bdf8", "#10b981", "#f59e0b"],
            title="Comparativa Volumétrica del Sistema de Acueducto EPM (Mm³)"
        )
        fig_emb.update_traces(texttemplate='%{text} Mm³', textposition='outside')
        fig_emb.update_layout(height=270, showlegend=False, margin=dict(t=40, b=10, l=10, r=40), xaxis_range=[0, 160])
        st.plotly_chart(fig_emb, use_container_width=True)
        st.caption("📌 *Piedras Blancas es de uso exclusivo para acueducto (no reporta telemetría energética a XM), exigiendo monitoreo hidrometeorológico propio de alta precisión.*")

    with col_fact:
        st.markdown("""
        <div class="exec-card border-amber">
            <h4>☀️ 1. Pérdida de la "Manta Natural" bajo El Niño</h4>
            <p>Ubicado en <i>Bosque Muy Húmedo Montano Bajo (bmh-MB)</i> a ~2,350 msnm, sus bajas temperaturas y nubosidad suelen protegerlo. Con <b>El Niño</b>, se rompe la cobertura nubosa, aumentando la radiación solar directa, la temperatura (+2°C) y la "sed" atmosférica.</p>
        </div>
        <div class="exec-card border-rose">
            <h4>📐 2. Morfología Tipo "Bandeja" (Baja Relación Volumen / Área)</h4>
            <p>Con ~0.5 Mm³ distribuidos en cerca de <b>20 hectáreas de espejo de agua</b>, su ratio morfológico (≈ 0.025 Mm³/ha) lo hace comportarse como una "bandeja" y no como un "vaso" profundo: expone una gran superficie térmica por cada metro cúbico almacenado.</p>
        </div>
        <div class="exec-card border-purple">
            <h4>🧪 3. Presión Social y Riesgo de Eutrofización en Estiaje</h4>
            <p>En diciembre y el 1T de 2027 aumenta la demanda poblacional y turística en Santa Elena y el oriente de Medellín, mientras que la mayor radiación y temperatura del agua aceleran floraciones de cianobacterias que comprometen la calidad del agua cruda.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("1.2 El Ciclo Hidrológico: ¿Qué Variable Podemos Controlar Realmente Hoy?")
    st.markdown("La ecuación de continuidad del embalse está dominada por **Precipitación ($P$)**, **Caudales Base ($Q_b$)** y **Evaporación ($E$)**. Para evitar la crisis de diciembre 2026 y el 1T de 2027, la inversión debe concentrarse donde existe **gobernabilidad humana inmediata**:")

    col_p, col_q, col_e = st.columns(3)
    with col_p:
        st.error("🌧️ **1. Precipitación ($P$) — Control: NULO (~0%)**")
        st.markdown("""
        * **Naturaleza:** Gobernada por anomalías macroclimáticas del Pacífico (ENSO) y migración de la ZCIT.
        * **Capacidad de Maniobra:** Nula. No podemos fabricar lluvias en pleno fenómeno de El Niño.
        * **Rol en Oct–Nov 2026:** Capturar y almacenar cada gota de los últimos aguaceros de la temporada bimodal.
        """)
    with col_q:
        st.warning("🌲 **2. Caudales Base ($Q_b$) — Control: LARGO PLAZO (5-15 años)**")
        st.markdown("""
        * **Naturaleza:** Recarga subsuperficial lenta desde suelos y bosques altoandinos que sostiene quebradas en estiaje.
        * **Capacidad de Maniobra:** Media-Alta vía *Soluciones Basadas en la Naturaleza (SbN)* y restauración predial.
        * **Límite en la Emergencia:** Es nuestra póliza estructural a futuro, pero no aportará litros nuevos para enero de 2027.
        """)
    with col_e:
        st.success("☀️ **3. Evaporación ($E$) — Control: INMEDIATO (50% al 85%)**")
        st.markdown("""
        * **Naturaleza:** Escape físico de vapor concentrado en un polígono pequeño y accesible (~20 ha).
        * **Capacidad de Maniobra:** **Máxima y Directa (2 a 6 semanas).** Aislamiento físico agua-aire con módulos flotantes.
        * **Decisión Estratégica:** Conservar un $\text{m}^3$ ya captado es más rápido y seguro que esperar lluvias bajo El Niño.
        """)

# -----------------------------------------
# TAB 2: Mecanismos Físicos y Tecnologías
# -----------------------------------------
with tab_fisica:
    st.subheader("Termodinámica Atmosférica (Penman-Monteith) a 2,350 msnm")
    st.info("🌿 **Lámina Libre vs. Transpiración Vegetal:** Mientras los bosques circundantes de Santa Elena regulan su pérdida de agua cerrando activamente sus **estomas** durante el estrés hídrico de El Niño, el espejo de agua de Piedras Blancas carece de barreras biológicas y queda a merced de dos motores termodinámicos:")

    col_rad, col_vie = st.columns(2)
    with col_rad:
        st.markdown("""
        <div class="exec-card border-amber">
            <h4>☀️ 1. Motor Radiativo (Balance Energético — ~68% del Flujo)</h4>
            <p>• <b>Trampa de Bajo Albedo (α ≈ 0.08):</b> El agua libre refleja solo el 8% de la luz solar y absorbe el <b>92% de la energía radiante</b>, calentando la capa superficial y rompiendo puentes de hidrógeno.<br>
            • <b>Sinergia con Eutrofización (α → 0.12):</b> La penetración de luz solar activa floraciones de algas y reduce el oxígeno disuelto, exigiendo mayor gasto químico en la PTAP.</p>
            <div class="formula-box">E_rad = [ 0.408 · Δ · (Rns - Rnl) ] / [ Δ + γ ]</div>
        </div>
        """, unsafe_allow_html=True)
    with col_vie:
        st.markdown("""
        <div class="exec-card border-sky">
            <h4>💨 2. Motor Aerodinámico (Viento y VPD — ~32% del Flujo)</h4>
            <p>• <b>Barrido de la Capa Límite:</b> Gobernado por el <b>Déficit de Presión de Vapor (VPD = es - ea)</b> y el viento a 2 m (u2), que reemplaza continuamente la cúpula húmeda por aire seco.<br>
            • <b>Efecto Altitud (2,350 msnm):</b> La menor presión barométrica (Patm ≈ 76.5 kPa) disminuye la constante psicrométrica (γ), facilitando físicamente el escape del vapor.</p>
            <div class="formula-box">E_aero = [ γ · 2.626 · (1 + 0.536 · u2) · VPD ] / [ Δ + γ ]</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("Matriz Científica y Tecnológica de Control Evaporativo en Antioquia")
    df_tech = pd.DataFrame({
        "Tecnología": [
            "⭐ Piloto Híbrido (Solar FPV + HexaCovers)",
            "☀️ Paneles Solares Flotantes (Floatovoltaics - FPV)",
            "⬡ Módulos Hexagonales (HexaCovers)",
            "🌑 Esferas de Sombra (Barrier Balls)",
            "🧪 Cobertores Líquidos (Monocapas Químicas)",
            "🛡️ Mantas de Burbujas / Lamas Rígidas"
        ],
        "Mecanismo Físico / Científico": [
            "Doble barrera: Sello modular rápido + generación fotovoltaica refrigerada",
            "Bloqueo radiativo y eólico con islas fotovoltaicas sobre flotadores HDPE",
            "Discos modulares de polipropileno reciclado auto-ensamblables al vaciarse",
            "Esferas plásticas UV parcialmente lastradas que cubren el 91% aire-agua",
            "Alcoholes grasos biodegradables (película monomolecular invisible)",
            "Láminas continuas de polímero (sufren desgarro mecánico por viento >1 ha)"
        ],
        "Eficacia Local": ["70% - 80%", "60% - 70%", "80% - 90%", "80% - 85%", "15% - 30%", "N/A a gran escala"],
        "CAPEX / OPEX": [
            "CAPEX: ~$36/m² | OPEX: Muy Bajo",
            "CAPEX: $0.55-$0.80/W | OPEX: Bajo",
            "CAPEX: $15-$25/m² | OPEX: Casi Nulo",
            "CAPEX: $10-$15/m² | OPEX: Bajo",
            "CAPEX: Muy Bajo | OPEX: Alto (dosis c/48h)",
            "CAPEX: Prohibitivo / Reemplazo anual"
        ],
        "Retorno (ROI)": [
            "3.5 a 4.0 Años",
            "2.5 a 4.0 Años (Leyes 1715 y 2099)",
            "7 a 10 Años (Por agua salvada)",
            "5 a 8 Años",
            "No se amortiza (Gasto OPEX)",
            "Inviable (>10 ha)"
        ],
        "Viabilidad Piedras Blancas": [
            "⭐⭐⭐⭐⭐ Óptima (Rapidez + Flujo de Caja)",
            "⭐⭐⭐⭐⭐ Excelente (Sinergia Agua-Energía EPM)",
            "⭐⭐⭐⭐⭐ Excelente (Despliegue express en semanas)",
            "⭐⭐⭐ Media-Buena (Exige confinamiento con Booms)",
            "⭐⭐ Solo apoyo táctico de emergencia corta",
            "⭐ Descartada para el espejo principal"
        ]
    })
    st.dataframe(df_tech, use_container_width=True, hide_index=True)

# -----------------------------------------
# TAB 3: Simulador del Proyecto Piloto y Caso de Negocio
# -----------------------------------------
with tab_piloto:
    st.subheader("🎛️ Simulador Termodinámico, Energético y Financiero: Estiaje Dic 2026 – Mar 2027")
    
    col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
    with col_cfg1:
        area_pb_ha = st.slider("🌊 Espejo de Agua Piedras Blancas (ha)", 12.0, 26.0, 20.0, 1.0)
        pct_cobertura = st.slider("🛡️ Cobertura del Proyecto Piloto (%)", 15, 70, 40, 5)
    with col_cfg2:
        tech_piloto = st.selectbox("🔧 Configuración Tecnológica", [
            "⭐ Opción A: Piloto Híbrido (50% FPV Solar + 50% HexaCovers)",
            "☀️ Opción C: 100% Solares Flotantes (Floatovoltaics - FPV)",
            "⬡ Opción B: 100% Módulos Hexagonales (Despliegue Rápido)",
            "🌑 100% Esferas de Sombra Confinadas (Barrier Balls)"
        ])
        escenario_nino = st.selectbox("🔥 Intensidad El Niño (Dic 26 - Mar 27)", [
            "El Niño Moderado-Fuerte (+2°C, -12% HR, +3 MJ/m²)",
            "El Niño Severo + Vientos Alisios (+3°C, -18% HR, +4.5 MJ/m²)",
            "Condición Histórica Media (Altiplano Santa Elena)"
        ])
    with col_cfg3:
        consumo_l_hab = st.number_input("🚰 Dotación Mínima Vital / Neta (L/hab-día)", 50, 250, 100, 10)
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
        eff_local, mwp_ha, capex_ha, payback_est = 0.78, 0.25, 0.356, "3.8 Años"
    elif "Solares" in tech_piloto:
        eff_local, mwp_ha, capex_ha, payback_est = 0.68, 0.50, 0.562, "3.1 Años"
    elif "Hexagonales" in tech_piloto:
        eff_local, mwp_ha, capex_ha, payback_est = 0.85, 0.0, 0.190, "7.8 Años (Hídrico)"
    else:
        eff_local, mwp_ha, capex_ha, payback_est = 0.82, 0.0, 0.150, "6.5 Años (Hídrico)"

    area_intervenida_ha = area_pb_ha * (pct_cobertura / 100.0)
    factor_reduccion_total = (pct_cobertura / 100.0) * eff_local

    perdida_sin_piloto_m3_dia = evap_dia_mm * area_pb_ha * 10.0
    perdida_con_piloto_m3_dia = perdida_sin_piloto_m3_dia * (1.0 - factor_reduccion_total)
    agua_salvada_m3_dia = perdida_sin_piloto_m3_dia - perdida_con_piloto_m3_dia
    agua_salvada_periodo = agua_salvada_m3_dia * dias_crisis
    agua_salvada_anual = agua_salvada_m3_dia * 365.0 * 0.88

    personas_abastecidas = (agua_salvada_periodo * 1000.0) / (consumo_l_hab * dias_crisis)
    mwp_instalados = area_intervenida_ha * mwp_ha
    # Rendimiento solar con +10% de simbiosis térmica en lámina fría (1,350 kWh/kWp-año -> GWh/año)
    gwh_anual = mwp_instalados * 1.35
    capex_estimado = area_intervenida_ha * capex_ha

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("💧 Evap. Sin Piloto", f"{evap_dia_mm:.2f} mm/día", f"{perdida_sin_piloto_m3_dia:,.0f} m³/día", delta_color="inverse")
    m2.metric(f"🛡️ Agua Salvada ({dias_crisis}d)", f"{agua_salvada_periodo:,.0f} m³", f"~{agua_salvada_anual:,.0f} m³/año")
    m3.metric("🏊‍♂️ Escala Física", f"{agua_salvada_periodo/2500:.1f} Piscinas", "Olímpicas retenidas")
    m4.metric("👥 Abastecimiento", f"{personas_abastecidas:,.0f} Hab", f"A {consumo_l_hab} L/hab-d")
    m5.metric("⚡ Generación FPV", f"{mwp_instalados:.1f} MWp", f"{gwh_anual:.2f} GWh/año (+10% efic.)")
    m6.metric("💰 CAPEX Neto (Ley 1715)", f"${capex_estimado:.2f}M USD", f"Payback: {payback_est}")

    st.markdown("---")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        perdida_total_sin = perdida_sin_piloto_m3_dia * dias_crisis
        perdida_total_con = perdida_con_piloto_m3_dia * dias_crisis
        pct_embalse_salvado = (agua_salvada_periodo / 500000.0) * 100.0

        fig_bal = go.Figure(data=[
            go.Bar(name="Pérdida Evaporativa (m³)", x=["Sin Piloto (Actual)", "Con Piloto Activo"], y=[perdida_total_sin, perdida_total_con], marker_color=["#ef4444", "#f59e0b"], text=[f"{perdida_total_sin:,.0f} m³", f"{perdida_total_con:,.0f} m³"], textposition="auto"),
            go.Bar(name="Agua Potable Retenida (m³)", x=["Sin Piloto (Actual)", "Con Piloto Activo"], y=[0, agua_salvada_periodo], marker_color="#10b981", text=["0 m³", f"+{agua_salvada_periodo:,.0f} m³ ({pct_embalse_salvado:.1f}% del vaso)"], textposition="auto")
        ])
        fig_bal.update_layout(
            barmode="stack",
            title=f"Balance Evaporativo ({dias_crisis} días) — Protege el {pct_embalse_salvado:.1f}% del Embalse",
            yaxis_title="Volumen de Agua (m³)", height=340, margin=dict(t=45, b=20, l=20, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_bal, use_container_width=True)

    with col_g2:
        fig_pm = go.Figure(data=[
            go.Pie(
                labels=[f"Motor Radiativo (Rn = {rn_mj:.1f} MJ/m²·d)", f"Motor Aerodinámico (VPD = {vpd_kpa:.2f} kPa)"],
                values=[max(0.01, t_rad), max(0.01, t_aero)],
                hole=0.48, marker_colors=["#f97316", "#0ea5e9"], textinfo="label+percent"
            )
        ])
        fig_pm.update_layout(
            title=f"Partición Termodinámica Penman-Monteith ({evap_dia_mm:.2f} mm/día a {patm:.1f} kPa)",
            height=340, margin=dict(t=45, b=20, l=20, r=20), showlegend=False
        )
        st.plotly_chart(fig_pm, use_container_width=True)

    st.subheader("Comparativa Ejecutiva de las 3 Opciones de Configuración (Base 8.0 ha = 40% del Espejo)")
    op1, op2, op3 = st.columns(3)
    with op1:
        st.markdown("""
        <div class="exec-card border-emerald">
            <h4>⭐ Opción A: Piloto Híbrido (Recomendado)</h4>
            <p><b>4 ha en HexaCovers</b> (despliegue inmediato en noviembre) + <b>4 ha en Solar Flotante FPV (2.0 MWp / 2.7 GWh-año)</b>.<br>
            • <b>CAPEX Neto (Ley 1715):</b> ~$2.85M USD<br>
            • <b>Payback:</b> 3.8 años (+20 años de flujo libre y autoconsumo en bombeo/PTAP EPM).</p>
        </div>
        """, unsafe_allow_html=True)
    with op2:
        st.markdown("""
        <div class="exec-card border-sky">
            <h4>⬡ Opción B: 100% Barrera Modular (8 ha Hexa/Balls)</h4>
            <p>Enfoque <b>100% rapidez hídrica</b> sin interconexión eléctrica. Reducción del 85% de evaporación en el área cubierta.<br>
            • <b>CAPEX Estimado:</b> ~$1.2M – $1.6M USD<br>
            • <b>Ventaja:</b> Cero trámites de conexión eléctrica; vaciado directo desde camión en noviembre.</p>
        </div>
        """, unsafe_allow_html=True)
    with op3:
        st.markdown("""
        <div class="exec-card border-amber">
            <h4>☀️ Opción C: 100% Solar Flotante FPV (4.0 MWp)</h4>
            <p>Máxima rentabilidad energética (~5.4 GWh/año), desplazando tarifa de $750–$900 COP/kWh (~$1.2M USD/año de ahorro).<br>
            • <b>CAPEX Neto (Ley 1715):</b> ~$4.5M USD<br>
            • <b>Payback:</b> 3.1 años (Exclusión de IVA 19%, aranceles y deducción 50% Renta).</p>
        </div>
        """, unsafe_allow_html=True)

# -----------------------------------------
# TAB 4: Co-Beneficios Multidimensionales (De Diapositiva 7)
# -----------------------------------------
with tab_cobeneficios:
    st.subheader("💎 Creación de Valor Público y Ambiental: Co-Beneficios del Piloto en Piedras Blancas")
    cb1, cb2 = st.columns(2)
    with cb1:
        st.markdown("""
        <div class="exec-card border-sky">
            <h4>🧪 1. Mejora de Calidad del Agua y Control de Algas en PTAP</h4>
            <p>Al sombrear el 40% de la superficie y reducir la temperatura superficial del agua en <b>~2.5°C</b>, se inhibe la fotosíntesis de cianobacterias. Esto frena episodios de eutrofización en verano, protege la fauna bentónica y <b>reduce entre un 20% y 30% el consumo de coagulantes y alguicidas en la PTAP</b>.</p>
        </div>
        <div class="exec-card border-amber">
            <h4>🌲 3. Cero Conflicto de Uso del Suelo en el Parque Arví</h4>
            <p>Instalar 2 a 4 MWp solares en tierra firme en Santa Elena exigiría adquirir predios de altísimo costo o talar hectáreas de reserva forestal protectora. Usar la lámina de un embalse artificial existente genera <b>impacto cero sobre el bosque nativo altoandino</b>.</p>
        </div>
        """, unsafe_allow_html=True)
    with cb2:
        st.markdown("""
        <div class="exec-card border-emerald">
            <h4>⚡ 2. Simbiosis Termo-Eléctrica (+8% a +12% Rendimiento Solar)</h4>
            <p>Los paneles solares en tierra pierden eficiencia cuando se sobrecalientan al mediodía. Sobre el espejo de agua frío de Piedras Blancas (2,350 msnm), el enfriamiento convectivo incrementa la producción eléctrica entre un <b>8% y 12% adicional</b> frente a instalaciones en techo o suelo.</p>
        </div>
        <div class="exec-card border-purple">
            <h4>🧭 4. Escalabilidad Regional hacia La Fe (145 ha) y Río Grande II (1,100 ha)</h4>
            <p>Por su escala manejable (~20 ha), aguas tranquilas y cercanía a Medellín, Piedras Blancas es el <b>laboratorio vivo ideal</b> para calibrar anclajes, boyas VPD y protocolos ambientales antes de escalar a <b>La Fe</b> y <b>Río Grande II</b>.</p>
        </div>
        """, unsafe_allow_html=True)

    st.success("🏛️ **Alineación Institucional:** Cumple las metas del **Pacto por la Seguridad Hídrica Territorial**, el Plan de Acción Climática de Medellín y los ODS 6 (Agua Limpia) y 7 (Energía Asequible y No Contaminante).")

# -----------------------------------------
# TAB 5: Hoja de Ruta y Presentación Ejecutiva 16:9
# -----------------------------------------
with tab_ruta:
    st.subheader("🚀 Ruta Crítica de Acción: Octubre 2026 – Primer Trimestre 2027")
    st.error("⚠️ **¿Por qué decidir HOY en Octubre de 2026?:** No se puede tapar un embalse cuando ya se secó en febrero. Debemos aprovechar los días lluviosos de **octubre y noviembre** para llenar el vaso de Piedras Blancas al 100% (~0.50 Mm³) e instalar simultáneamente la cobertura flotante para que actúe como una 'tapa hermética' desde el 1 de diciembre.")

    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.markdown("""
        <div class="exec-card border-sky">
            <h4>PASO 1 • OCTUBRE 2026</h4>
            <p><b>Aprobación Express y Cosecha</b><br>
            • Aprobación ejecutiva del Piloto (8 ha).<br>
            • Regla operativa de retención máxima.<br>
            • Orden de compra directa de módulos rápidos (Fase 1A) y pliegos FPV (Fase 1B).<br>
            <b style="color:#38bdf8;">Hito: Orden lista antes del 31 Oct.</b></p>
        </div>
        """, unsafe_allow_html=True)
    with r2:
        st.markdown("""
        <div class="exec-card border-emerald">
            <h4>PASO 2 • NOVIEMBRE 2026</h4>
            <p><b>Sellado Temprano del Vaso</b><br>
            • Captura de lluvias hasta cota máxima.<br>
            • Instalación de barreras flotantes (booms) y vaciado de módulos sin obra civil.<br>
            • Encendido de boya VPD y radiación.<br>
            <b style="color:#10b981;">Hito: 4 ha selladas al 30 Nov.</b></p>
        </div>
        """, unsafe_allow_html=True)
    with r3:
        st.markdown("""
        <div class="exec-card border-amber">
            <h4>PASO 3 • DICIEMBRE 2026</h4>
            <p><b>Defensa Activa en Verano</b><br>
            • Entrada de vientos alisios con el escudo físico ya operando.<br>
            • Ahorro inmediato de ~260 m³/día.<br>
            • Montaje de islas Solares Flotantes.<br>
            <b style="color:#f59e0b;">Hito: Mitigación pico fin de año.</b></p>
        </div>
        """, unsafe_allow_html=True)
    with r4:
        st.markdown("""
        <div class="exec-card border-purple">
            <h4>PASO 4 • ENE - MAR 2027</h4>
            <p><b>Superación El Niño y Escalado</b><br>
            • Preservación acumulada >31,000 m³.<br>
            • Agua cruda fría y sin floración algal.<br>
            • Expediente técnico validado para escalar al Embalse La Fe.<br>
            <b style="color:#a855f7;">Hito: Modelo listo para réplica.</b></p>
        </div>
        """, unsafe_allow_html=True)

    st.info("✅ **Decisión Solicitada Hoy:** Autorizar la estructuración técnica y presupuestal del Piloto Piedras Blancas (Fase 1 - Octubre 2026).")