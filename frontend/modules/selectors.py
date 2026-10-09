# frontend/modules/selectors.py

import streamlit as st
import geopandas as gpd
import pandas as pd
from sqlalchemy import text
from shapely.geometry import box
import json
import time
import unicodedata
import requests

from modules import db_manager
from modules.config import Config

# ====================================================================
# --- 1. REPARADOR DE TILDES (MOJIBAKE) ---
# ====================================================================
def decodificar_tildes(texto):
    """Corrige errores de codificación en BD como 'Abriaquã' -> 'Abriaquí'"""
    if not isinstance(texto, str): return texto
    try:
        if 'Ã' in texto or 'ã' in texto or '\x8d' in texto:
            return texto.encode('latin1').decode('utf-8')
    except: pass
    return texto

def renderizar_telemetria_aleph():
    """Panel de control universal que monitorea las variables de estado en tiempo real."""
    import streamlit as st
    import datetime
    
    st.sidebar.markdown("### 🧠 Telemetría del Aleph")
    
    mes_actual = datetime.datetime.now().month
    trimestres = {
        1: "DEF", 2: "EFM", 3: "FMA", 4: "MAM", 5: "AMJ", 6: "MJJ",
        7: "JJA", 8: "JAS", 9: "ASO", 10: "SON", 11: "OND", 12: "NDE"
    }
    trimestre_str = trimestres.get(mes_actual, "JAS")
        
    with st.sidebar.expander("🌦️ Pulso Climático Global", expanded=False):
        if 'aleph_iri_nino' not in st.session_state:
            try:
                from modules.climate_api import get_iri_enso_forecast, get_live_oni_data, get_live_soi_data, get_live_iod_data
                
                df_enso, metadatos_enso = get_iri_enso_forecast()
                
                if df_enso is not None and not df_enso.empty:
                    fila_actual = df_enso.iloc[0]
                    p_nina = float(fila_actual.get('La Niña', 0))
                    p_nino = float(fila_actual.get('El Niño', 0))
                    p_neutro = float(fila_actual.get('Neutral', 0))
                    trim_txt = str(fila_actual.get('Trimestre', 'Actual'))
                    fuente = metadatos_enso.get("fuente", "Conexión")
                    
                    if p_nina > 50: estado = "Niña 🌧️"
                    elif p_nino > 50: estado = "Niño ☀️"
                    else: estado = "Neutro ⚖️"
                    
                    st.session_state['enso_fase'] = estado
                    st.session_state['aleph_iri_nino'] = int(p_nino)
                    st.session_state['aleph_iri_neutro'] = int(p_neutro)
                    st.session_state['aleph_iri_nina'] = int(p_nina)
                    st.session_state['aleph_iri_trimestre'] = trim_txt
                    st.session_state['aleph_iri_tendencia'] = f"Sincronizado: {fuente} 📡"
                    
                    if len(df_enso) > 1:
                        fila_sig = df_enso.iloc[1]
                        st.session_state['aleph_iri_nino_sig'] = int(float(fila_sig.get('El Niño', 0)))
                        st.session_state['aleph_iri_neutro_sig'] = int(float(fila_sig.get('Neutral', 0)))
                        st.session_state['aleph_iri_nina_sig'] = int(float(fila_sig.get('La Niña', 0)))
                        st.session_state['aleph_iri_trimestre_sig'] = str(fila_sig.get('Trimestre', 'Siguiente'))
                
                oni_res = get_live_oni_data()
                df_oni, delta_oni = oni_res if oni_res else (None, 0.0)
                
                soi_res = get_live_soi_data()
                df_soi, delta_soi = soi_res if soi_res else (None, 0.0)
                
                iod_res = get_live_iod_data()
                df_iod, delta_iod = iod_res if iod_res else (None, 0.0)
                
                if df_oni is not None and not df_oni.empty:
                    oni_actual = df_oni.iloc[-1]
                    st.session_state['aleph_oni_val'] = oni_actual['anomalia_oni']
                    st.session_state['aleph_oni_delta'] = delta_oni
                    st.session_state['aleph_enso_categoria'] = oni_actual.get('categoria', '')
                if df_soi is not None and not df_soi.empty:
                    st.session_state['aleph_soi_val'] = df_soi['soi'].iloc[-1]
                    st.session_state['aleph_soi_delta'] = delta_soi
                if df_iod is not None and not df_iod.empty:
                    st.session_state['aleph_iod_val'] = df_iod['iod'].iloc[-1]
                    st.session_state['aleph_iod_delta'] = delta_iod
                    
            except Exception as e:
                st.session_state['aleph_iri_tendencia'] = f"Error conectando: {str(e)}"
                
        # --- RENDERIZADO VISUAL DEL ESTADO GLOBAL ---
        st.caption("📡 **Plumas de Probabilidad NOAA (En Vivo)**")
        
        enso_global = st.session_state.get('enso_fase', 'Desconocido ⚠️')
        enso_cat = st.session_state.get('aleph_enso_categoria', '')
        
        # 🚀 FIX VISUAL: Alerta Crítica para "Súper Fuerte"
        if "Súper Fuerte" in enso_cat:
            cat_str = f"🔥 (¡{enso_cat}!)"
            st.error(f"⚠️ ALERTA CLIMÁTICA: Anomalía ONI clasificada como {enso_cat}. Se esperan impactos hidrológicos extremos.")
        else:
            cat_str = f"({enso_cat})" if enso_cat and enso_cat != "Normal" else ""
            
        color_enso = "#3498db" if "Niña" in enso_global else "#e74c3c" if "Niño" in enso_global else "#f39c12" if "Desconocido" in enso_global else "#2ecc71"
        
        # Etiqueta HTML consolidada
        etiqueta_clima = f"<span style='color:{color_enso}; font-size:1.0em'><b>🌍 Clima ENSO: {enso_global} {cat_str}</b></span>"
        
        # --- PLUMA ACTUAL ---
        p_nino = st.session_state.get('aleph_iri_nino', 0)
        p_neutro = st.session_state.get('aleph_iri_neutro', 0)
        p_nina = st.session_state.get('aleph_iri_nina', 0)
        trimestre = st.session_state.get('aleph_iri_trimestre', 'Actual')
        
        if (p_nino + p_neutro + p_nina) > 0:
            st.markdown(f"**Trimestre {trimestre}:** &nbsp; {etiqueta_clima}", unsafe_allow_html=True)
            st.progress(p_nino / 100.0 if p_nino > 1 else p_nino, text=f"☀️ El Niño ({p_nino}%)")
            st.progress(p_neutro / 100.0 if p_neutro > 1 else p_neutro, text=f"⚖️ Neutro ({p_neutro}%)")
            st.progress(p_nina / 100.0 if p_nina > 1 else p_nina, text=f"🌧️ La Niña ({p_nina}%)")
            
        # --- PLUMA SIGUIENTE ---
        trim_sig = st.session_state.get('aleph_iri_trimestre_sig', '')
        if trim_sig:
            p_nino_sig = st.session_state.get('aleph_iri_nino_sig', 0)
            p_neutro_sig = st.session_state.get('aleph_iri_neutro_sig', 0)
            p_nina_sig = st.session_state.get('aleph_iri_nina_sig', 0)
            
            st.markdown(f"<br>**Próximo Trimestre ({trim_sig}):** &nbsp; {etiqueta_clima}", unsafe_allow_html=True)
            st.progress(p_nino_sig / 100.0 if p_nino_sig > 1 else p_nino_sig, text=f"☀️ El Niño ({p_nino_sig}%)")
            st.progress(p_neutro_sig / 100.0 if p_neutro_sig > 1 else p_neutro_sig, text=f"⚖️ Neutro ({p_neutro_sig}%)")
            st.progress(p_nina_sig / 100.0 if p_nina_sig > 1 else p_nina_sig, text=f"🌧️ La Niña ({p_nina_sig}%)")
            
        st.markdown("📊 **Índices Climáticos Actuales**")
        col_oni, col_soi, col_iod = st.columns(3)
        
        oni_val = st.session_state.get('aleph_oni_val', 'N/A')
        soi_val = st.session_state.get('aleph_soi_val', 'N/A')
        iod_val = st.session_state.get('aleph_iod_val', 'N/A')
        
        oni_d = st.session_state.get('aleph_oni_delta', 0.0)
        soi_d = st.session_state.get('aleph_soi_delta', 0.0)
        iod_d = st.session_state.get('aleph_iod_delta', 0.0)
        
        col_oni.metric("ONI", f"{oni_val:.2f}" if isinstance(oni_val, float) else oni_val, f"{oni_d:+.2f}")
        col_soi.metric("SOI", f"{soi_val:.2f}" if isinstance(soi_val, float) else soi_val, f"{soi_d:+.2f}")
        col_iod.metric("IOD", f"{iod_val:.2f}" if isinstance(iod_val, float) else iod_val, f"{iod_d:+.2f}")
        
        tendencia = st.session_state.get('aleph_iri_tendencia', '')
        if tendencia: st.caption(f"📈 {tendencia}")

# ====================================================================
# 📂 NAVEGACIÓN GLOBAL Y EL ALEPH V2.5 (ESCALAS AVANZADAS RESTAURADAS)
# ====================================================================
def renderizar_menu_navegacion(pagina_actual):
    st.sidebar.markdown("### 🧭 Navegación | Actual:")
    st.sidebar.info(f"📍 {pagina_actual}")
    
    with st.sidebar.expander("📂 Menú de Páginas", expanded=False):
        st.page_link("app.py", label="Inicio", icon="🏠")
        st.page_link("pages/01_🌦️_Clima_e_Hidrologia.py", label="Clima e Hidrología", icon="🌦️")
        st.page_link("pages/02_💧_Aguas_Subterraneas.py", label="Aguas Subterráneas", icon="💧")
        st.page_link("pages/03_🗺️_Isoyetas_HD.py", label="Isoyetas HD", icon="🗺️")
        st.page_link("pages/04_🍃_Biodiversidad.py", label="Biodiversidad", icon="🌱")
        st.page_link("pages/05_🏔️_Geomorfologia.py", label="Geomorfología", icon="⛰️")
        st.page_link("pages/06_🐄_Modelo_Pecuario.py", label="Modelo Pecuario", icon="🐄")
        st.page_link("pages/06_📈_Modelo_Demografico.py", label="Modelo Demográfico", icon="👥")
        st.page_link("pages/07_☀️_Evaporacion.py", label="Evaporación", icon="☀️")
        st.page_link("pages/07_💧_Calidad_y_Vertimientos.py", label="Calidad y Vertimientos", icon="🧪")
        st.page_link("pages/08_🔗_Sistemas_Hidricos_Territoriales.py", label="Sistemas Hídricos", icon="🌊")
        st.page_link("pages/09_🧠_Toma_de_Decisiones.py", label="Toma de Decisiones", icon="🧠") 
        st.page_link("pages/10_⚖️_Simulador_Integral.py", label="Simulador Integral", icon="⚖️")
        st.page_link("pages/10_👑_Panel_Administracion.py", label="Panel Administración", icon="⚙️")
        st.page_link("pages/11_⚙️_Generador.py", label="Generador", icon="✨")
        st.page_link("pages/12_📚_Ayuda_y_Docs.py", label="Ayuda y Docs", icon="📚")
        st.page_link("pages/13_🕵️_Detective.py", label="Detective", icon="🕵️")
        st.page_link("pages/14_🌍_Satelite_Terrestre.py", label="Satélite Terrestre", icon="🌍")
        st.page_link("pages/17_🛰️_Radar_Meteorologico.py", label="Radar Meteorológico", icon="🛰️")
        st.page_link("pages/15_⚖️_Escenarios_WEAP.py", label="Escenarios WEAP", icon="⚖️")
        st.page_link("pages/16_🏭_Inyeccion_RURH.py", label="Inyección RURH", icon="🏭")
        
    
    # -------------------------------------------------------------
    # 👁️ EL ALEPH (Selector Universal Multiescala Híbrido V5.2)
    # -------------------------------------------------------------
    with st.sidebar.expander("👁️ El Aleph (Selector Universal)", expanded=True):
        LISTA_DEPTOS = ["ANTIOQUIA"]
        LISTA_MPIOS_ANT = ["ABEJORRAL", "ABRIAQUI", "ALEJANDRIA", "AMAGA", "AMALFI", "ANDES", "ANGELOPOLIS", "ANGOSTURA", "ANORI", "ANZA", "APARTADO", "ARBOLETES", "ARGELIA", "ARMENIA", "BARBOSA", "BELLO", "BELMIRA", "BETANIA", "BETULIA", "BRICEÑO", "BURITICA", "CACERES", "CAICEDO", "CALDAS", "CAMPAMENTO", "CAÑASGORDAS", "CARACOLI", "CARAMANTA", "CAREPA", "CARMEN DE VIBORAL", "CAROLINA DEL PRINCIPE", "CAUCASIA", "CHIGORODO", "CISNEROS", "CIUDAD BOLIVAR", "COCORNA", "CONCEPCION", "CONCORDIA", "COPACABANA", "DABEIBA", "DONMATIAS", "EBEJICO", "EL BAGRE", "EL PEÑOL", "EL RETIRO", "ENTRERRIOS", "ENVIGADO", "FREDONIA", "FRONTINO", "GIRALDO", "GIRARDOTA", "GOMEZ PLATA", "GRANADA", "GUADALUPE", "GUARNE", "GUATAPE", "HELICONIA", "HISPANIA", "ITAGUI", "ITUANGO", "JARDIN", "JERICO", "LA CEJA", "LA ESTRELLA", "LA PINTADA", "LA UNION", "LIBORINA", "MACEO", "MARINILLA", "MONTEBELLO", "MURINDO", "MUTATA", "NARIÑO", "NECHI", "NECOCLI", "OLAYA", "PEQUE", "PUEBLO RICO", "PUERTO BERRIO", "PUERTO NARE", "PUERTO TRIUNFO", "REMEDIOS", "RIONEGRO", "SABANALARGA", "SABANETA", "SALGAR", "SAN ANDRES DE CUERQUIA", "SAN CARLOS", "SAN FRANCISCO", "SAN JERONIMO", "SAN JOSE DE LA MONTAÑA", "SAN JUAN DE URABA", "SAN LUIS", "SAN PEDRO DE LOS MILAGROS", "SAN PEDRO DE URABA", "SAN RAFAEL", "SAN ROQUE", "SAN VICENTE FERRER", "SANTA BARBARA", "SANTA ROSA DE OSOS", "SANTAFE DE ANTIOQUIA", "SANTUARIO", "SANTO DOMINGO", "SEGOVIA", "SONSON", "SOPETRAN", "TAMESIS", "TARAZA", "TARSO", "TITIRIBI", "TOLEDO", "TURBO", "URAMITA", "URRAO", "VALDIVIA", "VALPARAISO", "VEGACHI", "VENECIA", "VIGIA DEL FUERTE", "YALI", "YARUMAL", "YOLOMBO", "YONDO", "ZARAGOZA"]
        LISTA_SUBREGIONES = ["Bajo Cauca", "Magdalena Medio", "Nordeste", "Norte", "Occidente", "Oriente", "Suroeste", "Urabá", "Valle De Aburrá"]
        LISTA_CARS = ["AMVA", "CORANTIOQUIA", "CORNARE", "CORPOURABA"]

        # 3. Catálogo Cuencas (Sin cambios)
        @st.cache_data(ttl=3600)
        def obtener_catalogo_cuencas():
            import pandas as pd
            import os
            import re
            import unicodedata
            ruta_exacta = os.path.join(os.path.dirname(__file__), '..', 'data', 'Cuencas_SP.xlsx')
            df_c = pd.DataFrame()
            if os.path.exists(ruta_exacta):
                try:
                    df_c = pd.read_excel(ruta_exacta, engine='openpyxl')
                    df_c.columns = [str(c).lower().strip() for c in df_c.columns]
                    def sanar_texto(t):
                        if pd.isna(t): return ""
                        txt = str(t)
                        mojis = {"├¡": "í", "├▒": "ñ", "├│": "ó", "├í": "á", "├®": "é", "├║": "ú", 
                                 "├ü": "Á", "├ë": "É", "├\x8d": "Í", "├ô": "Ó", "├Ü": "Ú", "├æ": "Ñ", "├⌐": "é"}
                        for corrupto, sano in mojis.items(): txt = txt.replace(corrupto, sano)
                        txt = re.sub(r'_x[0-9A-Fa-f]{4}_', '', txt)
                        txt = re.sub(r'(?i)<null>.*', '', txt)
                        txt = txt.replace(' - ()', '').replace('-()', '').strip()
                        return txt if len(txt) > 2 and txt not in ["-", "", "()"] else ""
                    cols_texto = ['nomah', 'nomzh', 'nom_szh', 'nom_nss1', 'nom_nss2', 'nom_nss3']
                    for col in cols_texto:
                        if col in df_c.columns: df_c[col] = df_c[col].apply(sanar_texto)
                except Exception as e: print(f"Error cargando Cuencas: {e}")
            return df_c

        # 1. Comentamos la escala Nacional y reordenamos para que Departamental sea la primera
        niveles = {
        #   "🇨🇴 Nacional": "NACIONAL", # Oculto temporalmente
            "🏛️ Departamental": "DEPARTAMENTAL",
            "🏢 Municipal": "MUNICIPAL",
            "🧩 Regiones (Subregiones)": "REGIONAL",
            "🦅 Autoridades (CARs)": "CAR",
            "💧 Cuencas Hidrográficas": "CUENCA"
        }
        
        # 2. El radio button tomará por defecto el primer elemento (Departamental)
        escala_sel = st.radio("Escala de Análisis:", list(niveles.keys()), key="menu_escala_aleph")
        nivel_backend = niveles[escala_sel]
        
        # 3. Inicializamos la variable vacía para que se defina dentro del enrutador
        territorio_final = ""
        depto_filtro = "ANTIOQUIA"  # 🛟 FIX: Salvavidas para evitar el NameError
        
        # --- Enrutador de Escalas ---
        if nivel_backend == "DEPARTAMENTAL":
            territorio_final = st.selectbox("Departamento:", LISTA_DEPTOS, index=0, key="menu_depto_aleph")
            st.success(f"Territorio fijado: {territorio_final}")

        elif nivel_backend == "MUNICIPAL":
            lista_municipios = list(LISTA_MPIOS_ANT)
            if "MEDELLIN" not in lista_municipios:
                lista_municipios.append("MEDELLIN")
                lista_municipios.sort()
            idx_mpio = lista_municipios.index("MEDELLIN") if "MEDELLIN" in lista_municipios else 0
            territorio_final = st.selectbox("Municipio:", lista_municipios, index=idx_mpio, key="menu_muni_aleph")
            st.success(f"Territorio fijado: {territorio_final}")
            
        elif nivel_backend == "REGIONAL":
            territorio_final = st.selectbox("Subregión:", sorted(LISTA_SUBREGIONES), key="menu_reg_aleph")

        elif nivel_backend == "CAR":
            territorio_final = st.selectbox("Autoridad Ambiental:", sorted(LISTA_CARS), key="menu_car_aleph")
            
        elif nivel_backend == "CUENCA":
            df_c = obtener_catalogo_cuencas()
            if not df_c.empty:
                nombres_niveles = {
                    "AH": "🌊 AH - Área Hidrográfica",
                    "ZH": "💧 ZH - Zona Hidrográfica",
                    "SZH": "🌿 SZH - Subzona Hidrológica",
                    "NSS1": "🍃 NSS1 - Río Tributario", 
                    "NSS2": "🌱 NSS2 - Microcuenca Local", 
                    "NSS3": "💧 NSS3 - Quebradas Menores"
                }
                nivel_display = st.selectbox("Resolución Hídrica:", list(nombres_niveles.values()), index=5, key="menu_res_cuenca")
                nivel_cuenca = next(key for key, value in nombres_niveles.items() if value == nivel_display)
                
                if nivel_cuenca in ["AH", "ZH", "SZH"]:
                    col_obj = {"AH": "nomah", "ZH": "nomzh", "SZH": "nom_szh"}[nivel_cuenca]
                    if col_obj in df_c.columns:
                        opciones = sorted([str(x).strip() for x in df_c[col_obj].dropna().unique() if str(x).strip() != ''])
                        territorio_final = st.selectbox(f"Cuenca Exacta ({nivel_cuenca}):", opciones, key="menu_cuenca_aleph")
                        st.session_state['aleph_codigo_cuenca'] = territorio_final
                    else:
                        st.error("Nivel no disponible en el archivo.")
                        territorio_final = "SIN DATOS"
                        st.session_state['aleph_codigo_cuenca'] = "N/A"
                else: 
                    col_obj = {"NSS1": "nom_nss1", "NSS2": "nom_nss2", "NSS3": "nom_nss3"}[nivel_cuenca]
                    col_cod = {"NSS1": "nss1", "NSS2": "nss2", "NSS3": "nss3"}[nivel_cuenca]
                    if col_obj in df_c.columns and col_cod in df_c.columns:
                        df_c_filtro = df_c.dropna(subset=[col_obj]).copy()
                        df_c_filtro = df_c_filtro[df_c_filtro[col_obj].astype(str).str.strip() != ""]
                        import re
                        def limpiar_codigo(cod):
                            c = str(cod)
                            c = re.sub(r'(_x[0-9A-Fa-f]{4}_)+', '', c)
                            c = c.replace('_', '').strip()
                            return re.sub(r'\.0$', '', c)
                        df_c_filtro['codigo_limpio'] = df_c_filtro[col_cod].apply(limpiar_codigo)
                        df_c_filtro['Llave_Visual'] = df_c_filtro[col_obj].astype(str).str.strip() + " - (" + df_c_filtro['codigo_limpio'] + ")"
                        opciones_cuencas = sorted([str(x) for x in df_c_filtro['Llave_Visual'].unique() if str(x) != ' - ()' and not str(x).startswith(' -')])
                        
                        seleccion = st.selectbox(f"Cuenca Exacta ({nivel_cuenca}):", opciones_cuencas, key="menu_cuenca_aleph")
                        territorio_final = seleccion
                        
                        if " - (" in seleccion:
                            nombre_puro = seleccion.split(" - (")[0].strip()
                            codigo_puro = seleccion.split(" - (")[1].replace(")", "").strip()
                            if codigo_puro == "":
                                st.session_state['aleph_codigo_cuenca'] = nombre_puro
                            else:
                                st.session_state['aleph_codigo_cuenca'] = codigo_puro
                        else:
                            st.session_state['aleph_codigo_cuenca'] = seleccion.strip()
                    else:
                        st.error("Error en formato de columnas.")
                        territorio_final = "SIN DATOS"
                        st.session_state['aleph_codigo_cuenca'] = "N/A"
            else:
                st.error("Catálogo de Cuencas no encontrado.")
                territorio_final = "SIN DATOS"
                st.session_state['aleph_codigo_cuenca'] = "N/A"

    # =============================================================
    # 🔥 INYECCIÓN GLOBAL (EL PROTOCOLO ALEPH - ESTADO CENTRALIZADO)
    # =============================================================
    lugar_original = str(territorio_final).strip()
    lugar_upper = lugar_original.upper()
    nivel_upper = str(nivel_backend).upper().strip()

    import unicodedata
    import re

    # 1. PURIFICACIÓN BÁSICA (Quitar tildes y sufijos GIS)
    lugar_limpio = ''.join(c for c in unicodedata.normalize('NFD', lugar_upper) if unicodedata.category(c) != 'Mn')
    lugar_puro = lugar_limpio.split(" - (")[0].strip()
    lugar_puro = re.sub(r'(?i)\s*-?\s*NSS\d*\b', '', lugar_puro).strip()

    # 2. DICCIONARIO UNIVERSAL DE RESCATE (Homologación oficial DANE/ICA)
    dic_rescate = {
        "PUEBLO RICO": "PUEBLORRICO", "SAN VICENTE": "SAN VICENTE FERRER",
        "EL PENOL": "PENOL", "EL RETIRO": "RETIRO", "CAROLINA DEL PRINCIPE": "CAROLINA", 
        "SAN ANDRES DE CUERQUIA": "SAN ANDRES", "SAN JOSE DE LA MONTANA": "SAN JOSE", 
        "SAN PEDRO DE LOS MILAGROS": "SAN PEDRO", "AMVA": "VALLE DE ABURRA"
    }
    lugar_maestro = dic_rescate.get(lugar_puro, lugar_puro)

    # 3. FORJA DE LLAVE PECUARIA UNIVERSAL (Formato estricto: NIVEL_NOMBRE_TOTAL)
    # Agrupamos todas las resoluciones hídricas bajo la etiqueta maestra "CUENCA"
    nivel_pecuario = "CUENCA" if nivel_upper in ["AH", "ZH", "SZH", "NSS1", "NSS2", "NSS3", "CUENCA"] else nivel_upper
    
    # La llave no admite espacios ni puntos, solo guiones bajos
    texto_llave = re.sub(r'[^A-Z0-9]', '_', lugar_maestro)
    texto_llave = re.sub(r'_+', '_', texto_llave).strip('_')
    llave_pecuaria_universal = f"{nivel_pecuario}_{texto_llave}_TOTAL"

    # 4. FORJA DE PARÁMETROS DEMOGRÁFICOS (DANE)
    nivel_demo = "REGIONAL" if lugar_puro == "AMVA" else nivel_pecuario

    # 5. 🧠 INYECCIÓN AL CEREBRO CENTRAL (Disponibles para TODO el simulador)
    st.session_state['aleph_lugar'] = lugar_original             # Ej: Bzlo. Canime - (2317-03-01-04)
    st.session_state['aleph_escala'] = nivel_backend             # Ej: NSS3, MUNICIPAL
    
    st.session_state['aleph_lugar_puro'] = lugar_puro            # Ej: BZLO. CANIME
    st.session_state['aleph_lugar_maestro'] = lugar_maestro      # Ej: VALLE DE ABURRA
    st.session_state['aleph_nivel_demo'] = nivel_demo            # Ej: CUENCA, REGIONAL
    st.session_state['aleph_llave_pecuaria'] = llave_pecuaria_universal # Ej: CUENCA_BZLO_CANIME_TOTAL
    
    # Jinete de Retrocompatibilidad V1 (Garantiza que Biodiversidad y otros no fallen)
    st.session_state['zona_activa_global'] = lugar_limpio
    st.session_state['nivel_activo_global'] = nivel_backend

    # === LA CURA GLOBAL: PUENTE CARTOGRÁFICO PARA ANTIOQUIA ===
    if str(nivel_backend).strip().lower() == "departamental" and "antioquia" in str(lugar_original).lower():
        import geopandas as gpd
        try:
            url_ant = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/Antioquia.geojson"
            gdf_antioquia = gpd.read_file(url_ant)
            gdf_antioquia['nombre_homologado'] = 'ANTIOQUIA'
            st.session_state['aleph_poligono'] = gdf_antioquia
        except Exception as e:
            pass
    else:
        # 🧹 PURGA DE FANTASMAS: Si la escala cambia a Cuenca o Municipio,
        # vaciamos el mapa global para obligar a las páginas a extraer la geometría exacta.
        if 'aleph_poligono' in st.session_state:
            st.session_state['aleph_poligono'] = None
    # ==========================================================

    renderizar_telemetria_aleph()
    
    # 🧹 BOTÓN DE PURGA MOVIDO A LA PARTE INFERIOR ABSOLUTA
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if st.sidebar.button("🧹 Purgar Memoria y Caché", width="stretch", key="btn_purga_global_aleph"):
        st.session_state.clear()
        st.cache_data.clear()
        st.rerun()

# ====================================================================
# ☁️ CONEXIÓN A SUPABASE Y DEMÁS FUNCIONES ORIGINALES
# ====================================================================
@st.cache_resource
def get_supabase_client():
    try:
        from supabase import create_client
        url_sb = st.secrets.get("SUPABASE_URL") or st.secrets.get("supabase", {}).get("SUPABASE_URL") or st.secrets.get("supabase", {}).get("url")
        key_sb = st.secrets.get("SUPABASE_KEY") or st.secrets.get("supabase", {}).get("SUPABASE_KEY") or st.secrets.get("supabase", {}).get("key")
        if url_sb and key_sb: return create_client(url_sb, key_sb)
        else: return "NO_SECRETS"
    except ImportError: return "NO_LIBRARY"
    except Exception as e: return str(e)

def renderizar_gestor_escenarios(lugar):
    with st.sidebar.expander("📸 Gestor de Escenarios", expanded=False):
        st.markdown(f"**Territorio:** `{lugar}`")
        engine = db_manager.get_engine()
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS escenarios_sihcli (
                        id SERIAL PRIMARY KEY,
                        territorio TEXT NOT NULL,
                        nombre_escenario TEXT NOT NULL,
                        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        datos JSONB,
                        UNIQUE (territorio, nombre_escenario)
                    )
                """))
        except Exception as e:
            st.error(f"⚠️ Error verificando BD de escenarios: {e}")
            return

        nombre_nuevo = st.text_input("Nombre del Nuevo Escenario:", placeholder="Ej: Plan Resiliencia 2027")
        if st.button("💾 Guardar Escenario Actual", width="stretch"):
            if nombre_nuevo.strip():
                estado_actual = {
                    k: v for k, v in st.session_state.items() 
                    if isinstance(v, (int, float, str, bool, list, dict)) 
                    and not k.startswith("FormSubmitter")
                    and not k.startswith("btn_")
                }
                try:
                    query_insert = text("""
                        INSERT INTO escenarios_sihcli (territorio, nombre_escenario, datos, fecha) 
                        VALUES (:terr, :nom, :datos, CURRENT_TIMESTAMP)
                        ON CONFLICT (territorio, nombre_escenario) 
                        DO UPDATE SET datos = EXCLUDED.datos, fecha = CURRENT_TIMESTAMP
                    """)
                    with engine.begin() as conn:
                        conn.execute(query_insert, {"terr": lugar, "nom": nombre_nuevo.strip(), "datos": json.dumps(estado_actual)})
                    st.success(f"✅ Escenario '{nombre_nuevo}' blindado en Supabase.")
                except Exception as e:
                    st.error(f"❌ Error al guardar en la nube: {e}")
            else:
                st.warning("⚠️ Debes asignar un nombre al escenario.")

        st.markdown("---")
        try:
            query_load = text("SELECT nombre_escenario FROM escenarios_sihcli WHERE territorio = :terr ORDER BY fecha DESC")
            df_escenarios = pd.read_sql(query_load, engine, params={"terr": lugar})
            opciones_guardadas = df_escenarios['nombre_escenario'].tolist() if not df_escenarios.empty else []
        except Exception:
            opciones_guardadas = []

        if opciones_guardadas:
            esc_sel = st.selectbox("📂 Escenarios en la Nube:", opciones_guardadas)
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("🚀 Cargar", width="stretch"):
                    try:
                        q_fetch = text("SELECT datos FROM escenarios_sihcli WHERE territorio = :terr AND nombre_escenario = :nom")
                        with engine.connect() as conn:
                            resultado = conn.execute(q_fetch, {"terr": lugar, "nom": esc_sel}).fetchone()
                            if resultado and resultado[0]:
                                datos_recuperados = resultado[0] if isinstance(resultado[0], dict) else json.loads(resultado[0])
                                for k, v in datos_recuperados.items():
                                    if not k.startswith("btn_") and not k.startswith("FormSubmitter"):
                                        try: st.session_state[k] = v
                                        except Exception: pass
                                st.success(f"Restaurando '{esc_sel}'...")
                                time.sleep(0.5)
                                st.rerun() 
                    except Exception as e:
                        st.error(f"Error restaurando: {e}")
                        
            with col2:
                if st.button("🗑️", help="Eliminar este escenario"):
                    try:
                        q_del = text("DELETE FROM escenarios_sihcli WHERE territorio = :terr AND nombre_escenario = :nom")
                        with engine.begin() as conn: conn.execute(q_del, {"terr": lugar, "nom": esc_sel})
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
        else:
            st.info("Sin escenarios guardados.")

@st.cache_data(show_spinner=False, ttl=86400)
def obtener_matriz_maestra_csv(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.upper()
        return df
    except: return pd.DataFrame()

def render_cabezote_sintesis_body(nombre_zona):
    pob = st.session_state.get('aleph_pob_total', 0)
    bov = st.session_state.get('ica_bovinos_calc_met', 0)
    por = st.session_state.get('ica_porcinos_calc_met', 0)
    ave = st.session_state.get('ica_aves_calc_met', 0)
    
    if nombre_zona and nombre_zona not in ["Sin Selección", "-- Seleccione --", "NINGUNO", ""]:
        if pob > 0 or bov > 0 or por > 0 or ave > 0:
            st.success(f"📌 **SÍNTESIS ACTIVA** | 📍 Territorio: {nombre_zona} \n\n 👥 Humanos: {pob:,} | 🐄 Bov: {bov:,} | 🐖 Porc: {por:,} | 🐔 Aves: {ave:,}")

# ====================================================================
# Funciones Legacy (Mantenidas para compatibilidad interna)
# ====================================================================
def cargar_atributos_cuencas(): return pd.DataFrame()
def cargar_atributos_municipios(): return pd.DataFrame()
def render_selector_espacial(modo_firma="clasica"): return [], "Antioquia", 1500.0, None, "Departamento"