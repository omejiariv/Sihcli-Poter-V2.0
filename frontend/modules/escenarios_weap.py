import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import text
import ast
import geopandas as gpd

from modules.db_manager import get_engine
from modules.etp_extractor import extraer_etp_mensual
from modules.hydrological_balance import calcular_balance_mensual
from modules.land_cover import calcular_estadisticas_zona, get_infiltration_suggestion

def renderizar_motor_escenarios_weap(territorio, gdf_zona, pob_base_sugerida, anio_simulacion, rurh_base_m3s, oferta_media_sugerida):
    engine = get_engine()
    nombre_puro = territorio.split(" - (")[0].strip() if " - (" in territorio else territorio.strip()
    st.markdown(f"## ⚖️ Simulador Hidrosocial WEAP: **{nombre_puro}**")

    # =====================================================================
    # 🌍 FASE 1: SÍNTESIS PARAMÉTRICA (INVOCANDO PRECALCULADOS Y POLINOMIO)
    # =====================================================================
    area_km2, alt_min, alt_max, alt_promedio = 100.0, 0, 4000, 2000
    factor_infiltracion = 0.25
    precip_base = [120.0, 140.0, 180.0, 250.0, 300.0, 200.0, 180.0, 200.0, 260.0, 310.0, 240.0, 150.0] 
    fuente_clima = "Patrón Bimodal Andino (Sintético)"
    
    c3, c2, c1, c0 = 0.0, 0.0, 0.0, 0.0
    tiene_polinomio = False

    with st.spinner("🌍 Conectando con el Gemelo Digital (Matriz Maestra)..."):
        try:
            with engine.connect() as conn:
                q_poly = text('SELECT * FROM matriz_maestra_hipsometrica WHERE "Territorio" ILIKE :t LIMIT 1')
                df_poly = pd.read_sql(q_poly, conn, params={"t": f"%{nombre_puro}%"})
                if not df_poly.empty:
                    c3 = float(df_poly.iloc[0].get('Coef_C3', 0.0))
                    c2 = float(df_poly.iloc[0].get('Coef_C2', 0.0))
                    c1 = float(df_poly.iloc[0].get('Coef_C1', 0.0))
                    c0 = float(df_poly.iloc[0].get('Coef_C0', 0.0))
                    alt_min = int(df_poly.iloc[0].get('H_Minima', 0))
                    alt_max = int(df_poly.iloc[0].get('H_Maxima', 4000))
                    tiene_polinomio = True

                q_morph = text('SELECT * FROM matriz_hidrogeomorfologica_maestra WHERE "Territorio" ILIKE :t LIMIT 1')
                df_m = pd.read_sql(q_morph, conn, params={"t": f"%{nombre_puro}%"})
                if not df_m.empty:
                    col_area = next((c for c in df_m.columns if 'area' in c.lower()), None)
                    col_prom = next((c for c in df_m.columns if 'media' in c.lower() or 'prom' in c.lower()), None)
                    col_min = next((c for c in df_m.columns if 'min' in c.lower()), None)
                    col_max = next((c for c in df_m.columns if 'max' in c.lower()), None)
                    
                    # 🛡️ FIX: pd.notna() evita el crash si la BD entrega valores nulos (NaN)
                    if col_area and pd.notna(df_m.iloc[0][col_area]): area_km2 = float(df_m.iloc[0][col_area])
                    if col_prom and pd.notna(df_m.iloc[0][col_prom]): alt_promedio = int(df_m.iloc[0][col_prom])
                    if col_min and pd.notna(df_m.iloc[0][col_min]): alt_min = int(df_m.iloc[0][col_min])
                    if col_max and pd.notna(df_m.iloc[0][col_max]): alt_max = int(df_m.iloc[0][col_max])
                
                q_h = text('SELECT "Caudal_Medio_m3s" FROM matriz_hidrologica_maestra WHERE "Territorio" ILIKE :t LIMIT 1')
                val_q = conn.execute(q_h, {"t": f"%{nombre_puro}%"}).scalar()
                if val_q: oferta_media_sugerida = float(val_q)

        except Exception: pass

        if gdf_zona is not None and not gdf_zona.empty:
            # 1. 🛡️ Rescate Geométrico Blindado (CRS Seguro)
            try:
                if gdf_zona.crs is None: gdf_zona = gdf_zona.set_crs(epsg=4326)
                gdf_3116 = gdf_zona.to_crs(epsg=3116)
                area_real_km2 = gdf_3116.geometry.area.sum() / 1e6
                if area_km2 == 100.0: area_km2 = area_real_km2
                
                # 2. 🛡️ Rescate Topográfico Seguro (Copiado de Hidrología)
                ruta_dem = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/rasters/DemAntioquia_EPSG3116.tif"
                if area_real_km2 < 5000:
                    # 🐛 EL BUG ESTABA AQUÍ: Usamos gdf_zona en lugar de gdf_3116
                    morph = calculate_morphometry(gdf_zona, dem_path=ruta_dem) 
                    if morph and morph.get("alt_max_m", 0) > 0:
                        alt_min = int(morph.get("alt_min_m", 0))
                        alt_max = int(morph.get("alt_max_m", 4000))
                        alt_promedio = int(morph.get("alt_prom_m", 2000))
            except Exception as e:
                st.toast(f"⚠️ Aviso Morfometría: {e}") # Flare Gun: te avisará visualmente si algo falla
                pass

            # 3. 🛡️ Clima y Suelo Aislado
            try:
                ruta_cob = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/rasters/Cob2026_Actualizada.tif"
                stats_cob = calcular_estadisticas_zona(gdf_zona, ruta_cob)
                factor_infiltracion, _ = get_infiltration_suggestion(stats_cob)
                
                df_est = pd.read_sql("SELECT id_estacion, nombre, latitud, longitud FROM estaciones", engine).dropna()
                gdf_est = gpd.GeoDataFrame(df_est, geometry=gpd.points_from_xy(df_est.longitud, df_est.latitud), crs="EPSG:4326")
                cruce = gpd.sjoin_nearest(gdf_zona.to_crs(4326), gdf_est, how="left", distance_col="dist")
                if not cruce.empty:
                    id_est = str(cruce.iloc[0]['id_estacion'])
                    df_p = pd.read_sql(text("SELECT fecha, valor FROM precipitacion WHERE id_estacion = :id"), engine, params={"id": id_est})
                    if not df_p.empty:
                        df_p['mes'] = pd.to_datetime(df_p['fecha']).dt.month
                        prom_mensual = df_p.groupby('mes')['valor'].mean().reindex(range(1,13))
                        if prom_mensual.mean() > 0:
                            precip_base = prom_mensual.fillna(prom_mensual.mean()).tolist()
                            fuente_clima = f"Estación {cruce.iloc[0]['nombre']}"
            except Exception: pass
            
        # 🚀 CÁLCULO ETP DINÁMICO (Adiós a los valores quemados)
        try:
            etp_real = extraer_etp_mensual(gdf_zona)
            if np.std(etp_real) < 1.0:
                # Modelo de Temperatura vs Altura si la extracción satelital falla
                temp_media = 28.0 - (alt_promedio / 1000.0 * 6.5)
                etp_base = (temp_media * 4.5) + 20.0
                variacion_mensual = np.array([0.95, 1.0, 1.05, 0.90, 0.85, 0.80, 0.95, 1.0, 1.10, 0.90, 0.85, 0.80])
                etp_real = (etp_base * variacion_mensual).tolist()
        except:
            temp_media = 28.0 - (alt_promedio / 1000.0 * 6.5)
            etp_base = (temp_media * 4.5) + 20.0
            etp_real = (etp_base * np.array([0.95, 1.0, 1.05, 0.90, 0.85, 0.80, 0.95, 1.0, 1.10, 0.90, 0.85, 0.80])).tolist()

    if alt_max <= alt_min: alt_max = alt_min + 100
    # 🛡️ FIX: Paso dinámico (previene que Streamlit colapse en cuencas planas como Canime)
    paso_slider = max(1, int((alt_max - alt_min) / 20))

    # =====================================================================
    # 🎛️ FASE 2: PANEL DE CONTROL MULTIDIMENSIONAL
    # =====================================================================
    st.markdown("---")

    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown("#### ⛰️ Física y Oferta")
        # Slider blindado con su 'step' seguro
        cota_gestion = st.slider("Bocatoma (Cota msnm):", min_value=int(alt_min), max_value=int(alt_max), value=int(alt_min), step=paso_slider, help="Ajusta la altitud de captación. El motor calculará el área aportante aguas arriba.")
        var_clima = st.slider("Variación Climática %", -50, 50, 0, 5, help="Simula El Niño (negativo) o La Niña (positivo).")
        var_calidad = st.slider("Castigo Calidad %", 0, 80, 0, 5, help="Fracción del río contaminada y no apta para uso humano.")
        
    with c2:
        st.markdown("#### 👥 Presiones Humanas")
        pob_base = st.number_input("Población Base (hab):", min_value=0.0, value=float(pob_base_sugerida), step=1000.0)
        dotacion = st.number_input("Dotación (L/hab/día):", min_value=50, max_value=400, value=150)
        var_pob = st.slider("Crecimiento Flotante %", 0, 100, 0, 5)

    with c3:
        st.markdown("#### 🏭 RURH y Retornos")
        tope_rurh = max(oferta_media_sugerida * 2, rurh_base_m3s * 1.5, 0.1)
        var_rurh = st.slider("Concesiones RURH (m³/s)", 0.0, float(tope_rurh), float(rurh_base_m3s), 0.01)
        var_retorno = st.slider("Retorno de Aguas %", 0, 100, 80, 5, help="Agua que vuelve al cauce (vertimientos). Reduce el impacto neto de la extracción.")
        var_reuso = st.slider("Reuso Industrial %", 0, 100, 0, 5)

    with c4:
        st.markdown("#### 🛡️ Regulación y Mitigación")
        caudal_eco_pct = st.slider("Q. Ecológico Exigido %", 10, 50, 25, 5, help="Porcentaje legal para mantener la vida acuática.")
        var_eficiencia = st.slider("Eficiencia Acueducto %", 0, 50, 0, 5, help="Reducción de pérdidas técnicas en la red de tuberías.")
        capacidad_tanque_hm3 = st.number_input("Embalse / Tanque (Hm³):", 0.0, 100.0, 0.0, 0.1)

    # =====================================================================
    # 🧮 FASE 3: MOTOR DE BALANCE HÍDRICO (CIRUGÍA DE HIPSOMETRÍA VIVA)
    # =====================================================================
    area_porcentaje = 100.0
    
    if cota_gestion > alt_min:
        if tiene_polinomio:
            # Matemática viva desde la Matriz Hipsométrica
            a_relativa = (c3 * (cota_gestion**3)) + (c2 * (cota_gestion**2)) + (c1 * cota_gestion) + c0
            area_porcentaje = max(0.0, min(100.0, a_relativa))
        else:
            # Fallback geométrico lineal
            if alt_max > alt_min:
                area_porcentaje = max(0.0, 100.0 * (1.0 - ((cota_gestion - alt_min) / (alt_max - alt_min))))
            else:
                area_porcentaje = 100.0
                
    area_cota_km2 = area_km2 * (area_porcentaje / 100.0)

    factor_ppt = 1.0 + (var_clima / 100.0)
    factor_etp = 1.0 - (var_clima / 200.0) 
    
    precip_escenario = [p * factor_ppt for p in precip_base]
    etp_escenario = [e * factor_etp for e in etp_real]

    balance = calcular_balance_mensual(precip_escenario, etp_escenario, area_cota_km2, factor_recarga_base=factor_infiltracion)
    
    q_ideam_cota = oferta_media_sugerida * (area_porcentaje / 100.0)
    q_ideam_clima = q_ideam_cota * factor_ppt
    
    shape_mensual = np.array(balance["caudal_m3s"])
    # Evita que el déficit desaparezca si la escorrentía llega a 0 absoluto
    shape_norm = shape_mensual / shape_mensual.mean() if shape_mensual.mean() > 0 else np.zeros(12)

    caudal_bruto_mensual = (q_ideam_clima * shape_norm) * (1 - (var_calidad / 100.0))
    recarga_mensual_mm = np.array(balance["recarga"])
    recarga_anual_m3s = (np.sum(recarga_mensual_mm) / 1000.0) * (area_cota_km2 * 1e6) / (86400 * 365)

    # =====================================================================
    # ⚖️ FASE 4: MATEMÁTICA SOCIAL WEAP Y EMBALSES
    # =====================================================================
    q_ecologico = caudal_bruto_mensual * (caudal_eco_pct / 100.0)
    oferta_neta_mensual = np.maximum(0, caudal_bruto_mensual - q_ecologico)

    demanda_humana_bruta = ((pob_base * (1 + var_pob/100.0)) * dotacion) / (1000 * 86400)
    demanda_humana_neta = demanda_humana_bruta * (1 - (var_eficiencia / 100.0))
    retorno_humano = demanda_humana_neta * (var_retorno / 100.0)

    demanda_rurh_neta = var_rurh * (1 - (var_reuso / 100.0))
    retorno_rurh = demanda_rurh_neta * (var_retorno / 100.0) 

    demanda_extractiva_total = demanda_humana_neta + demanda_rurh_neta
    retorno_total = retorno_humano + retorno_rurh
    consumo_consuntivo_total = demanda_extractiva_total - retorno_total

    volumen_embalse_actual_hm3 = capacidad_tanque_hm3 * 0.5 
    deficit_array = np.zeros(12)
    volumen_historico = np.zeros(12)

    for i in range(12):
        balance_mes = oferta_neta_mensual[i] - consumo_consuntivo_total
        balance_hm3 = balance_mes * 3600 * 24 * 30 / 1e6
        volumen_embalse_actual_hm3 += balance_hm3
        
        if volumen_embalse_actual_hm3 > capacidad_tanque_hm3:
            volumen_embalse_actual_hm3 = capacidad_tanque_hm3 
        elif volumen_embalse_actual_hm3 < 0:
            deficit_hm3 = abs(volumen_embalse_actual_hm3)
            deficit_array[i] = deficit_hm3 * 1e6 / (3600 * 24 * 30) 
            volumen_embalse_actual_hm3 = 0.0
            
        volumen_historico[i] = volumen_embalse_actual_hm3

    # =====================================================================
    # 📈 FASE 5: RENDERIZADO VISUAL INTEGRADO (HOVERS INTELIGENTES)
    # =====================================================================
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    st.markdown("---")
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Eje Secundario (Clima y Suelo en mm)
    fig.add_trace(go.Bar(x=meses, y=precip_escenario, name="Precipitación (mm)", marker_color='rgba(52, 152, 219, 0.3)'), secondary_y=True)
    fig.add_trace(go.Bar(x=meses, y=recarga_mensual_mm, name="Recarga Acuíferos (mm)", marker_color='rgba(46, 204, 113, 0.4)'), secondary_y=True)
    fig.add_trace(go.Scatter(x=meses, y=balance["etr"], name="ETR Real (mm)", mode='lines+markers', line=dict(color='#27ae60', width=1, dash='dot')), secondary_y=True)
    fig.add_trace(go.Scatter(x=meses, y=etp_escenario, name="ETP Potencial (mm)", mode='lines', line=dict(color='#e74c3c', width=1, dash='dot')), secondary_y=True)
    
    # Eje Principal (Caudales en m3/s)
    y_demanda_visual = np.full(12, demanda_extractiva_total)
    y_consumo_real = np.full(12, consumo_consuntivo_total)
    caudal_maximo = caudal_bruto_mensual * 1.30
    caudal_minimo = caudal_bruto_mensual * 0.70

    fig.add_trace(go.Scatter(x=meses, y=caudal_maximo, name="Max", mode='lines', line=dict(width=0), showlegend=False), secondary_y=False)
    fig.add_trace(go.Scatter(x=meses, y=caudal_minimo, name="Rango Histórico de Oferta", mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(41, 128, 185, 0.1)'), secondary_y=False)

    # 💡 FIX GLOSARIO: Integrado en los tooltips al pasar el mouse
    fig.add_trace(go.Scatter(x=meses, y=caudal_bruto_mensual, name='Oferta Bruta',
        hovertemplate="<b>Oferta Bruta</b><br>Caudal natural del río provisto por la lluvia.<br>%{y:.3f} m³/s<extra></extra>",
        line=dict(color='#95a5a6', width=2, dash='dot')), secondary_y=False)
        
    fig.add_trace(go.Scatter(x=meses, y=oferta_neta_mensual, name='Oferta Neta',
        hovertemplate="<b>Oferta Neta</b><br>Agua disponible descontando el caudal ecológico exigido.<br>%{y:.3f} m³/s<extra></extra>",
        line=dict(color='#2980b9', width=4)), secondary_y=False)
        
    fig.add_trace(go.Scatter(x=meses, y=y_demanda_visual, name='Extracción Total',
        hovertemplate="<b>Extracción Total</b><br>Agua total que entra a los tubos del acueducto e industria.<br>%{y:.3f} m³/s<extra></extra>",
        line=dict(color='#e74c3c', width=2)), secondary_y=False)
        
    fig.add_trace(go.Scatter(x=meses, y=y_consumo_real, name='Consumo Consuntivo',
        hovertemplate="<b>Consumo Consuntivo</b><br>Agua que desaparece de la cuenca (no retorna como vertimiento).<br>%{y:.3f} m³/s<extra></extra>",
        line=dict(color='black', width=2, dash='dash')), secondary_y=False)
    
    if capacidad_tanque_hm3 > 0:
        fig.add_trace(go.Bar(x=meses, y=volumen_historico, name='Volumen Embalse (Hm³)', marker_color='rgba(241, 196, 15, 0.6)'), secondary_y=False)

    if np.sum(deficit_array) > 0:
        fig.add_trace(go.Scatter(x=meses, y=oferta_neta_mensual, showlegend=False, hoverinfo='skip', line=dict(width=0)), secondary_y=False)
        fig.add_trace(go.Scatter(x=meses, y=np.maximum(oferta_neta_mensual, y_consumo_real), name='⚠️ DÉFICIT CRÍTICO', fill='tonexty', fillcolor='rgba(0, 0, 0, 0.6)', line=dict(width=0)), secondary_y=False)

    max_caudal = max(np.max(caudal_maximo), np.max(y_demanda_visual)) * 1.1
    if max_caudal == 0: max_caudal = 1.0 
    fig.update_yaxes(range=[0, max_caudal], secondary_y=False)
    
    fig.update_layout(title="Dinámica Hidrosocial Completa (Clima, Oferta y Demanda)", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5), height=600)
    fig.update_yaxes(title_text="Caudal Extraíble (m³/s)", secondary_y=False)
    fig.update_yaxes(title_text="Lámina Climática (mm)", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True)

    # =====================================================================
    # 🩺 FASE 6 Y 7: DIAGNÓSTICO CLÍNICO, ORÁCULO Y MATRIZ TOTAL
    # =====================================================================
    st.markdown("---")
    
    df_weap = pd.DataFrame({
        "Mes": meses,
        "Area_Aportante_km2": np.round(np.full(12, area_cota_km2), 2),
        "Precipitacion_mm": np.round(precip_escenario, 1),
        "ETP_Potencial_mm": np.round(etp_escenario, 1),
        "ETR_Real_mm": np.round(balance["etr"], 1),
        "Recarga_Acuifero_mm": np.round(recarga_mensual_mm, 1),
        "Oferta_Bruta_m3s": np.round(caudal_bruto_mensual, 3),
        "Caudal_Ecologico_m3s": np.round(q_ecologico, 3),
        "Oferta_Neta_Libre_m3s": np.round(oferta_neta_mensual, 3),
        "Extraccion_Total_m3s": np.round(y_demanda_visual, 3),
        "Consumo_Consuntivo_m3s": np.round(np.full(12, consumo_consuntivo_total), 3),
        "Vol_Embalse_Hm3": np.round(volumen_historico, 2),
        "Deficit_m3s": np.round(deficit_array, 3)
    })

    colA, colB = st.columns([1, 1])

    with colA:
        st.subheader("🩺 Diagnóstico Clínico Integral")
        meses_criticos = df_weap[df_weap['Deficit_m3s'] > 0]
        oferta_neta_media = oferta_neta_mensual.mean()
        
        with st.expander("🔬 Síntesis Física Activa", expanded=True):
            fuente_pol = "Polinomio A(h) BD" if tiene_polinomio else "Lineal Geométrica"
            st.markdown(f"- **Área Aportante Real:** {area_cota_km2:,.1f} km² ({area_porcentaje:.1f}% calculada vía {fuente_pol}).")
            st.markdown(f"- **Clima Base:** {fuente_clima}")
            st.markdown(f"- **Oferta Bruta Promedio:** {caudal_bruto_mensual.mean():.3f} m³/s")
            st.markdown(f"- **Caudal Ecológico Retenido:** {q_ecologico.mean():.3f} m³/s")
            st.markdown(f"- **Dinámica Subterránea (Infiltración/Recarga):** {sum(balance['recarga']):.1f} mm/año (Aprox. **{recarga_anual_m3s:.3f} m³/s** constantes al acuífero).")
        
        if meses_criticos.empty:
            st.success(f"✅ **Sistema en Equilibrio:** La Oferta Neta y reservas soportan el consumo actual.")
            if demanda_extractiva_total < 0.05:
                st.warning(f"⚠️ **Nota Analítica:** La extracción en este momento es microscópica frente al tamaño del río. Para estresar el sistema y evaluar crisis, eleva las concesiones RURH.")
        else:
            st.error(f"⚠️ **Colapso Hídrico Detectado:** Déficit durante **{len(meses_criticos)} meses**.")
            peor = meses_criticos.loc[meses_criticos['Deficit_m3s'].idxmax()]
            st.markdown(f"**Pico de Crisis:** **{peor['Mes']}**, con un faltante de **{peor['Deficit_m3s']} m³/s**.")
            
            st.markdown("### 💡 Prescripción de Mitigación:")
            if consumo_consuntivo_total > oferta_neta_mensual.mean() and capacidad_tanque_hm3 == 0:
                st.write("- 🏗️ **Falta Regulación:** Necesitas aumentar la `Capacidad del Embalse` para guardar agua del invierno.")
            if var_eficiencia < 20:
                st.write("- 🚰 **Ineficiencia Urbana:** Aumenta la `Eficiencia Acueducto` para reducir pérdidas en tuberías.")
            if area_porcentaje < 50:
                st.write("- ⛰️ **Bocatoma Restrictiva:** Tu `Cota de Gestión` descarta mucha cuenca. Considera captar aguas abajo.")

        st.markdown("### 🔮 Oráculo Prospectivo (Proyección de Crisis)")
        litros_disponibles_dia = (oferta_neta_media - demanda_rurh_neta) * 86400 * 1000
        poblacion_maxima = litros_disponibles_dia / dotacion if dotacion > 0 else 0
        
        oferta_nino = oferta_neta_media * 0.70 
        litros_nino_dia = (oferta_nino - demanda_rurh_neta) * 86400 * 1000
        poblacion_maxima_nino = litros_nino_dia / dotacion if dotacion > 0 else 0

        anio_crisis_normal = "Estable hasta 2050+"
        anio_crisis_nino = "Estable hasta 2050+"
        
        try:
            df_evo = pd.read_sql(text('SELECT "año", "Pob_Base" FROM matriz_maestra_demografica WHERE "LLAVE_UNIVERSAL" ILIKE :t'), engine, params={"t": f"%{nombre_puro}%"})
            if not df_evo.empty:
                df_crisis_n = df_evo[(df_evo['año'] >= anio_simulacion) & (df_evo['Pob_Base'] > poblacion_maxima)]
                if not df_crisis_n.empty: anio_crisis_normal = str(df_crisis_n.iloc[0]['año'])
                
                df_crisis_nino = df_evo[(df_evo['año'] >= anio_simulacion) & (df_evo['Pob_Base'] > poblacion_maxima_nino)]
                if not df_crisis_nino.empty: anio_crisis_nino = str(df_crisis_nino.iloc[0]['año'])
        except: pass

        st.markdown(f"- 👥 **Población Límite de la Cuenca (Sostenible):** {poblacion_maxima:,.0f} habs.")
        st.markdown(f"- 📅 **Año de colapso demográfico natural:** {anio_crisis_normal}.")
        st.markdown(f"- 🔥 **Año de colapso bajo Fenómeno El Niño (-30% Oferta):** {anio_crisis_nino}.")
        
        st.info("🌦️ **Variabilidad Climática y Ordenamiento Territorial:**  \nSe debe incluir la variabilidad climática para los procesos de ordenamiento y planificación territorial. **Durante El Niño** se deben desarrollar obras de infraestructura y extracción profunda, y **durante La Niña** se debe aprovechar el potencial para almacenar agua en embalses y acuíferos, y generar energía. Se sugiere implementar sistemas de **Cosecha de Agua Lluvia** residenciales y diseñar baterías de **Pozos Subterráneos** para extraer reservas del acuífero durante las sequías.")
        st.info("💡 **Glosario Hidrosocial:**  \n* **Oferta Bruta:** Caudal natural del río provisto por la lluvia. \n* **Oferta Neta:** Agua disponible en el río *descontando* el caudal ecológico exigido y la contaminación. \n* **Extracción:** Agua total que entra a los tubos del acueducto y la industria. \n* **Consumo Consuntivo:** Agua que se evapora o se incorpora a productos y *desaparece* de la cuenca (no retorna al cauce).")

    with colB:
        st.subheader("📋 Matriz de Balances Total")
        st.dataframe(df_weap.style.format(precision=2), use_container_width=True)
        csv = df_weap.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Matriz Expandida (CSV)", data=csv, file_name=f"Simulador_WEAP_{nombre_puro}.csv", mime="text/csv", use_container_width=True)