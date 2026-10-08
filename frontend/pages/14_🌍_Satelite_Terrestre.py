# pages/14_🌍_Satelite_Terrestre.py

import os
import sys
import json
import streamlit as st
import ee
import folium
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE PÁGINA (Debe ir primero) ---
st.set_page_config(page_title="Radar Satelital Vivo", page_icon="🛰️", layout="wide")

# --- IMPORTACIÓN DE MÓDULOS (SIDEBAR Y SELECTORES) ---
try:
    from modules import selectors
    from modules.utils import inicializar_torrente_sanguineo
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from modules import selectors
    from modules.utils import inicializar_torrente_sanguineo

# ==========================================
# MENÚ Y SELECTORES TERRITORIALES
# ==========================================
# 1. Recuperamos el menú lateral izquierdo
selectors.renderizar_menu_navegacion("Satélite en Vivo")

try:
    inicializar_torrente_sanguineo()
except Exception:
    pass

st.title("🛰️ Radar Dynamic World (En Vivo)")
st.markdown("Clasificación de coberturas de la tierra en tiempo real mediante Inteligencia Artificial (Sentinel-2 / Google Earth Engine).")

# ==============================================================================
# 🧠 2. SELECTOR ESPACIAL Y CONEXIÓN ALEPH (Topología Estricta para GEE)
# ==============================================================================
try:
    ids_sel_dummy, nombre_zona_raw, alt_ref, gdf_zona_dummy, nivel_jerarquico_raw = selectors.render_selector_espacial()
except Exception as e:
    st.error(f"Error en selector: {e}")
    st.stop()

# 🚀 CONEXIÓN ALEPH
nombre_zona = st.session_state.get('aleph_lugar', nombre_zona_raw)
nivel_jerarquico = st.session_state.get('aleph_escala', nivel_jerarquico_raw)

# Suavizamos la barrera
if not nombre_zona or str(nombre_zona).strip() in ["", "None", "-- Seleccione --"]:
    st.info("👈 Seleccione un Territorio (Cuenca, Municipio o Región) en el menú lateral para iniciar.")
    st.stop()

# 🪂 FUNCIÓN CACHEADA GLOBALMENTE (Para búsquedas estructurales en GEE)
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_territorio_maestro():
    import geopandas as gpd
    import requests, io
    url = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson"
    try:
        res = requests.get(url, timeout=60) 
        if res.status_code == 200:
            gdf = gpd.read_file(io.BytesIO(res.content))
            gdf.columns = [c.lower().strip() for c in gdf.columns]
            return gdf
    except Exception as e:
        print(f"Error descargando TerritorioMaestro: {e}")
    return gpd.GeoDataFrame()

# 🚀 RESCATE ESTRUCTURAL: Usar el caché de memoria viva (Si existe)
gdf_zona = None
if 'aleph_poligono' in st.session_state and st.session_state['aleph_poligono'] is not None and not st.session_state['aleph_poligono'].empty:
    gdf_zona = st.session_state['aleph_poligono']

# 🪂 PARACAÍDAS CARTOGRÁFICO ESTRUCTURAL
if gdf_zona is None or gdf_zona.empty:
    with st.spinner("🪂 Sincronizando topología estricta con Google Earth Engine..."):
        try:
            import geopandas as gpd
            import unicodedata
            import re
            import pandas as pd
            
            def norm_text(t):
                if not isinstance(t, str) or pd.isna(t): return ""
                return unicodedata.normalize('NFKD', t.lower().strip()).encode('ascii', 'ignore').decode('utf-8')

            # 🗺️ DICCIONARIO DE TRADUCCIÓN
            ALIASES_MUNICIPIOS = {
                "el carmen de viboral": "EL CARMEN DE VIBORAL",
                "carmen de viboral": "EL CARMEN DE VIBORAL",
                "el penol": "PEÑOL",
                "penol": "PEÑOL",
                "el retiro": "RETIRO",
                "retiro": "RETIRO",
                "carolina del principe": "CAROLINA",
                "carolina": "CAROLINA",
                "santa fe de antioquia": "Santa Fe De Antioquia",
                "santafe de antioquia": "Santa Fe De Antioquia",
                "pueblo rico": "PUEBLORRICO",
                "pueblorrico": "PUEBLORRICO",
                "san jose de la montana": "SAN JOSE DE LA MONTAÑA",
                "san andres de cuerquia": "SAN ANDRES DE CUERQUIA",
                "san vicente": "SAN VICENTE FERRER",
                "san vicente ferrer": "SAN VICENTE FERRER",
                "ciudad bolivar": "CIUDAD BOLIVAR",
                "bolivar": "CIUDAD BOLIVAR"
            }

            lugar_crudo = str(nombre_zona).replace("CAR: ", "").strip()
            lugar_norm_inicial = norm_text(lugar_crudo)
            
            if lugar_norm_inicial in ALIASES_MUNICIPIOS:
                terr_norm = norm_text(ALIASES_MUNICIPIOS[lugar_norm_inicial])
                lugar_limpio_exacto = ALIASES_MUNICIPIOS[lugar_norm_inicial] 
            else:
                terr_norm = norm_text(lugar_crudo)
                lugar_limpio_exacto = lugar_crudo

            nivel_norm = str(nivel_jerarquico).upper().strip()
            
            es_nacional = "NACION" in nivel_norm
            es_departamento = "DEPARTAMENTO" in nivel_norm or "DEPARTAMENTAL" in nivel_norm or "COLOMBIA" in terr_norm
            es_municipio = "MUNICIPAL" in nivel_norm or "MUNICIPIO" in nivel_norm
            es_region = "REGION" in nivel_norm or "SUBREGION" in nivel_norm
            es_car = "CAR" in nivel_norm or "AUTORIDAD" in nivel_norm
            es_cuenca = "CUENCA" in nivel_norm or "NSS" in nivel_norm or "SZH" in nivel_norm
            
            encontrado = False

            # --- 1. BÚSQUEDA DE CUENCAS ---
            if es_cuenca:
                from modules.data_processor import load_and_process_all_data
                _, _, _, _, gdf_subcuencas, _ = load_and_process_all_data()
                
                if gdf_subcuencas is not None and not gdf_subcuencas.empty:
                    codigo_match = re.search(r'\((.*?)\)', str(nombre_zona))
                    cod_ideam = codigo_match.group(1).strip() if codigo_match else None
                    
                    encontrado = False
                    
                    if cod_ideam:
                        cols_cod = [c for c in gdf_subcuencas.columns if c.lower() in ['nss1', 'nss2', 'nss3', 'szh', 'zh', 'ah']]
                        for col in cols_cod:
                            mask_ideam = gdf_subcuencas[col].astype(str).str.strip() == cod_ideam
                            if mask_ideam.any():
                                gdf_zona_tmp = gdf_subcuencas[mask_ideam]
                                gdf_zona = gpd.GeoDataFrame(geometry=[gdf_zona_tmp.unary_union], crs=gdf_subcuencas.crs)
                                encontrado = True
                                break
                                
                    if not encontrado:
                        def limpiar_texto(t):
                            if not isinstance(t, str): return ""
                            return re.sub(r'[^A-Z0-9]', '', ''.join(c for c in unicodedata.normalize('NFD', t.upper()) if unicodedata.category(c) != 'Mn'))
                        
                        terr_limpio = limpiar_texto(lugar_crudo)
                        mask_c = gdf_subcuencas.apply(lambda row: terr_limpio in limpiar_texto(str(row.to_dict().values())), axis=1)
                        
                        if mask_c.any():
                            gdf_zona_tmp = gdf_subcuencas[mask_c]
                            
                            # =========================================================================
                            # 🛡️ INTERCEPTOR ESPACIAL ESTRICTO (MATA CLONES)
                            # =========================================================================
                            codigo_unico = st.session_state.get('aleph_codigo_cuenca', 'N/A')
                            
                            if codigo_unico != 'N/A':
                                mask_estricta = (gdf_subcuencas['NSS3'] == codigo_unico) | \
                                                (gdf_subcuencas['NSS2'] == codigo_unico) | \
                                                (gdf_subcuencas['NSS1'] == codigo_unico)
                                
                                if mask_estricta.any():
                                    gdf_zona_tmp = gdf_subcuencas[mask_estricta]
                                    
                            # 🔪 SEGURO ANTI-FRANKENSTEIN
                            if len(gdf_zona_tmp) > 1:
                                gdf_zona_tmp = gdf_zona_tmp.iloc[[0]]
                            # =========================================================================
                            
                            gdf_zona = gpd.GeoDataFrame(geometry=[gdf_zona_tmp.unary_union], crs=gdf_subcuencas.crs)
                            encontrado = True

            # --- 2. BÚSQUEDA TERRITORIAL ESTRUCTURAL ---
            if not encontrado and not es_cuenca:
                gdf_tm = fetch_territorio_maestro() 
                
                if not gdf_tm.empty:
                    # 🚀 FIX: Rescate seguro de variables y blindaje absoluto
                    lugar_seguro = str(locals().get('nombre_zona', locals().get('lugar_crudo', '')))
                    es_antioquia = "ANTIOQUIA" in lugar_seguro.upper() or "ANTIOQUIA" in str(terr_norm).upper()
                    
                    if es_nacional or es_departamento or es_antioquia:
                        # Búsqueda dinámica de la columna
                        col_depto = next((col for col in gdf_tm.columns if col.lower() in ['dpto_cnmbr', 'departamento']), None)
                        
                        if col_depto and not es_nacional:
                            # Filtro indestructible
                            mask = gdf_tm[col_depto].astype(str).str.upper().str.strip() == 'ANTIOQUIA'
                        else:
                            mask = pd.Series(True, index=gdf_tm.index)
                            
                        if mask.any():
                            # Reparamos geometrías y fusionamos
                            gdf_tm['geometry'] = gdf_tm.geometry.make_valid()
                            gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm[mask].unary_union], crs=gdf_tm.crs)
                            encontrado = True
                                
                    elif es_region:
                        col_sub = 'subregion'
                        if col_sub in gdf_tm.columns:
                            mask = gdf_tm[col_sub].apply(norm_text) == terr_norm
                            if mask.any():
                                gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm[mask].unary_union], crs=gdf_tm.crs)
                                encontrado = True
                                
                    elif es_car:
                        col_car = 'car'
                        if col_car in gdf_tm.columns:
                            if terr_norm == "amva":
                                mask = gdf_tm[col_car].apply(norm_text).str.contains("amva|aburra", na=False)
                            elif terr_norm == "corantioquia":
                                mask_corantioquia = gdf_tm[col_car].apply(norm_text).str.contains("corantioquia", na=False)
                                mask_no_amva = ~gdf_tm['mpio_cnmbr'].apply(norm_text).isin(['medellin', 'bello', 'itagui', 'envigado', 'sabaneta', 'copacabana', 'la estrella', 'girardota', 'caldas', 'barbosa'])
                                mask = mask_corantioquia & mask_no_amva
                            else:
                                mask = gdf_tm[col_car].apply(norm_text).str.contains(terr_norm, na=False)

                            if mask.any():
                                gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm[mask].unary_union], crs=gdf_tm.crs)
                                encontrado = True
                                
                    elif es_municipio:
                        col_mpio = 'mpio_cnmbr' if 'mpio_cnmbr' in gdf_tm.columns else 'municipio'
                        if col_mpio in gdf_tm.columns:
                            mask_norm = gdf_tm[col_mpio].apply(norm_text) == terr_norm
                            mask_exacta = gdf_tm[col_mpio] == lugar_limpio_exacto
                            mask = mask_norm | mask_exacta
                            
                            if mask.any():
                                gdf_zona = gpd.GeoDataFrame(geometry=[gdf_tm[mask].unary_union], crs=gdf_tm.crs)
                                encontrado = True

            if encontrado:
                st.sidebar.success("🪂 ¡Polígono sincronizado para GEE (Topología Exacta)!")
            else:
                st.sidebar.error("⚠️ El polígono no existe en la matriz maestra.")
                
        except Exception as e:
            st.sidebar.error(f"Error de sincronización estructural: {e}")

st.sidebar.success(f"🔗 Conexión Aleph Activa: {nombre_zona}")

# ==========================================
# 1. MOTOR DE AUTENTICACIÓN
# ==========================================
@st.cache_resource
def iniciar_conexion_gee():
    try:
        credenciales_dict = dict(st.secrets["gcp_service_account"])
        credentials = ee.ServiceAccountCredentials(
            email=credenciales_dict["client_email"],
            key_data=credenciales_dict["private_key"]
        )
        ee.Initialize(credentials)
        return True
    except Exception as e:
        st.error(f"Fallo en la comunicación con el satélite: {e}")
        return False

# ==========================================
# 2. PUENTE NATIVO FOLIUM - EARTH ENGINE
# ==========================================
def add_ee_layer(self, ee_image_object, vis_params, name):
    try:
        map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
        folium.raster_layers.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='Map Data &copy; Google Earth Engine',
            name=name,
            overlay=True,
            control=True
        ).add_to(self)
    except Exception as e:
        print(f"Error añadiendo capa EE: {e}")

folium.Map.add_ee_layer = add_ee_layer

# ==========================================
# 3. RENDERIZADO DEL MAPA DINÁMICO (Conexión SIG)
# ==========================================
if iniciar_conexion_gee():
    # Validamos que el usuario haya seleccionado una zona válida en el selector
    if gdf_zona is not None and not gdf_zona.empty:
        st.success(f"✅ Satélite enlazado. Escaneando la zona: **{nombre_zona}**")
        
        with st.spinner("Calculando órbitas y aplicando IA de clasificación... esto puede tomar unos segundos."):
            # 1. Convertir el polígono Geopandas a formato Google Earth Engine
            minx, miny, maxx, maxy = gdf_zona.total_bounds
            
            # Extraemos la geometría exacta (con todas sus curvas) para recortar el mapa
            # 🔥 CURACIÓN TOPOLÓGICA: Hacemos válidas las geometrías y aplicamos un buffer 0 para eliminar nudos antes de unir
            geom_unificada = gdf_zona.geometry.make_valid().buffer(0).unary_union
            # Convertimos esa figura maestra al lenguaje que entiende el satélite
            roi_ee = ee.Geometry(geom_unificada.__geo_interface__)
            
            # 2. Consultar Dynamic World para el último año
            dw_coleccion = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
                           .filterBounds(roi_ee) \
                           .filterDate('2023-01-01', '2024-01-01')
            
            # Magia: Tomamos el promedio (mode) y lo RECORTAMOS con la forma exacta de la cuenca
            dw_imagen = dw_coleccion.select('label').mode().clip(roi_ee)
            
            # ==========================================================
            # 🧠 INVENTARIO TOTAL DE COBERTURAS EN TIEMPO REAL
            # ==========================================================
            try:
                # 1. Agrupar píxeles por clase y sumar su área (m2)
                pixel_area = ee.Image.pixelArea()
                area_por_clase = pixel_area.addBands(dw_imagen).reduceRegion(
                    reducer=ee.Reducer.sum().group(groupField=1, groupName='clase'),
                    geometry=roi_ee,
                    scale=10, # Resolución de 10x10 metros
                    maxPixels=1e13, # 🔥 Límite expandido a 10 billones de píxeles
                    bestEffort=True # 🔥 Si es muy pesado, Google ajustará la escala automáticamente para no fallar
                ).get('groups')
                
                # 2. Traer los datos desde los servidores de Google a Python
                estadisticas = area_por_clase.getInfo()
                
                # 3. Diccionario de Clases Oficial de Dynamic World
                nombres_clases = {
                    0: "Agua", 1: "Bosques", 2: "Pastos", 3: "Cultivos", 
                    4: "Matorrales", 5: "Suelo Desnudo", 6: "Urbano / Infraestructura", 
                    7: "Nieve", 8: "Nubes"
                }
                
                # 4. Procesar resultados y capturar TODAS las coberturas
                resultados = []
                
                # Inicializamos contadores en 0.0 para evitar errores si una clase no existe en la foto
                ha_coberturas = {
                    'Agua': 0.0, 'Bosques': 0.0, 'Pastos': 0.0, 
                    'Cultivos': 0.0, 'Matorrales': 0.0, 
                    'Suelo Desnudo': 0.0, 'Urbano': 0.0
                }
                
                for item in estadisticas:
                    clase_id = int(item['clase'])
                    area_ha = item['sum'] / 10000.0 # Convertir m2 a Hectáreas
                    nombre = nombres_clases.get(clase_id, "Desconocido")
                    resultados.append({"Cobertura": nombre, "Área (ha)": area_ha})
                    
                    # 🧲 Atrapamos el valor exacto para cada clase
                    if clase_id == 0: ha_coberturas['Agua'] = area_ha
                    elif clase_id == 1: ha_coberturas['Bosques'] = area_ha
                    elif clase_id == 2: ha_coberturas['Pastos'] = area_ha
                    elif clase_id == 3: ha_coberturas['Cultivos'] = area_ha
                    elif clase_id == 4: ha_coberturas['Matorrales'] = area_ha
                    elif clase_id == 5: ha_coberturas['Suelo Desnudo'] = area_ha
                    elif clase_id == 6: ha_coberturas['Urbano'] = area_ha
                    
                # 💾 INYECCIÓN AL TORRENTE SANGUÍNEO (SESSION STATE)
                st.session_state['satelite_ha_agua'] = ha_coberturas['Agua']
                st.session_state['satelite_ha_bosque'] = ha_coberturas['Bosques']
                st.session_state['satelite_ha_pastos'] = ha_coberturas['Pastos']
                st.session_state['satelite_ha_cultivos'] = ha_coberturas['Cultivos']
                st.session_state['satelite_ha_matorrales'] = ha_coberturas['Matorrales']
                st.session_state['satelite_ha_suelo_desnudo'] = ha_coberturas['Suelo Desnudo']
                st.session_state['satelite_ha_urbano'] = ha_coberturas['Urbano']
                
                # 5. Renderizar Gráfico y Tabla en Streamlit
                if resultados:
                    import pandas as pd
                    import plotly.express as px
                    
                    df_coberturas = pd.DataFrame(resultados).sort_values(by="Área (ha)", ascending=False)
                    
                    st.markdown("### 📊 Inventario Satelital de Uso de Suelo")
                    c_graf, c_tabla = st.columns([2, 1])
                    
                    with c_tabla:
                        st.dataframe(df_coberturas.style.format({"Área (ha)": "{:,.1f}"}), use_container_width=True)
                        
                    with c_graf:
                        fig_pie = px.pie(
                            df_coberturas, values='Área (ha)', names='Cobertura', hole=0.4, 
                            color='Cobertura', color_discrete_map={
                                "Agua": "#419BDF", "Bosques": "#397D49", "Pastos": "#88B053", 
                                "Cultivos": "#7A87C6", "Matorrales": "#E49635", "Suelo Desnudo": "#DFC35A", 
                                "Urbano / Infraestructura": "#C4281B", "Nieve": "#A59B8F", "Nubes": "#B39FE1"
                            }
                        )
                        fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350)
                        st.plotly_chart(fig_pie, use_container_width=True)
                        
            except Exception as e:
                st.warning(f"Error procesando estadísticas satelitales: {e}")
            # ==========================================================
            # ==========================================================
            
            # 3. Paleta Oficial de Dynamic World
            dw_vis = {
                'min': 0, 'max': 8,
                'palette': [
                    '#419BDF', # 0: Agua
                    '#397D49', # 1: Árboles / Bosques
                    '#88B053', # 2: Pastos
                    '#7A87C6', # 3: Cultivos
                    '#E49635', # 4: Matorrales
                    '#DFC35A', # 5: Suelo Desnudo
                    '#C4281B', # 6: Construido / Urbano
                    '#A59B8F', # 7: Nieve / Hielo
                    '#B39FE1'  # 8: Nubes / Sin datos
                ]
            }
            
            # 4. Crear Mapa Base Centrado en la Zona Seleccionada
            centro_y = (miny + maxy) / 2
            centro_x = (minx + maxx) / 2
            m = folium.Map(location=[centro_y, centro_x], zoom_start=11)
            
            # Fondo satelital normal de Google
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                attr='Google',
                name='Satélite HD Base',
                overlay=False,
                control=True
            ).add_to(m)
            
            # Inyectar la capa de IA
            m.add_ee_layer(dw_imagen, dw_vis, f'Cobertura IA ({nombre_zona})')
            
            # Dibujar un borde blanco brillante alrededor del territorio
            folium.GeoJson(
                gdf_zona,
                name="Límite Territorial",
                style_function=lambda x: {'color': 'white', 'weight': 3, 'fillOpacity': 0}
            ).add_to(m)
            
            folium.LayerControl().add_to(m)
            
            # Renderizar en la pantalla de Streamlit
            st_folium(m, width="100%", height=600, returned_objects=[])
            
            # Leyenda visual
            st.markdown("""
            **Leyenda de Coberturas (Dynamic World a 10m de resolución):**
            🟦 Agua | 🟩 Bosques | 🟨 Pastos | 🟪 Cultivos | 🟧 Matorrales | 🟫 Suelo Desnudo | 🟥 Infraestructura / Urbano
            """)
    else:
        st.info("👈 Por favor, selecciona un territorio en el panel lateral para iniciar el escaneo satelital.")

# ==============================================================================
# 🛠️ PANEL DE ADMINISTRADOR: EXTRACCIÓN SATELITAL (GEE -> GOOGLE DRIVE)
# ==============================================================================
st.markdown("---")
with st.expander("🛠️ Panel de Administrador: Extracción Satelital Avanzada (Alta Resolución)", expanded=False):
    st.info("""
    **¿Qué hace esto?** Le ordena a la supercomputadora de Google Earth Engine que recorte el mapa global de Usos del Suelo de la ESA (10 metros de resolución) usando el perímetro exacto de Antioquia. 
    Para no colapsar la memoria de la aplicación, el archivo `.tif` resultante se exportará directamente a tu Google Drive en segundo plano.
    """)

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🚀 Iniciar Exportación a Google Drive", type="primary"):
            with st.spinner("Programando tarea en los servidores de Google..."):
                try:
                    import ee
                    
                    # 1. Definir el polígono de Antioquia (Nivel departamental de FAO)
                    antioquia = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq('ADM1_NAME', 'Antioquia'))
                    region_geo = antioquia.geometry()

                    # 2. Cargar el Dataset de la Agencia Espacial Europea (ESA WorldCover v200 - 2021)
                    dataset = ee.ImageCollection("ESA/WorldCover/v200").first()
                    landcover = dataset.select('Map').clip(region_geo)

                    # 3. Crear y configurar la Tarea de Exportación
                    # Guarda el archivo en el Drive de la cuenta autenticada en Earth Engine
                    task = ee.batch.Export.image.toDrive(
                        image=landcover,
                        description='Usos_Suelo_Antioquia_ESA_10m',
                        folder='SIHCLIM_Rasters',  # Creará esta carpeta en tu Drive si no existe
                        fileNamePrefix='Cob10m_Antioquia_ESA_2021',
                        region=region_geo,
                        scale=10, # Resolución original máxima (10 metros)
                        maxPixels=1e13, # Límite expandido para mapas gigantes
                        crs='EPSG:4326'
                    )

                    # 4. Disparar la tarea
                    task.start()
                    
                    st.success("✅ ¡Orden enviada con éxito a Google Earth Engine!")
                    st.code(f"ID de Tarea: {task.id}", language="text")
                    
                except Exception as e:
                    st.error(f"🚨 Error de conexión con Google Earth Engine: {e}")
                    
    with col2:
        st.markdown("""
        **Pasos a seguir después de iniciar:**
        1. Puedes cerrar esta ventana y seguir usando la aplicación. El proceso ocurrirá en los servidores de Google.
        2. Abre tu **Google Drive** (con la cuenta asociada a Earth Engine).
        3. Busca la carpeta `SIHCLIM_Rasters`.
        4. En unos minutos (o un par de horas), aparecerá el archivo `Cob10m_Antioquia_ESA_2021.tif`.
        5. Descárgalo y súbelo a Supabase para reemplazar el mapa estático actual.
        """)
