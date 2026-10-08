import streamlit as st
import pyeto
import plotly.graph_objects as go
import pandas as pd
import os
import sys

# -----------------------------------------
# Configuración e Integración al Aleph
# -----------------------------------------
st.set_page_config(page_title="Evaporación de Embalses", page_icon="💧", layout="wide")

try:
    from modules import selectors
    from modules.utils import encender_gemelo_digital
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules import selectors
    from modules.utils import encender_gemelo_digital

selectors.renderizar_menu_navegacion("Evaporación")
encender_gemelo_digital()

# -----------------------------------------
# Motor de Datos: Carga desde Supabase
# -----------------------------------------
@st.cache_data
def cargar_datos_embalses():
    import requests
    import io
    try:
        url = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/Area%20Volumen%20embalses%20Antioquia.xlsx"
        # Descargamos el archivo en memoria de forma segura
        response = requests.get(url, verify=False)
        df = pd.read_excel(io.BytesIO(response.content))
        
        # Corrección automática de formatos decimales importados desde Excel
        if 'Altura Promedio Cota Máx (msnm)' in df.columns:
            df['Altura Promedio Cota Máx (msnm)'] = df['Altura Promedio Cota Máx (msnm)'].apply(
                lambda x: x * 1000 if pd.notnull(x) and x < 10 else x
            )
        return df
    except Exception as e:
        st.error(f"Error cargando Excel de Embalses desde Supabase: {e}")
        return pd.DataFrame()

df_embalses = cargar_datos_embalses()

# Mapeo de Latitudes y Longitudes (Para el mapa interactivo y cálculos)
coords_embalses = {
    "Guatapé (El Peñol)": (6.26, -75.16), "Hidroituango": (7.13, -75.67), 
    "Jaguas": (6.31, -75.02), "La Fe": (6.11, -75.50), 
    "Piedras Blancas": (6.29, -75.49), "Playas": (6.27, -74.95),
    "Porce II": (6.75, -75.15), "Porce III": (6.80, -75.10), 
    "Riogrande II": (6.55, -75.45), "San Carlos": (6.21, -74.85)
}

# -----------------------------------------
# Interfaz Principal
# -----------------------------------------
st.title("💧 Dinámicas de Evaporación en Cuerpos de Agua Libre")
st.markdown("Plataforma interactiva para el análisis hidrológico, evaluación de impactos climáticos, restricciones operativas y simulación termodinámica en la red de embalses de Antioquia.")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📚 Marco Operativo y Climático", 
    "🛡️ Tecnologías de Mitigación", 
    "📊 Base de Datos Maestra",
    "🧮 Simulador Interactivo",
    "📡 Telemetría XM",
    "🗺️ Explorador Satelital"
])

# -----------------------------------------
# PESTAÑA 1: Marco Conceptual y Operativo
# -----------------------------------------
with tab1:
    st.header("El Ciclo Invisible: Termodinámica y Operación de Embalses")
    st.markdown("La gestión de embalses en Antioquia obedece a un delicado equilibrio entre la física atmosférica, la topografía del territorio, la demanda hídrica y las estrictas reglas de seguridad electromecánica.")
    
    with st.expander("🎬 Exploración Audiovisual: Dinámicas del Agua", expanded=False):
        st.video("https://youtu.be/1rPL-wr4osE")
        st.caption("Ver https://wrp.beg.utexas.edu/episode/reservoir-evaporation-monitoring-drought-index-texas-to-global-scales sobre el comportamiento y las dinámicas del recurso hídrico a escala global.")
    
    st.markdown("### 1. Fundamentos Físicos y Contexto Territorial")
    col_fisica, col_antioquia = st.columns(2)
    
    with col_fisica:
        st.info("💧 **Evaporación (Lámina Libre) vs. Transpiración (Plantas)**")
        st.markdown("""
        Aunque a menudo se agrupan como **Evapotranspiración**, los procesos son físicamente distintos:
        * **Evaporación (Lámina Libre):** En los embalses, el agua se evapora a una tasa gobernada por el **Déficit de Presión de Vapor (VPD)** (la "sed" del aire) y la velocidad del viento, que arrastra la capa límite de humedad. No hay barreras biológicas.
        * **Transpiración (Cobertura Vegetal):** En los bosques circundantes, el agua es extraída por las raíces y liberada por los **estomas**. Las plantas regulan activamente esta pérdida cerrando los estomas bajo estrés hídrico.
        
        > 🔬 *El modelo de Penman-Monteith integra el balance de energía (Radiación Neta) con la aerodinámica (Viento y VPD) para calcular ambas tasas con precisión termodinámica.*
        """)
        
    with col_antioquia:
        st.success("⛰️ **El Contexto de Antioquia: Cañones y Zonas de Vida**")
        st.markdown("""
        Los embalses antioqueños no están en llanuras abiertas; interactúan directamente con la compleja orografía andina:
        * **Efecto de Cañón (Viento):** En embalses como **Hidroituango** o **Porce III**, los estrechos cañones canalizan y aceleran los vientos (efecto Venturi), incrementando drásticamente el componente aerodinámico de la evaporación, incluso en días nublados.
        * **Zonas de Vida de Holdridge:** Un *Bosque Húmedo Tropical* (baja altitud, alta temperatura, como Porce) sufre dinámicas muy distintas a **La Fe** o **Piedras Blancas**, ubicados en *Bosque Muy Húmedo Montano Bajo*, donde las bajas temperaturas y alta nubosidad actúan como una manta natural.
        """)

    st.markdown("---")
    st.markdown("### 2. Dinámicas del Espejo de Agua y Restricciones Operativas")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("📉 Fluctuación del Espejo de Agua")
        st.markdown("""
        Los embalses con mayor fluctuación superficial son Guatapé e Hidroituango. Debido a la topografía de vertientes y valles en Antioquia, cuando Guatapé desciende a su nivel mínimo operacional (cota 1,860 msnm), **su espejo de agua se reduce en 2,100 hectáreas**. 
        
        Esto deja expuestas grandes playas de tierra, un fenómeno crítico que altera radicalmente el ecosistema local, el albedo superficial y la economía turística de la región.
        """)
        
        st.subheader("⚙️ Regla de Operación Segura (Niveles Mínimos)")
        st.markdown("""
        El nivel mínimo de operación es la cota crítica intocable por tres razones de ingeniería:
        * **Vórtices y Cavitación:** Evita que la baja columna de agua genere remolinos que introduzcan aire destructivo a los álabes mecánicos de las turbinas.
        * **Sedimentación:** Previene la succión de lodos y arenas densas acumuladas en el fondo del embalse hacia los túneles de carga.
        * **Caso Hidroituango:** Aunque se autorizó transitoriamente su operación hacia la cota 420 msnm para robustecer el SIN, su regla de seguridad estricta prohíbe turbinar por debajo de la cota 405 para garantizar la integridad estructural de la casa de máquinas subterránea.
        """)
        
    with col_b:
        st.subheader("🎛️ Flexibilidad en Captación de Acueductos")
        st.markdown("""
        El área metropolitana del Valle de Aburrá depende de reservas críticas como **Río Grande II (138.8 Millones de m³)**, **La Fe (11.1 Millones de m³)** y **Piedras Blancas (0.5 Millones de m³)**.
        
        En estos sistemas multipropósito, las torres de captación no absorben agua de un solo punto fijo. **EPM renovó las compuertas de La Fe para permitir extracciones selectivas a 5, 12 o 17 metros de profundidad**. 
        * Si el agua superficial sufre sobrepoblación de algas por alta temperatura y radiación (potenciada por eventos de alta evaporación), se capta de las compuertas profundas.
        * Si el "fondo técnico" presenta excesos de hierro o manganeso, se capta de los niveles superiores, garantizando así la calidad del agua cruda antes de la potabilización.
        """)

# -----------------------------------------
# PESTAÑA 2: Tecnologías de Mitigación
# -----------------------------------------
with tab2:
    st.header("Tecnologías de Control y Viabilidad Financiera")
    st.markdown("Desde barreras físicas tradicionales hasta infraestructuras de generación eléctrica que protegen el recurso hídrico, existen múltiples tecnologías para frenar la pérdida por evaporación.")
    
    st.markdown("### 1. Espectro de Tecnologías Base")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("Cubiertas y Mantas Físicas")
        st.markdown("""
        Método altamente eficaz a pequeña y mediana escala al bloquear el contacto directo agua-aire.
        * **Mantas Térmicas (Burbujas):** Reducen la evaporación casi por completo y retienen el calor nocturno.
        * **Cubiertas Automáticas (Lamas):** Rígidas (PVC/policarbonato), duraderas y brindan seguridad física.
        * **Cubiertas Solares:** Filtran rayos solares para reducir la brecha térmica entre el agua y el ambiente.
        """)
        
        st.subheader("Cobertores Líquidos (Mantas Químicas)")
        st.markdown("""
        Productos biodegradables que crean una **capa monomolecular invisible**. Frenan la salida del vapor sin alterar la potabilidad. A pequeña escala son económicos, pero a gran escala requieren dosificación "upwind" constante, perdiendo viabilidad.
        """)
    with col_t2:
        st.subheader("Sistemas de Esferas Flotantes (Barrier Balls)")
        st.markdown("""
        Esferas de plástico con protección UV que cubren la superficie bloqueando más del 90% de la interfaz agua-aire. Minimizan la radiación directa, reducen el crecimiento de algas y se apartan fácilmente ante intrusiones físicas.
        """)
        
        st.subheader("⬡ Módulos Hexagonales Autoconectables")
        st.markdown("""
        Alternativa mecánica modular (HexaCovers). Paneles de plástico que flotan y se autoensamblan geométricamente. Se adaptan dinámicamente al nivel del agua; si el embalse baja, se apilan en las orillas sin sufrir daños.
        """)

    st.markdown("---")
    st.markdown("### 2. Análisis Financiero y Evaluación Comparativa Dinámica")
    st.markdown("Ajuste el tamaño del embalse y seleccione una tecnología para proyectar su viabilidad a escala industrial (Cálculo basado en una cobertura del 40% de la superficie).")

    col_area, col_tech = st.columns([1, 2])
    with col_area:
        area_eval_ha = st.number_input("📐 Área total del embalse a evaluar (Hectáreas):", min_value=1.0, value=20.0, step=5.0)
    with col_tech:
        tech_eval = st.selectbox("🔍 Seleccionar Tecnología a Evaluar:", [
            "☀️ Paneles Solares Flotantes (Floatovoltaics - FPV)",
            "⬡ Módulos Hexagonales Autoconectables",
            "🌑 Sistemas de Esferas Flotantes (Barrier Balls)",
            "🛡️ Cubiertas y Mantas Físicas (Burbujas, Lamas, Solares)"
        ])

    tab_fin, tab_sin = st.tabs(["💰 Modelo Financiero y Viabilidad", "📊 Síntesis Comparativa Global"])

    with tab_fin:
        col_info, col_galeria = st.columns([1.6, 1.4])
        
        def obtener_galeria(prefijos):
            ruta_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'Fotos'))
            imgs = []
            if os.path.exists(ruta_base):
                for f in os.listdir(ruta_base):
                    if any(p.lower() in f.lower() for p in prefijos):
                        imgs.append(os.path.join(ruta_base, f))
            return sorted(imgs)
            
        with col_info:
            # --- CÁLCULOS DINÁMICOS BASADOS EN EL ÁREA SELECCIONADA ---
            area_cubierta_m2 = area_eval_ha * 10000 * 0.40 # 40% de cobertura
            factor_escala = area_eval_ha / 20.0
            mwp_instalado = 10.0 * factor_escala
            
            if "Paneles Solares" in tech_eval:
                st.success("**Tecnología Líder en Costo-Efectividad a Gran Escala:** Genera sinergia Agua-Energía.")
                tab_f1, tab_f2, tab_f3 = st.tabs(["Desglose Inversión", "Beneficios Fiscales", "Retorno (ROI)"])
                with tab_f1:
                    st.markdown(f"El CAPEX solar flotante oscila entre **$0.55 y $0.80 USD por vatio**. Cubrir el 40% del embalse ({area_cubierta_m2:,.0f} m²) permite instalar unos **{mwp_instalado:,.1f} MWp**. Inversión bruta: **${(6.70 * factor_escala):,.2f}M a ${(8.05 * factor_escala):,.2f}M USD**.")
                    df_capex = pd.DataFrame({
                        "Componente": ["Módulos Fotovoltaicos", "Flotadores HDPE y Pasarelas", "Inversores y Equipos", "Anclaje y Amarre", "BOP Eléctrico", "Ingeniería y Permisos"],
                        "Participación": ["35%", "22%", "16%", "12%", "8%", "7%"]
                    })
                    st.table(df_capex)
                with tab_f2:
                    st.markdown(f"""
                    Bajo las **Leyes 1715 y 2099**, el desembolso se reduce a **${(4.5 * factor_escala):,.2f}M - ${(5.5 * factor_escala):,.2f}M USD**:
                    * **Exclusión IVA (19%) y Exención Arancelaria** para equipos importados.
                    * **Deducción de Renta:** Hasta el 50% de la inversión en 15 años.
                    * **Depreciación Acelerada:** Amortización en 3 a 5 años.
                    """)
                with tab_f3:
                    st.markdown(f"""
                    Al generar {(13.5 * factor_escala):,.1f} GWh/año para autoconsumo en bombeo, desplazando tarifas de EPM ($700-$900 COP/kWh):
                    * **Ahorro Bruto Anual:** ${(2.5 * factor_escala):,.2f} - ${(3.0 * factor_escala):,.2f} Millones USD.
                    * **Payback:** **2.5 a 4 años**. Vida útil restante (20+ años) como flujo de caja positivo.
                    """)

            elif "Hexagonales" in tech_eval:
                st.info("**Alternativa Mecánica de Alta Durabilidad:** Ideal si la interconexión eléctrica no es viable.")
                st.markdown(f"""
                * **CAPEX (Inversión Inicial):** Moderada-Alta. Cubrir {area_cubierta_m2:,.0f} m² (40% de {area_eval_ha} Ha) cuesta aprox. **${(1.2 * factor_escala):,.2f}M - ${(2.0 * factor_escala):,.2f}M USD** ($15 - $25 USD/m²).
                * **OPEX (Gasto Recurrente):** Casi nulo. No requieren limpieza constante ni consumen energía.
                * **Retorno Financiero:** Indirecto. Se amortiza en 7 a 10 años basándose exclusivamente en el valor del agua cruda salvada.
                * **Viabilidad Técnica:** Excelente en topografías complejas; soportan fluctuaciones severas de cota sin tensión estructural.
                """)

            elif "Esferas" in tech_eval:
                st.warning("**Control Dinámico:** Famosas por su uso en el Embalse de Los Ángeles.")
                st.markdown(f"""
                * **CAPEX (Inversión Inicial):** Moderada. Aprox. **${(800 * factor_escala):,.0f}k - ${(1.2 * factor_escala):,.2f}M USD** para {area_cubierta_m2:,.0f} m² ($10 - $15 USD/m²).
                * **OPEX (Gasto Recurrente):** Bajo, pero superior a los hexágonos. Las esferas pueden acumular biopelículas o ser expulsadas a las orillas.
                * **Retorno Financiero:** 5 a 8 años por retención hídrica. 
                * **Limitación en Antioquia:** En cañones con efecto Venturi (vientos acelerados), las esferas tienden a apilarse en un solo extremo del embalse, perdiendo efectividad de cobertura.
                """)

            elif "Mantas" in tech_eval:
                st.error("**Descarte a Gran Escala:** Eficaces en piscinas y acueductos veredales, inviables en embalses.")
                st.markdown(f"""
                * **Mantas de Burbujas / Solares:** Extremadamente vulnerables al desgarro por fatiga mecánica (viento y oleaje en {area_eval_ha} Hectáreas). Vida útil reducida a 1-2 años a la intemperie total.
                * **Cubiertas de Lamas:** Costo prohibitivo a escala industrial (supera los $100 USD/m²), requiriendo infraestructuras de enrollado masivas imposibles de anclar en riberas irregulares.
                * **Veredicto:** Su uso debe restringirse a tanques de almacenamiento, plantas de tratamiento (PTAP) o reservorios menores a 1 Hectárea.
                """)

        # --- COLUMNA DE LA GALERÍA VISUAL INTERACTIVA ---
        with col_galeria:
            st.markdown("#### 📸 Explorador Visual y Casos de Estudio")
            
            # 1. GALERÍA DE FOTOS (CON EL FIX APLICADO)
            prefijos_busqueda = []
            if "Paneles Solares" in tech_eval:
                prefijos_busqueda = ["paneles_solares", "floating_solar"]
            elif "Hexagonales" in tech_eval:
                prefijos_busqueda = ["hexa-cover"]
            elif "Esferas" in tech_eval:
                prefijos_busqueda = ["esferas_flotantes"]
            elif "Mantas" in tech_eval:
                prefijos_busqueda = ["mantas_flotantes"]
            
            galeria = obtener_galeria(prefijos_busqueda)
            
            if galeria:
                if len(galeria) > 1:
                    idx = st.slider("Desliza para ver más fotografías:", 1, len(galeria), 1) - 1
                    # 🔥 FIX APLICADO: use_container_width en lugar de use_column_width
                    st.image(galeria[idx], use_container_width=True, caption=f"Fotografía {idx+1} de {len(galeria)}")
                else:
                    st.image(galeria[0], use_container_width=True, caption="Fotografía de referencia")
            else:
                st.info("💡 Agrega imágenes con los prefijos correctos en tu carpeta 'frontend/data/Fotos/' para verlas aquí.")
            
            st.markdown("---")
            
            # 2. SECCIÓN DE VIDEOS PEDAGÓGICOS
            st.markdown("#### 🎬 Referencias Documentales")
            
            st.markdown("---")
            if "Esferas" in tech_eval:
                st.video("https://www.youtube.com/watch?v=x7GWPTZBJd0")
            elif "Hexagonales" in tech_eval:
                st.video("https://www.youtube.com/watch?v=37mrElHtc8E")
            elif "Paneles" in tech_eval:
                st.info("📺 **Ver Documental:** [Floatovoltaics (Facebook Watch)](https://www.facebook.com/unboxfactory/videos/a-major-river-system-supplying-water-to-around-40-million-americans-is-now-testi/1475959924012973/)")
                st.caption("Documental corto explicando el funcionamiento de las esferas de sombra para control de algas y evaporación.")
            
            elif "Paneles Solares" in tech_eval:
                st.markdown("**El Nexo Agua-Energía (Floatovoltaics)**")
                # Enlace interactivo y estético para el documental de Facebook (o cualquier otra fuente FPV)
                st.info("📺 **Ver Documental:** [El Gran Proyecto Solar Hídrico (Facebook Watch)](https://www.facebook.com/unboxfactory/videos/a-major-river-system-supplying-water-to-around-40-million-americans-is-now-testi/1475959924012973/)")
                st.caption("Haz clic en el enlace superior para ver la cobertura de los megaproyectos sobre canales y reservas de agua.")
            
            else:
                st.caption("Selecciona 'Paneles Solares' o 'Sistemas de Esferas' para desbloquear los documentales en video asociados a estas tecnologías.")

    # --- PESTAÑA SÍNTESIS GLOBAL ---
    with tab_sin:
        st.markdown("#### Matriz de Decisión: Costo-Efectividad para Embalses (Escala > 10 Hectáreas)")
        df_sintesis = pd.DataFrame({
            "Tecnología": [
                "Solares Flotantes (FPV)", 
                "Módulos Hexagonales", 
                "Barrier Balls (Esferas)", 
                "Mantas Físicas (Burbujas/Lamas)", 
                "Cobertor Líquido (Químico)"
            ],
            "Inversión Inicial (CAPEX)": ["Muy Alta", "Moderada - Alta", "Moderada", "Alta (Lamas) / Baja (Burbujas)", "Muy Baja"],
            "Costo Operativo (OPEX)": ["Bajo (Mantenimiento eléctrico)", "Casi Nulo", "Bajo", "Alto (Reemplazos frecuentes)", "Muy Alto (Dosis perpetuas)"],
            "Retorno de Inversión": ["2.5 - 4 Años (Ahorro Agua, Genera Energía, Mejora la Calidad)", "7 - 10 Años (Ahorra Agua, Mejora Calidad)", "5 - 8 Años (Ahorra Agua, Mejora Calidad)", "Inviable a gran escala", "No se amortiza (Gasto fijo)"],
            "Viabilidad en Antioquia": ["⭐⭐⭐⭐⭐ (Excelente)", "⭐⭐⭐⭐ (Muy Buena)", "⭐⭐ (Riesgo por vientos)", "⭐ (Útil en áreas pequeñas o crisis)", "⭐ (Áreas pequeñas o crisis)"]
        })
        st.dataframe(df_sintesis, use_container_width=True, hide_index=True)
        st.caption("Nota: La viabilidad en Antioquia considera la topografía de cañones (vientos fuertes) y la necesidad de mantener la potabilidad del agua libre de aditivos constantes.")

# -----------------------------------------
# PESTAÑA 3: Base de Datos Maestra
# -----------------------------------------
with tab3:
    st.header("🗄️ Parámetros Físicos y Batimétricos de Antioquia")
    st.markdown("Inventario técnico consolidado extraído del archivo `Area Volumen embalses Antioquia.xlsx`.")
    
    if not df_embalses.empty:
        import plotly.express as px
        
        st.markdown("### 📊 Analítica Comparativa de Embalses")
        
        # 1. Identificar dinámicamente qué columnas se pueden graficar
        cols_numericas = []
        for c in df_embalses.columns:
            if c != 'Embalse' and pd.to_numeric(df_embalses[c], errors='coerce').notnull().any():
                cols_numericas.append(c)
                
        df_grafico = df_embalses.copy()
        for c in cols_numericas:
            df_grafico[c] = pd.to_numeric(df_grafico[c], errors='coerce')
            
        # 2. Controles Dinámicos
        col_ctrl1, col_ctrl2 = st.columns(2)
        with col_ctrl1:
            metrica_sel = st.selectbox("📏 Seleccionar Métrica a Comparar:", cols_numericas, index=0)
        with col_ctrl2:
            orden_sel = st.radio("⬇️ Ordenar por:", ["De Mayor a Menor", "De Menor a Mayor"], horizontal=True)
            
        ascendente = True if orden_sel == "De Menor a Mayor" else False
        df_grafico = df_grafico.dropna(subset=[metrica_sel]).sort_values(by=metrica_sel, ascending=ascendente)
        
        # 3. Panel de Indicadores Top
        st.markdown("#### 🏆 Topologías Destacadas")
        ind1, ind2, ind3, ind4 = st.columns(4)
        
        def obtener_top(df, col):
            if col in df.columns and not df[col].isnull().all():
                return df.loc[df[col].idxmax()]['Embalse']
            return "N/A"
            
        ind1.metric("🌊 Mayor Espejo de Agua", obtener_top(df_grafico, 'Área Máxima (ha)'), "Por Área Máxima")
        ind2.metric("📦 Mayor Almacenamiento", obtener_top(df_grafico, 'Volumen Máximo (Mm³)'), "Por Vol. Máximo")
        ind3.metric("🕳️ Mayor Profundidad", obtener_top(df_grafico, 'Profundidad Máxima (m)'), "Por Prof. Máxima")
        ind4.metric("⛰️ Mayor Altitud", obtener_top(df_grafico, 'Altura Promedio Cota Máx (msnm)'), "Por Cota msnm")
        
        # 4. Gráfico de Barras Interactivo
        fig_comp = px.bar(
            df_grafico, 
            x='Embalse', 
            y=metrica_sel, 
            text_auto='.2s',
            color=metrica_sel,
            color_continuous_scale='Teal' if ascendente else 'Blues',
            title=f"Comparativa Global: {metrica_sel}"
        )
        fig_comp.update_layout(margin=dict(t=40, b=0, l=0, r=0), coloraxis_showscale=False)
        st.plotly_chart(fig_comp, use_container_width=True)
        
        st.markdown("---")
        
        # 5. Gráfico Fijo: Eficiencia Morfológica (Relación Volumen / Área)
        st.markdown("#### 📐 Eficiencia Morfológica: Relación Volumen / Área")
        st.info('💡 **Nota Técnica:** La relación Volumen / Área (Mm³/ha) es una métrica de "eficiencia morfológica" que permite entender qué embalses son similares a una "bandeja" (mucha área, poca profundidad = alta evaporación) y cuáles son como un "vaso" (poca área, mucha profundidad = baja evaporación relativa).')
        st.caption("🔍 **Cómo leer el gráfico:** Los embalses a la izquierda (valores altos) tienen una morfología tipo 'vaso' y minimizan las pérdidas por evaporación respecto a su volumen almacenado. Los embalses a la derecha (valores bajos) tienen una morfología tipo 'bandeja', exponiendo una gran superficie térmica y siendo más vulnerables a la evaporación masiva.")
        
        # Cálculo seguro del Ratio
        df_ratio = df_embalses.copy()
        df_ratio['Vol_num'] = pd.to_numeric(df_ratio['Volumen Máximo (Mm³)'], errors='coerce')
        df_ratio['Area_num'] = pd.to_numeric(df_ratio['Área Máxima (ha)'], errors='coerce')
        df_ratio = df_ratio.dropna(subset=['Vol_num', 'Area_num'])
        df_ratio = df_ratio[df_ratio['Area_num'] > 0] # Evitar divisiones por cero
        
        df_ratio['Ratio (Mm³/ha)'] = df_ratio['Vol_num'] / df_ratio['Area_num']
        df_ratio = df_ratio.sort_values(by='Ratio (Mm³/ha)', ascending=False)
        
        fig_ratio = px.bar(
            df_ratio, 
            x='Embalse', 
            y='Ratio (Mm³/ha)', 
            text_auto='.4f',
            color='Ratio (Mm³/ha)',
            color_continuous_scale='Emrld',
            title="Relación Volumen / Área (Mm³/ha)"
        )
        fig_ratio.update_layout(margin=dict(t=40, b=0, l=0, r=0), coloraxis_showscale=False)
        st.plotly_chart(fig_ratio, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 📋 Matriz de Datos Crudos")

        # FIX: Convertir a string para visualización segura sin corromper Arrow
        df_display = df_embalses.astype(str).copy()
        st.dataframe(df_display, use_container_width=True, hide_index=True, height=300)
        
        csv_export = df_embalses.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Descargar Base de Datos (CSV)",
            data=csv_export,
            file_name="Parametros_Embalses_Antioquia.csv",
            mime="text/csv",
            type="primary"
        )
    else:
        st.warning("⚠️ No se encontró la base de datos maestra.")

# -----------------------------------------
# PESTAÑA 4: Simulador Termodinámico (Dashboard de Control)
# -----------------------------------------
with tab4:
    import plotly.express as px
    from plotly.subplots import make_subplots
    
    st.header("🎛️ Centro de Simulación y Control de Escenarios")
    
    # 1. Definición del Motor Termodinámico Reutilizable
    def calcular_penman(alt, lat, dia, tmax, tmin, rh, viento, rad_sol, albedo):
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

    # Mapeo de Latitudes base aproximadas
    latitudes = {
        "Guatapé (El Peñol)": 6.26, "Hidroituango": 7.13, "Jaguas": 6.31,
        "La Fe": 6.11, "Piedras Blancas": 6.29, "Playas": 6.27,
        "Porce II": 6.75, "Porce III": 6.80, "Riogrande II": 6.55, "San Carlos": 6.21
    }

    # --- PANEL LATERAL DE CONTROL (CON EXPANDERS) ---
    with st.sidebar:
        with st.expander("⚙️ Geometría y Batimetría (CAV)", expanded=True):
            if not df_embalses.empty and 'Embalse' in df_embalses.columns:
                lista_embalses = ["Personalizado"] + df_embalses['Embalse'].dropna().tolist()
                embalse_sel = st.selectbox("🌊 Seleccionar Embalse", lista_embalses)
                if embalse_sel != "Personalizado":
                    fila = df_embalses[df_embalses['Embalse'] == embalse_sel].iloc[0]
                    def_alt = float(fila.get('Altura Promedio Cota Máx (msnm)', 2150.0))
                    def_area = float(fila.get('Área Máxima (ha)', 100.0))
                    # Usamos el Volumen Máximo Total para la precisión del polinomio CAV
                    def_vol_max = float(fila.get('Volumen Máximo (Mm³)', 10.0))
                    def_min_op = float(fila.get('Nivel Mínimo Operación / Regla Segura (msnm)', 0.0))
                    def_lat = latitudes.get(embalse_sel, 6.28)
                else:
                    def_alt, def_lat, def_area, def_vol_max, def_min_op = 2150.0, 6.28, 100.0, 10.0, 0.0
            else:
                embalse_sel = "Personalizado"
                def_alt, def_lat, def_area, def_vol_max, def_min_op = 2150.0, 6.28, 100.0, 10.0, 0.0

            # Límites Matemáticos (Sin bloquear la UI)
            cota_min_val = round(float(def_min_op), 1) if (def_min_op > 0 and def_min_op < def_alt) else 0.0
            cota_max_val = round(float(def_alt), 1) if def_alt > 0 else 0.0

            # 🔥 FIX: Se agregaron llaves (keys) dinámicas para que los valores se reseteen al cambiar de embalse.
            altitud = st.number_input(
                "Cota Máxima (msnm)", 
                value=float(def_alt), step=50.0, key=f"alt_{embalse_sel}",
                help="Nivel máximo de llenado del embalse (cota de vertedero o corona). Define el 100% de la capacidad operativa."
            )
            
            cota_input = st.number_input(
                "📡 Cota Actual (Lectura XM)", 
                value=float(def_alt * 0.98), step=1.0, key=f"cot_{embalse_sel}",
                help="Nivel actual del espejo de agua. La plataforma auto-calibra los volúmenes usando este dato."
            )
            
            # Autoajuste de Seguridad (Evita el StreamlitValueBelowMinError)
            cota_actual = cota_input
            if cota_min_val > 0 and cota_actual < cota_min_val:
                st.warning(f"⚠️ Autoajuste: La Regla Segura impide operar por debajo de {cota_min_val:,.1f} msnm.")
                cota_actual = cota_min_val
            if cota_max_val > 0 and cota_actual > cota_max_val:
                st.warning(f"⚠️ Autoajuste: El nivel no puede superar la Cota Máxima de {cota_max_val:,.1f} msnm.")
                cota_actual = cota_max_val

            if embalse_sel != "Personalizado":
                st.info(f"📏 **Límites Aceptables:** Mín: **{cota_min_val:,.0f} msnm** | Máx: **{cota_max_val:,.0f} msnm**")

            latitud = st.number_input(
                "Latitud (°)", value=float(def_lat), step=0.1, key=f"lat_{embalse_sel}",
                help="Coordenada geográfica utilizada para calcular la declinación solar y el balance de radiación."
            )
            
            area_ha = st.number_input(
                "Área Máxima (ha)", 
                value=float(def_area), step=10.0, key=f"are_{embalse_sel}",
                help="Superficie del espejo de agua en hectáreas cuando el embalse alcanza la cota máxima."
            )
            
            volumen_max_mm3 = st.number_input(
                "Volumen Máximo Total (Mm³)", 
                value=float(def_vol_max), step=1.0, key=f"vol_{embalse_sel}",
                help="Capacidad volumétrica total (Útil + Muerto) del embalse. Este es el ancla matemática del Polinomio CAV."
            )
            
        with st.expander("🌤️ Clima Diario (Línea Base)", expanded=False):
            dia_ano = st.slider("Día del año", 1, 365, 152)
            t_max = st.slider("Temp. Máxima (°C)", 15.0, 45.0, 26.0)
            t_min = st.slider("Temp. Mínima (°C)", 5.0, 30.0, 16.0)
            rh_media = st.slider("Humedad Relativa (%)", 30.0, 100.0, 75.0)
            viento_2m = st.slider("Viento a 2m (m/s)", 0.0, 10.0, 2.0)
            rs = st.slider("Radiación Solar (MJ/m²/día)", 5.0, 30.0, 18.0)
            
        with st.expander("🔬 Laboratorio de Escenarios", expanded=False):
            escenario_climatico = st.selectbox("🌦️ Escenario Climático", ["Línea Base", "🔥 El Niño (Cálido/Seco)", "🌧️ La Niña (Húmedo/Nublado)", "🌍 Cambio Climático 2050"])
            calidad_agua = st.selectbox("🧪 Estado de Calidad", ["Óptima (Albedo 0.08)", "🦠 Eutrofización/Algas (Albedo 0.12)", "🟤 Alta Turbidez (Albedo 0.10)"])
            mitigacion = st.selectbox("🛡️ Intervención Tecnológica", ["Ninguna", "Bolas de Sombra (85% red.)", "Solares Flotantes FPV (50% red.)", "Mallas de Sombreo (75% red.)", "Monocapas Químicas (25% red.)"])

        with st.expander("👥 Demanda Hídrica Poblacional", expanded=False):
            poblacion_analisis = st.number_input("Población a Abastecer (Hab)", value=1000000, step=50000, help="Población analizada (ej. habitantes del Valle de Aburrá).")
            consumo_per_capita = st.slider("Consumo Per Cápita (L/hab-día)", 50, 300, 150)
            escala_temporal = st.selectbox("Escala Temporal de Análisis", ["Día", "Semana", "Mes", "Año"], index=3)
    
    # --- APLICACIÓN DE MODIFICADORES ---
    mod_tmax, mod_tmin, mod_rh, mod_rs = t_max, t_min, rh_media, rs
    if escenario_climatico == "🔥 El Niño (Cálido/Seco)":
        mod_tmax += 2.0; mod_rh = max(30.0, mod_rh - 10.0); mod_rs += 2.0
    elif escenario_climatico == "🌧️ La Niña (Húmedo/Nublado)":
        mod_tmax -= 1.0; mod_rh = min(100.0, mod_rh + 10.0); mod_rs -= 2.0
    elif escenario_climatico == "🌍 Cambio Climático 2050":
        mod_tmax += 2.5; mod_tmin += 1.5; mod_rs += 1.0

    if "Eutrofización" in calidad_agua: albedo_final = 0.12
    elif "Turbidez" in calidad_agua: albedo_final = 0.10
    else: albedo_final = 0.08

    factor_mit = 0.0
    if "Bolas" in mitigacion: factor_mit = 0.85
    elif "Solares" in mitigacion: factor_mit = 0.50
    elif "Mallas" in mitigacion: factor_mit = 0.75
    elif "Monocapas" in mitigacion: factor_mit = 0.25

    # --- CÁLCULOS TERMODINÁMICOS Y DE BATIMETRÍA ---
    coef_alfa = volumen_max_mm3 / (altitud**3) if altitud > 0 else 0
    volumen_xm_calculado = coef_alfa * (cota_actual**3)
    eq_cav_str = f"V(z) = {coef_alfa:.2e}·z³"

    evap_dia, term_rad, term_aero, vpd, rn, P = calcular_penman(
        altitud, latitud, dia_ano, mod_tmax, mod_tmin, mod_rh, viento_2m, mod_rs, albedo_final
    )
    evap_mitigada_dia = evap_dia * (1 - factor_mit)
    
    # Cálculos Físicos Base
    area_dinamica_ha = area_ha * ((cota_actual / altitud)**2) if altitud > 0 else area_ha
    evap_dia, term_rad, term_aero, vpd, rn, P = calcular_penman(altitud, latitud, dia_ano, mod_tmax, mod_tmin, mod_rh, viento_2m, mod_rs, albedo_final)
    
    evap_mitigada_dia = evap_dia * (1 - factor_mit)
    perdida_vol_dia = evap_mitigada_dia * area_dinamica_ha * 10
    vol_salvado_dia = (evap_dia - evap_mitigada_dia) * area_dinamica_ha * 10
    piscinas_dia = perdida_vol_dia / 2500.0

    # --- CÁLCULOS DE DEMANDA POBLACIONAL Y ESCALAS ---
    dias_escala = {"Día": 1, "Semana": 7, "Mes": 30, "Año": 365}[escala_temporal]
    demanda_litros_escala = poblacion_analisis * consumo_per_capita * dias_escala
    demanda_m3_escala = demanda_litros_escala / 1000.0
    piscinas_demanda = demanda_m3_escala / 2500.0
    
    evap_vol_escala = perdida_vol_dia * dias_escala
    pct_evap_vs_demanda = (evap_vol_escala / demanda_m3_escala) * 100 if demanda_m3_escala > 0 else 0

    st.markdown(f"### Análisis Dinámico para: **{embalse_sel}**")
    
    k1, k2, k_piscina, k3, k4, k5, k6 = st.columns(7)
    k1.metric("💧 Evap. Neta", f"{evap_mitigada_dia:.2f} mm/día", f"Base: {evap_dia:.2f}" if factor_mit > 0 else None, delta_color="inverse")
    k2.metric("📉 Pérdida Vol.", f"{perdida_vol_dia:,.0f} m³/día", "Diario", delta_color="off")
    k_piscina.metric("🏊‍♂ Escala Física", f"{piscinas_dia:,.1f} Piscinas/día", "Olímpicas (2.5k m³)", delta_color="off")
    k3.metric("🛡️ Agua Salvada", f"{vol_salvado_dia:,.0f} m³/día", f"{(factor_mit*100):.0f}%" if factor_mit > 0 else "Sin mitigar")
    k4.metric("📐 Área Dinámica", f"{area_dinamica_ha:,.0f} ha", f"Cota XM: {cota_actual:.0f}m")
    k5.metric("📦 Vol. Estimado", f"{(volumen_max_mm3*(cota_actual/altitud)**3):,.1f} Mm³", "Polinomio CAV")
    k6.metric("📊 Ecuación CAV", eq_cav_str, "Sincronizado XM")
    
    st.markdown("---")
    
    # --- DASHBOARD DE DEMANDA SOCIAL ---
    st.markdown(f"#### 👥 Tensión Hídrica: Evaporación vs. Demanda ({escala_temporal})")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric(f"🚰 Demanda Requerida", f"{demanda_m3_escala:,.0f} m³", f"Pop: {poblacion_analisis:,} hab", delta_color="off")
    d2.metric(f"🏊‍♂️ Equivalencia Demanda", f"{piscinas_demanda:,.1f} Piscinas", "Volumen en Olímpicas", delta_color="off")
    d3.metric(f"🌤️ Pérdida por Evaporación", f"{evap_vol_escala:,.0f} m³", f"Acumulado en el {escala_temporal}", delta_color="inverse")
    d4.metric("⚠️ Peso Evap. vs Demanda", f"{pct_evap_vs_demanda:,.1f} %", "Porcentaje de la provisión", delta_color="inverse")

    st.markdown("---")

    col_izq, col_der = st.columns(2)
    with col_izq:
        st.markdown("#### 1. Motores del Flujo Evaporativo")
        
        # Cálculos de traducción anual para la gráfica
        suma_terms = term_rad + term_aero
        pct_rad = term_rad / suma_terms if suma_terms > 0 else 0
        pct_aero = term_aero / suma_terms if suma_terms > 0 else 0
        
        vol_anual_litros = perdida_vol_dia * 365 * 1000
        litros_rad = vol_anual_litros * pct_rad
        litros_aero = vol_anual_litros * pct_aero
        
        consumo_anual_pc = consumo_per_capita * 365
        personas_rad = litros_rad / consumo_anual_pc if consumo_anual_pc > 0 else 0
        personas_aero = litros_aero / consumo_anual_pc if consumo_anual_pc > 0 else 0

        fig_pie = go.Figure(data=[go.Pie(
            labels=['Motor Radiativo (Solar)', 'Motor Aerodinámico (Viento/VPD)'],
            values=[max(0, term_rad), max(0, term_aero)],
            hole=.4, marker_colors=['#FF9900', '#3399FF'],
            # Agregamos los datos customizados para mostrarlos al pasar el ratón
            customdata=[
                [f"{litros_rad:,.0f} L/Año", f"{personas_rad:,.0f} Hab"],
                [f"{litros_aero:,.0f} L/Año", f"{personas_aero:,.0f} Hab"]
            ],
            hovertemplate="<b>%{label}</b><br>Impacto: %{percent}<br>Equivale a: %{customdata[0]}<br>Abastecería a: %{customdata[1]}<extra></extra>"
        )])
        fig_pie.update_layout(margin=dict(t=10, b=10, l=0, r=0), height=300)
        st.plotly_chart(fig_pie, use_container_width=True)
        st.caption(f"💡 **Costo Social Anual:** La evaporación impulsada por radiación equivaldría al abastecimiento anual de **{personas_rad:,.0f} personas**. La evaporación por viento al de **{personas_aero:,.0f} personas**.")

    with col_der:
        st.markdown("#### 2. Radiografía Regional de Pérdidas")
        tipo_grafico = st.radio("Métrica de Análisis", ["Pérdidas Absolutas (m³/día)", "Impacto Relativo (% del Volumen Útil/día)"], horizontal=True)
        
        if not df_embalses.empty:
            nombres, valores = [], []
            for _, row in df_embalses.iterrows():
                e_nom = row['Embalse']
                e_alt = float(row.get('Altura Promedio Cota Máx (msnm)', 2150.0))
                e_area = float(row.get('Área Máxima (ha)', 100.0))
                e_vol = float(row.get('Volumen Útil (Mm³)', 1.0))
                if e_vol == 0: e_vol = 1.0 
                e_lat = latitudes.get(e_nom, 6.28)
                
                e_evap, _, _, _, _, _ = calcular_penman(e_alt, e_lat, dia_ano, mod_tmax, mod_tmin, mod_rh, viento_2m, mod_rs, albedo_final)
                e_perdida = (e_evap * (1 - factor_mit)) * e_area * 10
                
                nombres.append(e_nom)
                if "Absolutas" in tipo_grafico:
                    valores.append(e_perdida)
                else:
                    impacto_pct = (e_perdida / (e_vol * 1_000_000)) * 100
                    valores.append(impacto_pct)
                
            eje_x_title = 'Pérdida (m³)' if "Absolutas" in tipo_grafico else 'Pérdida (% Vol. Útil)'
            df_reg = pd.DataFrame({'Embalse': nombres, eje_x_title: valores}).sort_values(eje_x_title, ascending=True)
            
            formato_texto = '.2s' if "Absolutas" in tipo_grafico else '.3f'
            fig_bar = px.bar(df_reg, x=eje_x_title, y='Embalse', orientation='h', text_auto=formato_texto, color=eje_x_title, color_continuous_scale='Reds')
            fig_bar.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=310, coloraxis_showscale=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Carga la base de datos para ver la comparativa regional.")

    st.markdown("---")
    
    c_anual, c_mitig = st.columns(2)
    with c_anual:
        st.markdown(f"#### 3. Ciclo Hidrológico Anual: {embalse_sel}")
        st.caption("Proyección asumiendo el clima base sostenido, modulado por la declinación solar.")
        
        dias_mes = [15, 45, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]
        meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        dias_por_mes = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        vols_mensuales, vols_acumulados, acum = [], [], 0
        
        for d, d_mes in zip(dias_mes, dias_por_mes):
            ev, _, _, _, _, _ = calcular_penman(altitud, latitud, d, mod_tmax, mod_tmin, mod_rh, viento_2m, mod_rs, albedo_final)
            vol_m = (ev * (1 - factor_mit)) * area_dinamica_ha * 10 * d_mes
            vols_mensuales.append(vol_m)
            acum += vol_m
            vols_acumulados.append(acum)
            
        fig_anual = make_subplots(specs=[[{"secondary_y": True}]])
        fig_anual.add_trace(go.Bar(x=meses, y=vols_mensuales, name="Pérdida Mes", marker_color='#3498db'), secondary_y=False)
        fig_anual.add_trace(go.Scatter(x=meses, y=vols_acumulados, name="Acumulado", line=dict(color='#e74c3c', width=3)), secondary_y=True)
        
        fig_anual.update_layout(
            height=320, 
            margin=dict(t=30, b=10, l=0, r=0), 
            legend=dict(orientation="h", yanchor="top", y=1.1, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_anual, use_container_width=True)

    with c_mitig:
        st.markdown("#### 4. Evaluación de Alternativas de Mitigación")
        st.caption("Comparativa de agua salvada (m³/día) vs. Índice de costo relativo para cada tecnología.")
        
        evap_base, _, _, _, _, _ = calcular_penman(altitud, latitud, dia_ano, mod_tmax, mod_tmin, mod_rh, viento_2m, mod_rs, albedo_final)
        vol_perdida_base = evap_base * area_dinamica_ha * 10
        
        techs = ["Bolas de Sombra", "Solares Flotantes", "Mallas de Sombreo", "Monocapas Químicas"]
        reds = [0.85, 0.50, 0.75, 0.25]
        costos = [4.0, 5.0, 3.5, 1.0] 
        agua_salvada = [vol_perdida_base * r for r in reds]
        
        df_mit = pd.DataFrame({'Tecnología': techs, 'Agua Salvada (m³)': agua_salvada, 'Índice de Costo': costos})
        df_mit = df_mit.sort_values('Agua Salvada (m³)', ascending=True)
        
        fig_scatter = px.scatter(df_mit, x='Índice de Costo', y='Agua Salvada (m³)', color='Tecnología', size='Agua Salvada (m³)', text='Tecnología', size_max=40)
        fig_scatter.update_traces(textposition='bottom center')
        fig_scatter.update_layout(height=320, margin=dict(t=30, b=10, l=0, r=0), showlegend=False, xaxis=dict(range=[0, 6], title="Costo Relativo (1=Bajo, 5=Muy Alto)"))
        st.plotly_chart(fig_scatter, use_container_width=True)

# -----------------------------------------
# PESTAÑA 5: Telemetría XM (Últimos 3 Meses)
# -----------------------------------------
with tab5:
    st.header("📡 Telemetría XM: Dinámica Real del Embalse (Últimos 90 Días)")
    st.markdown("Conexión en vivo al portal de datos del Sistema Interconectado Nacional (XM S.A. E.S.P.) para extraer la curva real histórica.")
    
    if st.button("📡 Conectar con Servidores XM y Descargar Curva Real", type="primary"):
        
        if "Personalizado" in embalse_sel:
            st.warning("⚠️ XM no tiene registros para un embalse 'Personalizado'. Selecciona un embalse en el menú lateral.")
            
        elif any(acueducto in embalse_sel.upper() for acueducto in ["LA FE", "PIEDRAS BLANCAS"]):
            st.info(f"ℹ️ **{embalse_sel}** es un embalse de uso exclusivo para acueducto y potabilización (EPM). Al no generar energía para el Sistema Interconectado Nacional, no reporta telemetría a XM.")
            
        else:
            with st.spinner("Descargando catálogo y estableciendo conexión segura con XM..."):
                try:
                    import datetime as dt
                    from pydataxm import *
                    import plotly.express as px
                    import re
                    
                    api_xm = pydataxm.ReadDB()
                    end_date = dt.date.today() - dt.timedelta(days=5)
                    start_date = end_date - dt.timedelta(days=90)
                    
                    cat = api_xm.get_collections()
                    metric_id_volumen = "VolUtil"
                    
                    if not cat.empty:
                        filtro = cat[cat['MetricName'].str.contains('Volumen', case=False, na=False) & 
                                     cat['MetricName'].str.contains('til', case=False, na=False)]
                        if not filtro.empty:
                            metric_id_volumen = filtro.iloc[0]['MetricId']
                    
                    df_xm = api_xm.request_data(metric_id_volumen, "Embalse", start_date, end_date)
                    
                    if not df_xm.empty:
                        col_name = next((c for c in df_xm.columns if 'NAME' in c.upper() or 'SISTEMA' in c.upper()), None)
                        col_date = next((c for c in df_xm.columns if 'DATE' in c.upper() or 'FECHA' in c.upper()), None)
                        col_value = next((c for c in df_xm.columns if 'VALUE' in c.upper() or 'VALOR' in c.upper()), None)
                        
                        if col_name and col_date and col_value:
                            nombre_sel_limpio = embalse_sel.upper().strip()
                            homologacion_xm = {
                                "GUATAPÉ (EL PEÑOL)": "PENOL",
                                "GUATAPE (EL PEÑOL)": "PENOL",
                                "HIDROITUANGO": "ITUANGO",
                                "SAN CARLOS": "PUNCHINA",
                                "RIOGRANDE II": "RIOGRANDE2",
                                "JAGUAS": "SAN LORENZO",
                                "PLAYAS": "PLAYAS",
                                "PORCE II": "PORCE II",
                                "PORCE III": "PORCE III",
                                "MIRAFLORES": "MIRAFLORES",
                                "TRONERAS": "TRONERAS"
                            }
                            
                            nombre_buscar = homologacion_xm.get(nombre_sel_limpio, nombre_sel_limpio)
                            df_filtrado = df_xm[df_xm[col_name].str.strip().str.upper() == nombre_buscar].copy()
                            if df_filtrado.empty:
                                df_filtrado = df_xm[df_xm[col_name].str.contains(nombre_buscar, na=False, case=False)].copy()
                            
                            if not df_filtrado.empty:
                                df_filtrado[col_date] = pd.to_datetime(df_filtrado[col_date])
                                df_filtrado = df_filtrado.sort_values(col_date)
                                
                                # 🚀 CÁLCULOS CAV (Sincronización Total de Escalas a Metros Cúbicos)
                                fila_tech = df_embalses[df_embalses['Embalse'] == embalse_sel].iloc[0]
                                v_max_m3 = float(fila_tech.get('Volumen Máximo (Mm³)', 0)) * 1_000_000
                                cota_max = float(fila_tech.get('Altura Promedio Cota Máx (msnm)', 1))
                                cota_min = float(fila_tech.get('Nivel Mínimo Operación / Regla Segura (msnm)', 0))
                                
                                # Polinomio CAV V(z) = alfa * z^3
                                coef_alfa_xm = v_max_m3 / (cota_max**3) if cota_max > 0 else 0
                                vol_regla_segura = coef_alfa_xm * (cota_min**3)
                                
                                # Extracción inteligente de la Cota de Captación desde el texto del Excel
                                cota_cap, vol_captacion = None, None
                                raw_cap = str(fila_tech.get('Altura / Cota de Captación (msnm o Niveles)', ''))
                                match_cap = re.search(r'\d+(\.\d+)?', raw_cap)
                                if match_cap:
                                    val_num = float(match_cap.group())
                                    if val_num > 200: # Ignorar si son solo metros de profundidad
                                        cota_cap = val_num
                                        vol_captacion = coef_alfa_xm * (cota_cap**3)

                                # Sincronizar curva XM (Energía) a Volumen Total (m³)
                                vol_actual_total = coef_alfa_xm * (cota_actual**3)
                                vol_actual_util = vol_actual_total - vol_regla_segura
                                ultimo_vol_xm = float(df_filtrado[col_value].iloc[-1])
                                
                                # Factor de conversión para unificar las unidades
                                if ultimo_vol_xm > 0 and vol_actual_util > 0:
                                    factor = vol_actual_util / ultimo_vol_xm
                                else:
                                    v_util_m3 = float(fila_tech.get('Volumen Útil (Mm³)', 10)) * 1_000_000
                                    max_xm = float(df_filtrado[col_value].max())
                                    factor = (v_util_m3 / max_xm) if max_xm > 0 else 1.0
                                
                                df_filtrado['Vol_Total_m3'] = vol_regla_segura + (df_filtrado[col_value] * factor)
                                
                                # Calcular la Cota inversa a partir del Volumen (CAV)
                                df_filtrado['Cota_m'] = (df_filtrado['Vol_Total_m3'] / coef_alfa_xm) ** (1/3) if coef_alfa_xm > 0 else 0
                                
                                # Renderizar Gráfico con Doble Eje (Subplots)
                                from plotly.subplots import make_subplots
                                fig_xm = make_subplots(specs=[[{"secondary_y": True}]])
                                
                                # Trazo 1: Volumen (Eje Y Primario - Izquierda)
                                fig_xm.add_trace(
                                    go.Scatter(x=df_filtrado[col_date], y=df_filtrado['Vol_Total_m3'], 
                                               fill='tozeroy', name='Volumen (m³)',
                                               line=dict(color='#3498db', width=3), fillcolor='rgba(52, 152, 219, 0.2)'),
                                    secondary_y=False
                                )
                                
                                # Trazo 2: Cota (Eje Y Secundario - Derecha)
                                fig_xm.add_trace(
                                    go.Scatter(x=df_filtrado[col_date], y=df_filtrado['Cota_m'], 
                                               name='Cota (msnm)',
                                               line=dict(color='#2ecc71', width=2, dash='dot')),
                                    secondary_y=True
                                )
                                
                                # Configuración de Ejes y Leyendas
                                fig_xm.update_layout(
                                    title=f"Evolución del Volumen y Cota Operativa: {embalse_sel}",
                                    height=450, margin=dict(t=40, b=0, l=0, r=0),
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                                )
                                fig_xm.update_yaxes(title_text="Volumen Calculado (m³)", secondary_y=False)
                                fig_xm.update_yaxes(title_text="Cota Equivalente (msnm)", secondary_y=True)
                                
                                # Dibujar Líneas de Referencia (Alineadas al Eje Primario/Secundario)
                                if vol_regla_segura > 0:
                                    fig_xm.add_hline(y=vol_regla_segura, line_dash="dash", line_color="#e74c3c", 
                                                     annotation_text=f"Regla Segura", 
                                                     annotation_position="bottom right", secondary_y=False)
                                    fig_xm.add_hline(y=cota_min, line_color="rgba(0,0,0,0)", secondary_y=True) # Sincronizador de eje
                                if vol_captacion is not None:
                                    fig_xm.add_hline(y=vol_captacion, line_dash="dot", line_color="#f39c12", 
                                                     annotation_text=f"Captación", 
                                                     annotation_position="top left", secondary_y=False)

                                st.plotly_chart(fig_xm, use_container_width=True)
                                
                                ultimo_vol_final = df_filtrado['Vol_Total_m3'].iloc[-1]
                                ultima_fecha = df_filtrado[col_date].iloc[-1].strftime('%Y-%m-%d')
                                st.success(f"✅ ¡Sincronización Exitosa! Volumen Total proyectado al {ultima_fecha}: **{ultimo_vol_final/1e6:,.1f} Millones de m³**.")
                                
                                # 📋 Ficha Técnica Oficial (6 Columnas)
                                st.markdown("---")
                                st.markdown(f"#### 📋 Ficha Técnica Oficial: {embalse_sel}")
                                
                                f1, f2, f3, f4, f5, f6 = st.columns(6)
                                f1.metric("📐 Área Máxima", f"{float(fila_tech.get('Área Máxima (ha)', 0)):,.0f} ha")
                                f2.metric("📉 Var. Espejo", f"{float(fila_tech.get('Variación Espejo (ha)', 0)):,.0f} ha")
                                f3.metric("📦 Vol. Máx Total", f"{float(fila_tech.get('Volumen Máximo (Mm³)', 0)):,.1f} Mm³")
                                f4.metric("⚓ Mín. Operativo", f"{cota_min:,.0f} msnm")
                                f5.metric("📏 Prof. Máxima", f"{float(fila_tech.get('Profundidad Máxima (m)', 0)):,.1f} m")
                                
                                captacion_txt = str(fila_tech.get('Lugar de Captación', 'N/A'))
                                if captacion_txt.lower() == 'nan': captacion_txt = 'N/A'
                                f6.metric("🚰 Estructura", captacion_txt[:25] + ("..." if len(captacion_txt)>25 else ""))

                            else:
                                st.warning(f"⚠️ No se encontraron registros bajo el identificador '{nombre_buscar}'.")
                        else:
                            st.error("No se pudo interpretar el formato de XM.")
                    else:
                        st.error(f"El servidor XM no devolvió datos para la métrica.")
                        
                except Exception as e:
                    st.error(f"❌ Error de conexión o procesamiento: {e}")

# -----------------------------------------
# PESTAÑA 6: Explorador Satelital
# -----------------------------------------
with tab6:
    st.header("🗺️ Explorador Satelital y Base Batimétrica")
    st.markdown("Visualización en vivo del anillo de embalses de Antioquia. Usa el ratón para explorar.")
    
    col_mapa, col_datos = st.columns([1.3, 1])
    with col_mapa:
        import folium
        from folium import plugins
        
        # Centroide en Antioquia
        m = folium.Map(location=[6.5, -75.3], zoom_start=9)
        
        # 🚀 Añadir Botón de Fullscreen
        plugins.Fullscreen(
            position='topright', 
            title='Expandir Mapa', 
            title_cancel='Salir Pantalla Completa', 
            force_separate_button=True
        ).add_to(m)
        
        # 1. Mapa Base: Satélite Esri
        tile_url = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        folium.TileLayer(
            tiles=tile_url,
            attr='Esri',
            name='Satélite Esri',
            overlay=False,
            control=True
        ).add_to(m)
        
        # 2. Mapa Base: OpenStreetMap
        folium.TileLayer('OpenStreetMap', name='Open Street Map', overlay=False, control=True).add_to(m)
        
        # 3. Capas GeoJSON Externas (Supabase)
        urls_geojson = {
            "Predios Ejecutados": "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/PrediosEjecutados.geojson",
            "Antioquia": "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/Antioquia.geojson",
            "Territorio Maestro": "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson"
        }
        
        # Asignamos colores distintos a cada capa para diferenciarlas
        colores_geo = {"Predios Ejecutados": "#f1c40f", "Antioquia": "#9b59b6", "Territorio Maestro": "#e74c3c"}
        
        for nombre_capa, url_g in urls_geojson.items():
            try:
                folium.GeoJson(
                    url_g,
                    name=nombre_capa,
                    style_function=lambda feature, color=colores_geo[nombre_capa]: {
                        'fillColor': color,
                        'color': color,
                        'weight': 2,
                        'fillOpacity': 0.15
                    },
                    show=False # Inician apagadas por defecto
                ).add_to(m)
            except Exception as e:
                pass # Si algún GeoJSON falla, el mapa continúa cargando normalmente
        
        # Colocar marcadores con nombres PERMANENTES si la base de datos existe
        if not df_embalses.empty:
            for _, row in df_embalses.iterrows():
                nombre = row['Embalse']
                if nombre in coords_embalses:
                    lat, lon = coords_embalses[nombre]
                    vol = row.get('Volumen Máximo (Mm³)', 'N/A')
                    area = row.get('Área Máxima (ha)', 'N/A')
                    
                    html_popup = f"<b>{nombre}</b><br>Volumen: {vol} Mm³<br>Área: {area} ha"
                    
                    # Tooltip con permanent=True y estilos CSS para las etiquetas
                    folium.Marker(
                        [lat, lon], 
                        popup=folium.Popup(html_popup, max_width=250),
                        tooltip=folium.Tooltip(
                            nombre, 
                            permanent=True, 
                            direction='right', 
                            style="font-size: 11px; font-weight: bold; background-color: rgba(255,255,255,0.8); border: none; padding: 2px 4px; border-radius: 4px;"
                        ),
                        icon=folium.Icon(color='blue', icon='tint')
                    ).add_to(m)
                    
        # Agregamos el Controlador de Capas (menú flotante en el mapa)
        folium.LayerControl(position='topright', collapsed=True).add_to(m)

        # 🔥 FIX: Renderizado nativo HTML a prueba de fallos
        import streamlit.components.v1 as components
        components.html(m._repr_html_(), height=500)

    with col_datos:
        if not df_embalses.empty:
            # Ajustamos la altura para que coincida con el mapa
            st.dataframe(df_embalses.astype(str), use_container_width=True, hide_index=True, height=500)
        else:
            st.warning("⚠️ Base de datos maestra no encontrada.")