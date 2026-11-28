# pages/11_⚙️_Generador.py

import streamlit as st
import geopandas as gpd
import pandas as pd
import tempfile
import zipfile
import io
import os
import warnings
import re
import unicodedata


from modules import climate_api

warnings.filterwarnings('ignore')
st.set_page_config(page_title="Generador Espacial", page_icon="⚙️", layout="wide")

st.title("⚙️ Centro de Geoprocesamiento y Transformación")
st.info("Herramientas de administrador para cruces espaciales, compresión y estandarización de cartografía web.")

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
            if st.button("Ingresar al Gemelo Digital", type="primary", width="stretch"):
                # 💡 La contraseña por defecto es "AdminPoter"
                if clave_beta == st.secrets.get("CLAVE_BETA", "AdminPoter"):
                    st.session_state["beta_unlocked"] = True
                    st.rerun() # Recarga la página y muestra todo el contenido
                else:
                    st.error("❌ Credencial incorrecta. Acceso denegado.")
        
        # 🛑 st.stop() es la magia: evita que Python siga leyendo el código hacia abajo
        st.stop() 

# Llamamos a la función para activar el escudo
muro_de_acceso_beta()

# ==============================================================================

# --- ACTUALIZACIÓN: AGREGAMOS LA CUARTA PESTAÑA ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🧩 1. Intersecciones Espaciales (Cuencas)", 
    "🔄 2. Convertidor GeoJSON (Soporta ZIP y Simplificación)", 
    "🗜️ 3. Compresor/Extractor ZIP",
    "🔁 4. Convertidor GeoJSON a SHP + Atributos",
    "🔗 5. Homologador de Veredas",
    "🌧️ 6. Fusión Hidrometeorológica",
    "📡 7. Puente SIATA (Tiempo Real)"
])

# =====================================================================
# PESTAÑA 1: INTERSECCIÓN ESPACIAL (MUNICIPIOS O VEREDAS)
# =====================================================================
with tab1:
    st.subheader("Generador de Intersecciones Espaciales")
    st.write("Cruce de mapas para calcular la proporción de cada territorio dentro de las cuencas.")
    
    nivel_cruce = st.radio("Selecciona el Nivel Territorial a cruzar con las Cuencas:", ["Municipios", "Veredas"], horizontal=True)
    
    if st.button(f"🚀 Iniciar Cruce Espacial ({nivel_cruce})", type="primary"):
        with st.spinner("1. Cargando y proyectando mapas (EPSG:9377)..."):
            try:
                # 1. Cargar Cuencas (Siempre es el mismo)
                cuencas = gpd.read_file('data/SubcuencasAinfluencia.geojson')
                cuencas = cuencas.to_crs(epsg=9377)
                
                # 2. Cargar Capa Territorial según la selección
                if nivel_cruce == "Municipios":
                    territorio = gpd.read_file('data/mgn_municipios_optimizado.geojson')
                    col_nombre = 'MPIO_CNMBR'
                    col_padre = 'DPTO_CNMBR' # Opcional
                    nombre_salida = 'cuencas_mpios_proporcion.csv'
                else:
                    territorio = gpd.read_file('data/Veredas_Antioquia_TOTAL_UrbanoyRural.geojson')
                    col_nombre = 'NOMBRE_VER'
                    col_padre = 'NOMB_MPIO' # Necesario en veredas por homonimia
                    nombre_salida = 'cuencas_veredas_proporcion.csv'
                
                territorio = territorio.to_crs(epsg=9377)
                st.success(f"Mapas cargados. Cuencas: {len(cuencas)} | {nivel_cruce}: {len(territorio)}")

                # 3. Calcular área original del territorio
                territorio['Area_Original_Ha'] = territorio.geometry.area / 10000

                # 4. Intersección
                st.info("2. Ejecutando geoprocesamiento de intersección (Esto puede tardar unos minutos)...")
                interseccion = gpd.overlay(territorio, cuencas, how='intersection')

                # 5. Calcular nueva área y proporción
                interseccion['Area_Interseccion_Ha'] = interseccion.geometry.area / 10000
                interseccion['Porcentaje'] = (interseccion['Area_Interseccion_Ha'] / interseccion['Area_Original_Ha']) * 100
                
                # Limpiamos porcentajes mayores a 100 (errores de topología menores)
                interseccion['Porcentaje'] = interseccion['Porcentaje'].apply(lambda x: min(x, 100.0))

                # 6. Preparar tabla final
                if nivel_cruce == "Municipios":
                    df_final = interseccion[['MPIO_CNMBR', 'ZH', 'SUBC_LBL', 'N_NSS1', 'Area_Interseccion_Ha', 'Porcentaje']].copy()
                    df_final.columns = ['Municipio', 'Zona_Hidrografica', 'Subcuenca', 'Sistema', 'Area_Ha', 'Porcentaje']
                else:
                    df_final = interseccion[['NOMBRE_VER', 'NOMB_MPIO', 'ZH', 'SUBC_LBL', 'N_NSS1', 'Area_Interseccion_Ha', 'Porcentaje']].copy()
                    df_final.columns = ['Vereda', 'Municipio', 'Zona_Hidrografica', 'Subcuenca', 'Sistema', 'Area_Ha', 'Porcentaje']

                st.success("✅ Cruce completado con éxito.")
                st.dataframe(df_final.head())

                # 7. Botón de descarga
                csv = df_final.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"📥 Descargar {nombre_salida}",
                    data=csv,
                    file_name=nombre_salida,
                    mime='text/csv',
                )

            except Exception as e:
                st.error(f"🚨 Ocurrió un error en el cruce: {e}")

# =====================================================================
# PESTAÑA 2: EL TRANSFORMADOR DE SHAPEFILES (SOPORTA ZIP Y SIMPLIFICACIÓN)
# =====================================================================
with tab2:
    st.subheader("Transformador y Optimizador Web de Cartografía")
    st.markdown("Sube un archivo **.zip** (ej. de 65 MB) que contenga tu Shapefile. El sistema lo descomprimirá, lo simplificará para la web y te entregará un GeoJSON ligero.")
    
    modo_carga = st.radio("Método de Carga:", ["Subir archivo .zip (Recomendado)", "Subir archivos sueltos"], horizontal=True)
    
    # --- CONTROL DE SIMPLIFICACIÓN ---
    st.markdown("---")
    st.markdown("#### 📉 Optimización Topológica (Adelgazar Mapa)")
    simplificar = st.checkbox("Activar simplificación de fronteras (Crucial para mapas Nacionales grandes)", value=True)
    factor_simp = st.slider(
        "Tolerancia (Grados). Más alto = Más liviano pero bordes más rectos. 0.005 es ideal para Municipios.", 
        min_value=0.001, max_value=0.050, value=0.005, step=0.001, format="%.3f"
    )
    st.markdown("---")
    
    if modo_carga == "Subir archivo .zip (Recomendado)":
        archivo_zip = st.file_uploader("Sube tu archivo ZIP (debe contener un .shp adentro)", type=['zip'])
        
        if archivo_zip and st.button("⚙️ Descomprimir, Simplificar y Transformar"):
            with st.spinner("Procesando ZIP en la nube..."):
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        # 1. Extraer ZIP
                        with zipfile.ZipFile(archivo_zip, 'r') as zip_ref:
                            zip_ref.extractall(tmpdir)
                            
                        # 2. Buscar archivo .shp
                        ruta_shp = None
                        for root, dirs, files in os.walk(tmpdir):
                            for file in files:
                                if file.lower().endswith('.shp'):
                                    ruta_shp = os.path.join(root, file)
                                    break
                            if ruta_shp: break
                            
                        if not ruta_shp:
                            st.error("❌ No se encontró ningún archivo .shp dentro del ZIP.")
                        else:
                            # 3. Leer con GeoPandas
                            st.toast("Leyendo polígonos...")
                            gdf = gpd.read_file(ruta_shp)
                            
                            # 4. Proyección a WGS84 (Web)
                            if gdf.crs is None: gdf.set_crs(epsg=3116, inplace=True)
                            if gdf.crs.to_string() != "EPSG:4326": 
                                st.toast("Reproyectando coordenadas a WGS84...")
                                gdf = gdf.to_crs(epsg=4326)
                            
                            # 5. SIMPLIFICACIÓN TOPOLÓGICA MÁGICA
                            if simplificar:
                                st.toast(f"Simplificando geometrías (Tolerancia: {factor_simp})...")
                                gdf['geometry'] = gdf['geometry'].simplify(tolerance=factor_simp, preserve_topology=True)
                            
                            st.toast("Convirtiendo a GeoJSON...")
                            geojson_data = gdf.to_json()
                            nombre_base = os.path.basename(ruta_shp).replace('.shp', '').replace('.SHP', '') + "_optimizado"
                            
                            st.success(f"✅ ¡Capa '{nombre_base}' lista! ({len(gdf)} polígonos procesados).")
                            st.download_button(
                                label=f"📥 Descargar {nombre_base}.geojson",
                                data=geojson_data,
                                file_name=f"{nombre_base}.geojson",
                                mime="application/json"
                            )
                except Exception as e:
                    st.error(f"❌ Error procesando el ZIP: {str(e)}")
                    
    else: # Modo archivos sueltos
        archivos_subidos = st.file_uploader("Selecciona archivos (Mínimo .shp, .shx y .dbf)", accept_multiple_files=True)
        if archivos_subidos:
            archivo_shp = next((f for f in archivos_subidos if f.name.lower().endswith('.shp')), None)
            
            if archivo_shp and st.button("⚙️ Transformar sueltos a GeoJSON"):
                with st.spinner("Procesando archivos sueltos..."):
                    try:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            for f in archivos_subidos:
                                with open(os.path.join(tmpdir, f.name), "wb") as f_out:
                                    f_out.write(f.getvalue())
                                    
                            ruta_shp_temporal = os.path.join(tmpdir, archivo_shp.name)
                            gdf = gpd.read_file(ruta_shp_temporal)
                            
                            if gdf.crs is None: gdf.set_crs(epsg=3116, inplace=True)
                            if gdf.crs.to_string() != "EPSG:4326": gdf = gdf.to_crs(epsg=4326)
                            
                            if simplificar:
                                gdf['geometry'] = gdf['geometry'].simplify(tolerance=factor_simp, preserve_topology=True)
                            
                            geojson_data = gdf.to_json()
                            nombre_base = archivo_shp.name.replace('.shp', '').replace('.SHP', '') + "_optimizado"
                            
                            st.success(f"✅ ¡Capa estandarizada! ({len(gdf)} registros).")
                            st.download_button(
                                label=f"📥 Descargar {nombre_base}.geojson", data=geojson_data,
                                file_name=f"{nombre_base}.geojson", mime="application/json"
                            )
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            elif not archivo_shp:
                st.warning("⚠️ Falta el archivo principal .shp en tu selección.")

# =====================================================================
# PESTAÑA 3: UTILIDAD DE COMPRESIÓN / DESCOMPRESIÓN ZIP
# =====================================================================
with tab3:
    st.subheader("🗜️ Gestor de Archivos ZIP")
    
    col_zip1, col_zip2 = st.columns(2)
    
    with col_zip1:
        st.markdown("### 📦 Comprimir Archivos")
        st.markdown("Sube varios archivos sueltos para empaquetarlos en un solo `.zip`.")
        archivos_a_comprimir = st.file_uploader("Selecciona archivos a comprimir", accept_multiple_files=True, key="uploader_comp")
        
        if archivos_a_comprimir:
            nombre_zip = st.text_input("Nombre del archivo final:", value="mapas_comprimidos")
            if st.button("📦 Crear Archivo ZIP"):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for archivo in archivos_a_comprimir:
                        zip_file.writestr(archivo.name, archivo.getvalue())
                
                st.success("✅ ZIP creado exitosamente.")
                st.download_button(
                    label=f"📥 Descargar {nombre_zip}.zip",
                    data=zip_buffer.getvalue(),
                    file_name=f"{nombre_zip}.zip",
                    mime="application/zip"
                )

    with col_zip2:
        st.markdown("### 📂 Descomprimir ZIP")
        st.markdown("Sube un archivo `.zip` para extraer su contenido.")
        archivo_a_descomprimir = st.file_uploader("Sube un archivo ZIP", type=['zip'], key="uploader_desc")
        
        if archivo_a_descomprimir:
            with zipfile.ZipFile(archivo_a_descomprimir, 'r') as zip_ref:
                lista_archivos = zip_ref.namelist()
                st.write(f"**Contiene {len(lista_archivos)} archivos:**")
                for nombre_archivo in lista_archivos:
                    if not nombre_archivo.endswith('/'): 
                        datos_archivo = zip_ref.read(nombre_archivo)
                        st.download_button(
                            label=f"⬇️ {os.path.basename(nombre_archivo)}",
                            data=datos_archivo,
                            file_name=os.path.basename(nombre_archivo),
                            key=f"desc_{nombre_archivo}"
                        )

    # -------------------------------------------------------------------------
    # ⚡ SUPERPODER: PROCESADOR AUTOMÁTICO MASIVO DE ZIPs DEL SIATA
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("🦸‍♂️ Procesador Automático Multi-ZIP (Lluvia SIATA)")
    st.markdown("Sube **todos los archivos `.zip`** que hayas descargado del SIATA al mismo tiempo. El sistema devorará todas las estaciones, sumará la lluvia diaria y ensamblará una matriz consolidada única.")
    
    # 🔥 MAGIA ACTIVADA: accept_multiple_files=True
    archivos_zip_siata = st.file_uploader("Sube uno o varios archivos .zip del SIATA:", type=['zip'], key="zips_siata", accept_multiple_files=True)
    
    if archivos_zip_siata and st.button("🚀 Extraer, Sumar y Consolidar Todo", type="primary"):
        with st.spinner(f"Procesando {len(archivos_zip_siata)} archivos ZIP simultáneamente..."):
            try:
                import pandas as pd
                import numpy as np
                import zipfile
                import re
                import os
                from io import StringIO
                
                lista_dataframes = []
                codigos_nulos = [-999, -999.0, -99.9, 999, 999.9, 9999, -9999, -9999.0]
                
                for archivo_zip in archivos_zip_siata:
                    try:
                        with zipfile.ZipFile(archivo_zip, 'r') as z:
                            for nombre_archivo in z.namelist():
                                try:
                                    nombre_base = os.path.basename(nombre_archivo).lower()
                                    # Ignorar archivos que no sean de datos o catálogos de estaciones
                                    if not nombre_base.endswith(('.csv', '.tab', '.txt')):
                                        continue
                                    if 'estaciones_pluviometro' in nombre_base or 'catalogo' in nombre_base or 'manifest' in nombre_base:
                                        continue
                                        
                                    # 🔥 FIX 1: Captura tanto archivos modernos (_4_2026_01) como históricos 2010-2012 (_4_tm_2010_01)
                                    match_estacion = re.search(r'_(\d{1,4})(?:_tm)?_(\d{4})[-_](\d{2})', nombre_base)
                                    id_estacion = f"SIATA_{match_estacion.group(1)}" if match_estacion else "SIATA_Desconocida"
                                    
                                    with z.open(nombre_archivo) as f:
                                        raw_bytes = f.read()
                                        try:
                                            texto = raw_bytes.decode('utf-8')
                                        except UnicodeDecodeError:
                                            texto = raw_bytes.decode('latin1')
                                            
                                        df_temp = pd.read_csv(StringIO(texto), sep=None, engine='python', on_bad_lines='skip')
                                        
                                    if df_temp is None or df_temp.empty:
                                        continue
                                        
                                    # Normalizar nombres de columnas (limpia BOM, espacios y pasa a minúsculas: 'P' -> 'p')
                                    df_temp.columns = [str(c).replace('\ufeff', '').strip().lower() for c in df_temp.columns]
                                    
                                    # Si la columna 'codigo' viene dentro del archivo, usarla para garantizar el ID exacto
                                    if 'codigo' in df_temp.columns and df_temp['codigo'].dropna().shape[0] > 0:
                                        cod_interno = str(df_temp['codigo'].dropna().iloc[0]).split('.')[0].strip()
                                        if cod_interno.isdigit():
                                            id_estacion = f"SIATA_{cod_interno}"
                                            
                                    # 🔥 FIX 2: Detecta 'p1', 'p2' (2012-2026) y también la columna exacta 'p' (2010-2012)
                                    col_fecha = next((c for c in df_temp.columns if any(k in c for k in ['fech', 'date', 'time'])), None)
                                    col_valor = next(
                                        (c for c in df_temp.columns if c in ['p1', 'p', 'p2'] or any(k in c for k in ['valor', 'precip', 'lluvia', 'p (mm)', 'acum', 'mm'])),
                                        None
                                    )
                                    
                                    if col_fecha and col_valor:
                                        # 🔥 FIX 3: Reglas Oficiales de Calidad SIATA (Tabla 4 - P-GAA-SIATA-107)
                                        if 'p1' in df_temp.columns:
                                            p1 = pd.to_numeric(df_temp['p1'].astype(str).str.replace(',', '.'), errors='coerce').replace(codigos_nulos, np.nan)
                                            p2 = (
                                                pd.to_numeric(df_temp['p2'].astype(str).str.replace(',', '.'), errors='coerce').replace(codigos_nulos, np.nan)
                                                if 'p2' in df_temp.columns else pd.Series(np.nan, index=df_temp.index)
                                            )
                                            serie_lluvia = p1.fillna(p2)
                                            if 'calidad' in df_temp.columns:
                                                cal = pd.to_numeric(df_temp['calidad'], errors='coerce').fillna(1).astype(int)
                                                # Si p1 es dudoso (1511, 2511, 15110, 25110) -> tomar p2
                                                mask_p1_malo = cal.isin([1511, 2511, 15110, 25110])
                                                serie_lluvia.loc[mask_p1_malo] = p2.loc[mask_p1_malo]
                                                # Si ambos son dudosos (151, 251, 1510, 2510) -> anular minuto
                                                mask_ambos_malos = cal.isin([151, 251, 1510, 2510])
                                                serie_lluvia.loc[mask_ambos_malos] = np.nan
                                        else:
                                            # Archivos 2010-2012 (columna 'p') u otros formatos
                                            serie_lluvia = pd.to_numeric(df_temp[col_valor].astype(str).str.replace(',', '.'), errors='coerce').replace(codigos_nulos, np.nan)
                                            if 'calidad' in df_temp.columns and col_valor == 'p':
                                                cal = pd.to_numeric(df_temp['calidad'], errors='coerce').fillna(1).astype(int)
                                                serie_lluvia.loc[~cal.isin([1, 2])] = np.nan
                                                
                                        # Filtro físico por registro minuto / 5-min (0 a 50 mm)
                                        df_temp['lluvia_limpia'] = serie_lluvia.where((serie_lluvia >= 0) & (serie_lluvia < 50))
                                        
                                        # 🔥 FIX 4: Fecha mensual exacta sin el bug de dayfirst=True en fechas YYYY-MM-DD
                                        if match_estacion and df_temp['lluvia_limpia'].notna().sum() > 0:
                                            anio_arch, mes_arch = int(match_estacion.group(2)), int(match_estacion.group(3))
                                            fecha_mes = pd.Timestamp(year=anio_arch, month=mes_arch, day=1)
                                            df_mensual = pd.DataFrame({
                                                'fecha': [fecha_mes],
                                                id_estacion: [round(float(df_temp['lluvia_limpia'].sum()), 2)]
                                            })
                                            lista_dataframes.append(df_mensual)
                                        else:
                                            muestra_f = str(df_temp[col_fecha].dropna().iloc[0]).strip() if not df_temp[col_fecha].dropna().empty else ""
                                            es_iso = bool(re.match(r'^\d{4}[-/]', muestra_f))
                                            df_temp['fecha_dt'] = pd.to_datetime(df_temp[col_fecha], format='mixed', dayfirst=not es_iso, errors='coerce')
                                            df_temp = df_temp.dropna(subset=['fecha_dt', 'lluvia_limpia'])
                                            
                                            if not df_temp.empty:
                                                df_temp['mes_año'] = df_temp['fecha_dt'].dt.to_period('M').dt.to_timestamp()
                                                df_mensual = df_temp.groupby('mes_año', as_index=False)['lluvia_limpia'].sum().round(2)
                                                df_mensual = df_mensual.rename(columns={'mes_año': 'fecha', 'lluvia_limpia': id_estacion})
                                                lista_dataframes.append(df_mensual)
                                except Exception:
                                    continue
                    except Exception:
                        continue

                if lista_dataframes:
                    # 1. Fusión masiva de todos los meses procesados
                    df_master = pd.concat(lista_dataframes, ignore_index=True)
                    df_master['fecha'] = pd.to_datetime(df_master['fecha']).dt.to_period('M').dt.to_timestamp()
                    
                    # 2. Eliminar fragmentos idénticos (si subiste dos veces el mismo ZIP) y sumar por fecha
                    df_master = df_master.drop_duplicates()
                    df_final = df_master.groupby('fecha', as_index=False).sum(min_count=1)
                    
                    # 3. 🛡️ CORTAFUEGOS TEMPORAL: Solo permite entre Enero 2010 y el mes actual (bloquea Dic 2026)
                    mes_actual_tope = pd.Timestamp.today().to_period('M').to_timestamp()
                    df_final = df_final[
                        (df_final['fecha'] >= pd.Timestamp('2010-01-01')) & 
                        (df_final['fecha'] <= mes_actual_tope)
                    ].copy()
                    
                    # 4. Ordenar cronológicamente y redondear antes de convertir la fecha a texto
                    df_final = df_final.sort_values('fecha').reset_index(drop=True)
                    cols_num = [c for c in df_final.columns if c != 'fecha']
                    df_final[cols_num] = df_final[cols_num].round(2)
                    df_final['fecha'] = df_final['fecha'].dt.strftime('%Y-%m-%d')
                    
                    st.success(f"✅ ¡Multi-Magia completada! Se procesaron {len(lista_dataframes)} archivos mensuales y se ensambló la súper-matriz ({len(cols_num)} estaciones).")
                    st.dataframe(df_final, use_container_width=True)
                    
                    csv_consolidado = df_final.to_csv(index=False, sep=';', decimal=',', encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        label="📥 Descargar Súper-Matriz Multi-Estación (Lista para Inyectar)",
                        data=csv_consolidado,
                        file_name="Datos_SIATA_Multi_ZIP_Consolidado.csv",
                        mime="text/csv",
                        type="primary",
                        use_container_width=True
                    )
                else:
                    st.warning("⚠️ No se encontraron datos válidos de precipitación dentro de los archivos ZIP.")
            except Exception as e:
                st.error(f"❌ Error al procesar los archivos ZIP: {e}")

# =====================================================================
# PESTAÑA 4: CONVERTIDOR GEOJSON A SHAPEFILE + VISOR DE ATRIBUTOS
# =====================================================================
with tab4:
    st.subheader("🔁 Convertidor GeoJSON a Shapefile (SHP) y Visor de Atributos")
    st.markdown("Sube un archivo **.geojson** o **.json**. Podrás previsualizar su tabla de atributos y exportarlo como un Shapefile listo para software GIS (QGIS/ArcGIS).")
    
    archivo_geojson_in = st.file_uploader("Sube tu archivo GeoJSON", type=['geojson', 'json'], key="up_geo2shp")
    
    if archivo_geojson_in:
        with st.spinner("Leyendo estructura del archivo espacial..."):
            try:
                # 1. Leer el GeoJSON
                gdf_in = gpd.read_file(archivo_geojson_in)
                
                # 🔥 INYECCIÓN: Extraer X e Y de la geometría a columnas de la tabla
                if gdf_in.crs is None or gdf_in.crs != "EPSG:4326":
                    gdf_in = gdf_in.to_crs(epsg=4326) # Aseguramos formato WGS84 (Grados Decimales)
                
                gdf_in['Longitud_W'] = gdf_in.geometry.x
                gdf_in['Latitud_N'] = gdf_in.geometry.y
                
                # 2. Mostrar Información de la Tabla
                st.success(f"✅ Archivo cargado correctamente. Contiene **{len(gdf_in)}** geometrías/polígonos.")
                
                st.markdown("#### 📋 Estructura de Campos (Atributos)")
                
                # Extraer nombres de campos y tipos de datos (ignorando la geometría)
                df_info = pd.DataFrame({
                    "Campo": gdf_in.columns,
                    "Tipo de Dato": gdf_in.dtypes.astype(str)
                })
                df_info = df_info[df_info["Campo"] != "geometry"].reset_index(drop=True)
                
                col_info1, col_info2 = st.columns([1, 2.5])
                with col_info1:
                    st.dataframe(df_info, width="stretch")
                
                with col_info2:
                    st.markdown("**Vista Previa de los Datos (Primeras 5 filas):**")
                    # Mostrar el dataframe sin la columna geometry para que sea ligero visualmente
                    df_vista = pd.DataFrame(gdf_in.drop(columns='geometry'))
                    st.dataframe(df_vista.head(), width="stretch")
                
                # 3. Conversión a Shapefile empaquetado en ZIP
                st.markdown("---")
                st.markdown("#### 📦 Exportar a Shapefile (.shp)")
                st.info("💡 **Nota:** El formato Shapefile exige que esté compuesto por varios archivos complementarios (.shp, .shx, .dbf, .prj, etc.). Te entregaremos un archivo **.zip** con todos los componentes debidamente empaquetados.")
                
                nombre_export = st.text_input("Nombre base para el archivo final:", value="Capa_Exportada")
                
                if st.button("🚀 Convertir y Empaquetar a SHP", type="primary"):
                    with st.spinner("Generando y empaquetando archivos Shapefile..."):
                        
                        # Usamos un directorio temporal para guardar los múltiples archivos del SHP
                        with tempfile.TemporaryDirectory() as tmpdir:
                            shp_path = os.path.join(tmpdir, f"{nombre_export}.shp")
                            
                            # GeoPandas exporta el SHP. Advierte si los nombres superan los 10 caracteres (limitación del formato SHP)
                            gdf_in.to_file(shp_path, driver='ESRI Shapefile')
                            
                            # Empaquetamos todo el contenido del directorio temporal en un ZIP en memoria
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                                for root, dirs, files in os.walk(tmpdir):
                                    for file in files:
                                        filepath = os.path.join(root, file)
                                        zip_file.write(filepath, arcname=file)
                            
                            st.success("✅ ¡Geometría y tabla de atributos empaquetados exitosamente!")
                            st.download_button(
                                label=f"📥 Descargar {nombre_export}.zip",
                                data=zip_buffer.getvalue(),
                                file_name=f"{nombre_export}.zip",
                                mime="application/zip"
                            )
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo GeoJSON: {str(e)}")

# =====================================================================
# PESTAÑA 5: Generador de Diccionario Maestro (Veredas)
# =====================================================================

with tab5:
    st.markdown("### 🔗 Generador de Diccionario Maestro (Veredas)")
    st.info("Cruza las bases tabulares (DANE) con las espaciales (GeoJSON) usando el Código DANE para generar el diccionario `homologacion_veredas.csv`.")

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        file_dane = st.file_uploader("1. Archivo Matriz (ej. veredas_dane.csv)", type=['csv'], key="dane_csv")
        st.caption("Debe tener columnas: `codigo_vereda`, `NOMB_MPIO`, `NOMBRE_VER`")
    with col_h2:
        file_gis = st.file_uploader("2. Archivo Espacial (ej. veredas_gisant.csv)", type=['csv'], key="gis_csv")
        st.caption("Debe tener columnas: `codigo_vereda`, `NOMB_MPIO`, `NOMBRE_VER`")

    if file_dane and file_gis:
        if st.button("🚀 Generar Diccionario de Homologación", type="primary", width="stretch"):
            with st.spinner("Realizando exorcismo de datos y cruzando bases..."):
                try:
                    # 🛡️ LECTOR MEGA-BLINDADO (Anti-BOM y Anti-Punto y Coma)
                    def leer_csv_robusto(file_obj):
                        file_obj.seek(0)
                        # Detectar separador manualmente leyendo una muestra
                        sample = file_obj.read(1000).decode('utf-8', errors='ignore')
                        sep_char = ';' if ';' in sample else ','
                        file_obj.seek(0)
                        
                        try:
                            # utf-8-sig DESTRUYE el carácter fantasma \ufeff de Excel
                            return pd.read_csv(file_obj, sep=sep_char, encoding='utf-8-sig')
                        except UnicodeDecodeError:
                            file_obj.seek(0)
                            return pd.read_csv(file_obj, sep=sep_char, encoding='latin1')

                    # 1. Leer archivos
                    df_dane = leer_csv_robusto(file_dane)
                    df_gis = leer_csv_robusto(file_gis)

                    # 2. Exorcismo de columnas (Eliminar TODO rastro de caracteres invisibles)
                    df_dane.columns = [str(c).replace('\ufeff', '').replace('\xef\xbb\xbf', '').strip() for c in df_dane.columns]
                    df_gis.columns = [str(c).replace('\ufeff', '').replace('\xef\xbb\xbf', '').strip() for c in df_gis.columns]

                    # 3. Forzar el nombre de la llave (Si dice "codigo" en algún lado, lo volvemos codigo_vereda)
                    df_dane.columns = ['codigo_vereda' if 'codigo' in c.lower() else c for c in df_dane.columns]
                    df_gis.columns = ['codigo_vereda' if 'codigo' in c.lower() else c for c in df_gis.columns]

                    # 4. Asegurar que sean strings limpios de 8 dígitos
                    df_dane['codigo_vereda'] = df_dane['codigo_vereda'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(8)
                    df_gis['codigo_vereda'] = df_gis['codigo_vereda'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(8)

                    # 5. Cruzar bases
                    df_cruce = pd.merge(df_dane, df_gis, on='codigo_vereda', suffixes=('_DANE', '_GIS'))

                    # Verificar si cruzaron
                    if df_cruce.empty:
                        st.error("❌ Los archivos se leyeron bien, pero no hay códigos DANE que coincidan. Revisa los datos de las columnas de código.")
                        st.stop()

                    # Función limpiadora interna
                    def limpiar_texto(t, municipio=""):
                        if not isinstance(t, str): return ""
                        t = str(t).upper().strip()
                        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
                        for word in [r'\bVEREDA\b', r'\bVDA\.?\b', r'\bSECTOR\b', r'\bCASERIO\b']:
                            t = re.sub(word, '', t)
                        if municipio:
                            mun = ''.join(c for c in unicodedata.normalize('NFD', str(municipio).upper()) if unicodedata.category(c) != 'Mn')
                            id_final = t + "_" + mun
                        else:
                            id_final = t
                        return re.sub(r'[^A-Z0-9_]', '', id_final)

                    # Construir los ADN
                    df_cruce['ID_TABLA'] = df_cruce.apply(lambda row: limpiar_texto(row.get('NOMBRE_VER_DANE', ''), row.get('NOMB_MPIO_DANE', '')), axis=1)
                    df_cruce['ID_MAPA'] = df_cruce.apply(lambda row: limpiar_texto(row.get('NOMBRE_VER_GIS', ''), row.get('NOMB_MPIO_GIS', '')), axis=1)

                    # Extraer rebeldes
                    df_rebeldes = df_cruce[df_cruce['ID_TABLA'] != df_cruce['ID_MAPA']]
                    df_final = df_rebeldes[['ID_TABLA', 'ID_MAPA']].drop_duplicates()

                    st.success(f"✅ ¡Éxito Total! Se cruzaron los datos y se detectaron {len(df_final)} discrepancias territoriales.")
                    st.dataframe(df_final, width="stretch")

                    # Botón de descarga
                    csv_dict = df_final.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar homologacion_veredas.csv",
                        data=csv_dict,
                        file_name="homologacion_veredas.csv",
                        mime="text/csv",
                        type="primary"
                    )
                    st.info("💡 Instrucción: Descarga este archivo y guárdalo en la carpeta `data/` de tu proyecto. El `Modelo Demográfico` lo leerá automáticamente para arreglar los mapas.")

                except Exception as e:
                    st.error(f"❌ Error interno durante el procesamiento: {e}")

# ------------------------------------------------------------------------------
# 🚀 PESTAÑA 6: GEMELO DIGITAL (CONSOLIDADOR MAESTRO DE REDES)
# ------------------------------------------------------------------------------
with tab6:
    st.header("🌧️ Gemelo Digital: Súper-Consolidador de Redes Hidrometeorológicas")
    st.markdown("""
    Este motor unifica todo tu arsenal de datos en una única base de datos coherente:
    1. Combina secuencialmente aplicando rigor científico (Prioridad: Automáticas > Recientes > Histórico).
    2. Aplica el **Bisturí Temporal 2010** para homogeneizar sensores modernos con líneas base antiguas.
    3. Levanta el **Gemelo Digital** para imputar vacíos mediante correlación espacial de vecindad (>0.65) y fases ENSO.
    """)
    
    if 'csv_fusionado_data' not in st.session_state:
        st.session_state['csv_fusionado_data'] = None
        st.session_state['fusion_resumen'] = ""
        st.session_state['fusion_preview'] = None

    # Interfaz organizada para los 5 flujos de datos posibles
    col_1, col_2 = st.columns(2)
    with col_1:
        file_maestro = st.file_uploader("🥉 3. Histórico Legado (1970-2020) [Baja Prioridad]", type=['csv'])
        file_auto_ideam = st.file_uploader("🥇 1. IDEAM Automáticas (Bot Matriz) [Alta Prioridad]", type=['csv'])
    with col_2:
        file_parche_1 = st.file_uploader("🥈 2. Transición Reciente (2010-2025) [Media Prioridad]", type=['csv'])
        file_satelital = st.file_uploader("🚀 4. Satelital Copernicus (Opcional)", type=['csv'])
        file_calibracion = st.file_uploader("📥 Matriz Calibración Copernicus (Opcional)", type=['csv'])
        
    usar_imputacion = st.checkbox("Activar Imputación Avanzada del Gemelo Digital (Espacial + ENSO)", value=True)
        
    # Exigimos los 3 archivos terrestres como mínimo para encender el motor
    if file_maestro and file_parche_1 and file_auto_ideam:
        if st.button("🔄 Ejecutar Fusión e Imputación Maestra", type="primary", width="stretch"):
            with st.spinner("1. Tejiendo la red del IDEAM (Histórica + Transición + Automática)..."):
                try:
                    # ----------------------------------------------------------
                    # 🧹 ADUANA DE DATOS: LECTURA INTELIGENTE (ESTANDARIZADA)
                    # ----------------------------------------------------------
                    def leer_csv_seguro(file_obj):
                        if file_obj is None: return None
                        file_obj.seek(0)
                        try:
                            df = pd.read_csv(file_obj, sep=None, engine='python', encoding='utf-8-sig')
                            return df
                        except Exception:
                            file_obj.seek(0)
                            return pd.read_csv(file_obj, sep=';', engine='python', encoding='latin1', on_bad_lines='skip')

                    # Ejecución de carga
                    df_m = leer_csv_seguro(file_maestro)
                    df_p1 = leer_csv_seguro(file_parche_1)
                    df_auto = leer_csv_seguro(file_auto_ideam)
                    df_sat = leer_csv_seguro(file_satelital) 

                    # ----------------------------------------------------------
                    # 🛡️ CINTURÓN DE SEGURIDAD Y ESTANDARIZACIÓN (MULTIRRED)
                    # ----------------------------------------------------------
                    import numpy as np
                    import re
                    import os

                    codigos_falsos = [999.9, 999.0, 999, 9999.9, 9999.0, 9999, -99.9, -99.0, -999.0, -9999.0, -999]
                    cols_ignorar = {'fecha', 'date', 'fecha_hora', 'datetime', 'año', 'anio', 'year', 'mes', 'month', 'dia', 'day', 'id', 'index'}
                    mes_actual_tope = pd.Timestamp.today().to_period('M').to_timestamp()

                    def detectar_columnas_estaciones(columnas):
                        """Detecta tanto códigos numéricos (IDEAM) como alfanuméricos (SIATA_446, EPM, etc.)."""
                        validas = []
                        for c in columnas:
                            c_str = str(c).replace('\ufeff', '').strip()
                            c_low = c_str.lower()
                            if c_low in cols_ignorar or c_low.startswith('unnamed'):
                                continue
                            if any(ch.isdigit() for ch in c_str):
                                validas.append(c_str)
                        return validas

                    def parsear_fechas_seguras(df_t):
                        """Parsea fechas fila por fila sin confundir DD/MM/YYYY con YYYY-MM-DD."""
                        # Si el archivo ya trae columnas 'año' y 'mes' limpias, verificarlas como respaldo
                        s_raw = df_t['fecha'].astype(str).str.replace('\ufeff', '', regex=False).str.strip()
                        es_iso = s_raw.str.match(r'^\d{4}[-/]')
                        
                        fechas = pd.Series(pd.NaT, index=df_t.index, dtype='datetime64[ns]')
                        if es_iso.any():
                            fechas.loc[es_iso] = pd.to_datetime(s_raw.loc[es_iso], format='mixed', dayfirst=False, errors='coerce')
                        if (~es_iso).any():
                            fechas.loc[~es_iso] = pd.to_datetime(s_raw.loc[~es_iso], format='mixed', dayfirst=True, errors='coerce')
                            
                        # Si existen columnas explícitas de año y mes, usarlas para corregir cualquier ambigüedad
                        cols_lower = {c.lower(): c for c in df_t.columns}
                        col_y = cols_lower.get('año') or cols_lower.get('anio') or cols_lower.get('year')
                        col_m = cols_lower.get('mes') or cols_lower.get('month')
                        if col_y and col_m:
                            y_num = pd.to_numeric(df_t[col_y], errors='coerce')
                            m_num = pd.to_numeric(df_t[col_m], errors='coerce')
                            mask_ym = y_num.between(1900, 2100) & m_num.between(1, 12)
                            if mask_ym.any():
                                fechas_ym = pd.to_datetime(
                                    y_num[mask_ym].astype(int).astype(str) + '-' +
                                    m_num[mask_ym].astype(int).astype(str).str.zfill(2) + '-01',
                                    format='%Y-%m-%d', errors='coerce'
                                )
                                fechas.loc[mask_ym] = fechas_ym
                        return fechas

                    def limpiar_dataframe_red(df_in):
                        """Limpia y estandariza un DataFrame sin perder su posición en la jerarquía."""
                        if df_in is None or df_in.empty:
                            return pd.DataFrame()

                        df_temp = df_in.copy()
                        # Limpiar BOM (\ufeff), comillas y sufijos '.0' en los nombres de columnas
                        df_temp.columns = [
                            re.sub(r'\.0$', '', str(c).replace('\ufeff', '').strip().replace('"', ''))
                            for c in df_temp.columns
                        ]

                        # Normalizar nombre de la columna de fecha (insensible a mayúsculas)
                        for c in list(df_temp.columns):
                            if c.lower() in {'fecha', 'date', 'fecha_hora', 'datetime'} and 'fecha' not in df_temp.columns:
                                df_temp.rename(columns={c: 'fecha'}, inplace=True)
                            elif c.lower() == 'fecha' and c != 'fecha':
                                df_temp.rename(columns={c: 'fecha'}, inplace=True)

                        if 'fecha' not in df_temp.columns:
                            return pd.DataFrame()

                        # Descartar filas de resumen de Excel ("Promedio", "Anual", "max", "min", etc.)
                        s_fecha = df_temp['fecha'].astype(str).str.strip()
                        mask_fecha_valida = s_fecha.str.contains(r'\d{4}', regex=True, na=False)
                        df_temp = df_temp[mask_fecha_valida].copy()
                        if df_temp.empty:
                            return pd.DataFrame()

                        # 🔥 LECTURA VECTORIZADA DE FECHAS (Inmune a mezcla de formatos)
                        df_temp['fecha'] = parsear_fechas_seguras(df_temp)
                        df_temp.dropna(subset=['fecha'], inplace=True)
                        if df_temp.empty:
                            return pd.DataFrame()

                        # Normalizar siempre al día 1 de cada mes y cortar fechas futuras (> mes actual)
                        df_temp['fecha'] = df_temp['fecha'].dt.to_period('M').dt.to_timestamp()
                        df_temp = df_temp[df_temp['fecha'] <= mes_actual_tope].copy()
                        if df_temp.empty:
                            return pd.DataFrame()

                        cols_est = detectar_columnas_estaciones(df_temp.columns)
                        if not cols_est:
                            return pd.DataFrame()

                        for col in cols_est:
                            if df_temp[col].dtype == object:
                                df_temp[col] = df_temp[col].astype(str).str.replace(',', '.', regex=False).str.strip()
                            df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce')

                            # 🛡️ BLINDAJE MENSUAL: Mata códigos de error (-999), ceros falsos (0.0) y diluvios irreales (>1500)
                            df_temp.loc[
                                df_temp[col].isin(codigos_falsos) |
                                (df_temp[col] <= 0) |
                                (df_temp[col] > 1500),
                                col
                            ] = np.nan

                        df_temp = df_temp.groupby('fecha')[cols_est].sum(min_count=1)
                        return df_temp.sort_index()

                    # Desempaquetado seguro (respeta la posición aunque falte algún archivo)
                    df_m_clean = limpiar_dataframe_red(df_m)
                    df_p1_clean = limpiar_dataframe_red(df_p1)
                    df_auto_clean = limpiar_dataframe_red(df_auto)
                    df_sat_clean = limpiar_dataframe_red(df_sat)

                    # ==========================================================
                    # 🌍 PASO 1: CONSOLIDACIÓN SECUENCIAL CIENTÍFICA
                    # ==========================================================
                    # 🥇 PRIORIDAD MÁXIMA a las Automáticas / SIATA (df_auto_clean)
                    # 🥈 PRIORIDAD MEDIA al Parche 2010-2025 (df_p1_clean)
                    # 🥉 PRIORIDAD BAJA al Histórico viejo (df_m_clean)
                    df_terrestre = pd.DataFrame()
                    for df_capa in [df_auto_clean, df_p1_clean, df_m_clean]:
                        if not df_capa.empty:
                            df_terrestre = df_capa.copy() if df_terrestre.empty else df_terrestre.combine_first(df_capa)

                    cols_totales = detectar_columnas_estaciones(df_terrestre.columns)
                    limites_nacimiento = {}
                    for col in cols_totales:
                        datos_validos = df_terrestre[col].dropna()
                        fecha_min_dato = datos_validos.index.min() if not datos_validos.empty else None
                        # Ninguna estación SIATA puede nacer antes de 2010-01-01 (inicio oficial de la red)
                        if str(col).upper().startswith('SIATA_') and pd.notna(fecha_min_dato):
                            fecha_min_dato = max(fecha_min_dato, pd.Timestamp('2010-01-01'))
                        limites_nacimiento[col] = fecha_min_dato

                    # ==========================================================
                    # 🛡️ PASO 2: BISTURÍ TEMPORAL (INMUNIZADO)
                    # ==========================================================
                    AÑO_RUPTURA = 2010
                    log_homogeneidad = 0
                    if not df_terrestre.empty:
                        df_terrestre.index = pd.to_datetime(df_terrestre.index)

                        for col in cols_totales:
                            # No aplicar reescalado pre-2010 a estaciones de la red SIATA
                            if str(col).upper().startswith('SIATA_'):
                                continue

                            serie_col = df_terrestre[col].dropna()
                            serie_hist = serie_col[serie_col.index.year < AÑO_RUPTURA]
                            serie_reciente = serie_col[serie_col.index.year >= AÑO_RUPTURA]

                            if len(serie_hist) > 24 and len(serie_reciente) > 12:
                                media_hist = serie_hist.mean()
                                media_reciente = serie_reciente.mean()

                                if pd.notna(media_hist) and pd.notna(media_reciente) and media_reciente > 0:
                                    factor = media_hist / media_reciente
                                    if 0.5 < factor < 2.0:
                                        df_terrestre.loc[df_terrestre.index.year >= AÑO_RUPTURA, col] *= factor
                                        log_homogeneidad += 1

                    st.success(f"⚖️ Homogeneidad Terrestre: Se calibró el bloque moderno de {log_homogeneidad} estaciones.")

                    df_final = df_terrestre.copy()
                    mensaje_estatus = "Ecosistema unificado basado en redes terrestres priorizadas (IDEAM / SIATA)."

                    # ==========================================================
                    # 🛰️ PASO 3: INGESTIÓN SATELITAL (OPCIONAL)
                    # ==========================================================
                    if not df_sat_clean.empty:
                        st.info("🛰️ Datos satelitales detectados. Integrando capa adicional...")
                        df_final = df_sat_clean.copy() if df_final.empty else df_final.combine_first(df_sat_clean)
                        mensaje_estatus = "Ecosistema unificado Híbrido (Redes Terrestres + Copernicus)."

                    df_final = df_final[df_final.index <= pd.Timestamp.today()]

                    # ==========================================================
                    # 🧩 PASO 4: GEMELO DIGITAL (IMPUTACIÓN ESPACIAL + ENSO)
                    # ==========================================================
                    cols_estaciones = detectar_columnas_estaciones(df_final.columns)

                    if usar_imputacion and cols_estaciones:
                        with st.spinner("2. Levantando Gemelo Digital: Interconectando estaciones..."):
                            from modules import climate_api

                            Q1_mes = df_final.groupby(df_final.index.month)[cols_estaciones].transform(lambda x: x.quantile(0.25))
                            Q3_mes = df_final.groupby(df_final.index.month)[cols_estaciones].transform(lambda x: x.quantile(0.75))
                            techo_mensual = Q3_mes + (3.0 * (Q3_mes - Q1_mes))

                            for col in cols_estaciones:
                                limite_col = techo_mensual[col].clip(lower=450.0).fillna(800.0)
                                df_final.loc[df_final[col] > limite_col, col] = np.nan

                            MIN_DATOS_REALES = 24
                            conteo_reales = df_final[cols_estaciones].notna().sum()
                            estaciones_robustas = conteo_reales[conteo_reales >= MIN_DATOS_REALES].index.tolist()

                            if estaciones_robustas:
                                matriz_corr = df_final[estaciones_robustas].corr(method='pearson')
                                climatologia_mensual = df_final.groupby(df_final.index.month)[estaciones_robustas].mean()
                                UMBRAL_CORRELACION = 0.65

                                df_imputado_espacial = df_final[cols_estaciones].copy()

                                for estacion in estaciones_robustas:
                                    registros_vacios = df_final[df_final[estacion].isna()].index
                                    if len(registros_vacios) > 0:
                                        vecinas_ordenadas = matriz_corr[estacion].drop(estacion, errors='ignore').sort_values(ascending=False)
                                        vecinas_validas = vecinas_ordenadas[vecinas_ordenadas >= UMBRAL_CORRELACION].index.tolist()

                                        for fecha_idx in registros_vacios:
                                            mes_actual = fecha_idx.month
                                            for vecina in vecinas_validas:
                                                valor_vecina = df_final.loc[fecha_idx, vecina]
                                                if pd.notna(valor_vecina):
                                                    media_target = climatologia_mensual.loc[mes_actual, estacion]
                                                    media_vecina = climatologia_mensual.loc[mes_actual, vecina]
                                                    if pd.notna(media_vecina) and media_vecina > 0 and pd.notna(media_target):
                                                        df_imputado_espacial.loc[fecha_idx, estacion] = valor_vecina * (media_target / media_vecina)
                                                        break

                                df_final[cols_estaciones] = df_imputado_espacial

                                # Respaldo Climático con Fase ENSO (Niño / Niña / Neutro)
                                df_clima_vivo = climate_api.get_live_oni_data()
                                if df_clima_vivo is not None and not df_clima_vivo.empty:
                                    df_oni = df_clima_vivo.copy()
                                    if 'fecha' in df_oni.columns:
                                        df_oni['fecha'] = pd.to_datetime(df_oni['fecha'], errors='coerce').dt.to_period('M').dt.to_timestamp()
                                        df_oni.set_index('fecha', inplace=True)
                                    df_oni = df_oni[~df_oni.index.duplicated(keep='first')]

                                    if 'fase_enso' in df_oni.columns:
                                        df_final = df_final.join(df_oni[['fase_enso']], how='left')
                                        df_promedios_enso = df_final.groupby([df_final.index.month, 'fase_enso'])[estaciones_robustas].transform('mean')
                                        df_final[estaciones_robustas] = df_final[estaciones_robustas].fillna(df_promedios_enso)
                                        df_final.drop(columns=['fase_enso'], inplace=True)

                                df_promedios_mensuales = df_final.groupby(df_final.index.month)[estaciones_robustas].transform('mean')
                                df_final[estaciones_robustas] = df_final[estaciones_robustas].fillna(df_promedios_mensuales)

                    # 🛡️ CORTAFUEGOS DE NACIMIENTO
                    if cols_estaciones:
                        for col in cols_estaciones:
                            inicio = limites_nacimiento.get(col)
                            if pd.notna(inicio):
                                df_final.loc[df_final.index < inicio, col] = np.nan
                        df_final.dropna(subset=cols_estaciones, how='all', inplace=True)

                    df_final[cols_estaciones] = df_final[cols_estaciones].round(2)
                    df_final = df_final.sort_index().reset_index()
                    df_final['fecha'] = pd.to_datetime(df_final['fecha']).dt.strftime('%Y-%m-%d')

                    st.session_state['csv_fusionado_data'] = df_final.to_csv(sep=';', decimal=',', index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.session_state['fusion_resumen'] = f"✅ Operación Exitosa ({len(cols_estaciones)} estaciones integradas). {mensaje_estatus}"
                    st.session_state['fusion_preview'] = df_final.tail(10)

                except Exception as e:
                    st.error(f"❌ Ocurrió un error procesando los archivos: {e}")

    # Renderizado
    if st.session_state.get('csv_fusionado_data') is not None:
        st.markdown("---")
        st.success("✅ ¡Súper-Matriz Unificada Generada con Éxito!")
        st.info(st.session_state['fusion_resumen'])
        st.dataframe(st.session_state['fusion_preview'], use_container_width=True)

        st.download_button(
            label="📥 Descargar Matriz Definitiva Total (Apta para Supabase)",
            data=st.session_state['csv_fusionado_data'],
            file_name="DatosPptnmes_Maestro_Integral.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True
        )
        
# =====================================================================
# 📡 PESTAÑA 7: PUENTE SIATA (GESTIÓN INTEGRAL DE ESTACIONES Y LLUVIA)
# =====================================================================
with tab7:
    st.header("📡 Centro de Integración SIATA -> Supabase")
    st.markdown(
        "Flujo depurado en 3 pasos para registrar el catálogo oficial de estaciones con geometría PostGIS, "
        "inyectar la matriz histórica consolidada (2010–2026) y descargar el último trimestre."
    )

    # -------------------------------------------------------------------------
    # 📍 PASO 1: INYECTAR / ACTUALIZAR CATÁLOGO DE ESTACIONES SIATA EN SUPABASE
    # -------------------------------------------------------------------------
    st.subheader("📍 Paso 1: Sincronizar Catálogo Oficial de Estaciones SIATA")
    st.markdown(
        "Sube tu archivo **`Estaciones_pluviometro.csv`** (o `.json`/`.geojson`). "
        "Se asignará el prefijo `SIATA_`, se normalizarán los municipios sin tildes (`MEDELLIN`), "
        "se añadirá la estación histórica `SIATA_287` y se creará la geometría PostGIS (`geom`)."
    )

    archivo_cat_est = st.file_uploader(
        "Sube Estaciones_pluviometro.csv (o archivo GeoJSON del SIATA):",
        type=['csv', 'json', 'geojson'],
        key="siata_cat_oficial"
    )

    if st.button("💉 Sincronizar Estaciones SIATA en Supabase (Tabla: estaciones)", type="primary", use_container_width=True):
        if archivo_cat_est is None:
            st.error("🚨 Primero sube el archivo 'Estaciones_pluviometro.csv' en la caja de arriba.")
        else:
            with st.spinner("Sincronizando estaciones y geometrías PostGIS en Supabase..."):
                try:
                    import pandas as pd
                    import geopandas as gpd
                    import unicodedata
                    from modules.db_manager import get_engine

                    def limpiar_texto_mpio(txt):
                        if pd.isna(txt):
                            return "MEDELLIN"
                        s = ''.join(
                            c for c in unicodedata.normalize('NFD', str(txt).strip())
                            if unicodedata.category(c) != 'Mn'
                        )
                        return s.upper().replace("'", "''")

                    nombre_f = archivo_cat_est.name.lower()
                    if nombre_f.endswith('.csv'):
                        df_in = pd.read_csv(archivo_cat_est, sep=None, engine='python')
                        df_in.columns = [str(c).replace('\ufeff', '').strip() for c in df_in.columns]
                        col_cod = next(c for c in df_in.columns if 'cod' in c.lower() or 'cód' in c.lower() or 'id' in c.lower())
                        col_nom = next((c for c in df_in.columns if 'nom' in c.lower()), None)
                        col_mun = next((c for c in df_in.columns if 'mun' in c.lower() or 'ubic' in c.lower()), None)
                        col_lat = next(c for c in df_in.columns if 'lat' in c.lower())
                        col_lon = next(c for c in df_in.columns if 'lon' in c.lower())

                        df_up = pd.DataFrame({
                            'cod_num': df_in[col_cod].astype(str).str.split('.').str[0].str.strip(),
                            'nombre': df_in[col_nom] if col_nom else "Estación SIATA",
                            'municipio': df_in[col_mun] if col_mun else "MEDELLIN",
                            'latitud': pd.to_numeric(df_in[col_lat].astype(str).str.replace(',', '.'), errors='coerce'),
                            'longitud': pd.to_numeric(df_in[col_lon].astype(str).str.replace(',', '.'), errors='coerce')
                        })
                    else:
                        gdf_in = gpd.read_file(archivo_cat_est)
                        col_cod = next(c for c in gdf_in.columns if 'cod' in c.lower() or 'id' in c.lower())
                        df_up = pd.DataFrame({
                            'cod_num': gdf_in[col_cod].astype(str).str.split('.').str[0].str.strip(),
                            'nombre': gdf_in.get('nombre', 'Estación SIATA'),
                            'municipio': gdf_in.get('ubicacion', 'MEDELLIN'),
                            'latitud': gdf_in.geometry.y,
                            'longitud': gdf_in.geometry.x
                        })

                    # Eliminar duplicados (ej. estación 842) y coordenadas vacías
                    df_up = df_up.dropna(subset=['latitud', 'longitud']).drop_duplicates(subset=['cod_num'], keep='first').copy()
                    df_up['id_estacion'] = 'SIATA_' + df_up['cod_num']

                    # Rescatar estación histórica SIATA_287 (presente en los ZIPs 2018-2023)
                    if 'SIATA_287' not in df_up['id_estacion'].values:
                        df_287 = pd.DataFrame([{
                            'cod_num': '287',
                            'id_estacion': 'SIATA_287',
                            'nombre': 'Estación SIATA 287 (Santa Elena)',
                            'municipio': 'MEDELLIN',
                            'latitud': 6.250400,
                            'longitud': -75.544900
                        }])
                        df_up = pd.concat([df_up, df_287], ignore_index=True)

                    mpios_aburra = {
                        'MEDELLIN', 'BELLO', 'ITAGUI', 'ENVIGADO', 'SABANETA',
                        'LA ESTRELLA', 'CALDAS', 'COPACABANA', 'GIRARDOTA', 'BARBOSA'
                    }

                    sql_queries = []
                    for _, row in df_up.iterrows():
                        id_est = str(row['id_estacion']).strip()
                        nom = str(row['nombre']).strip().replace("'", "''")
                        mun = limpiar_texto_mpio(row['municipio'])
                        subreg = 'VALLE DE ABURRÁ' if mun in mpios_aburra else 'ANTIOQUIA (EXTERNA)'
                        lon = float(row['longitud'])
                        lat = float(row['latitud'])

                        # ON CONFLICT DO UPDATE garantiza que si ya existían con tilde o sin geom, queden corregidas
                        q = f"""
                        INSERT INTO estaciones 
                        (id_estacion, nombre, longitud, latitud, municipio, departamento, subregion, geom)
                        VALUES 
                        ('{id_est}', '{nom}', {lon}, {lat}, '{mun}', 'ANTIOQUIA', '{subreg}', ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326))
                        ON CONFLICT (id_estacion) DO UPDATE SET
                            nombre = EXCLUDED.nombre,
                            longitud = EXCLUDED.longitud,
                            latitud = EXCLUDED.latitud,
                            municipio = EXCLUDED.municipio,
                            subregion = EXCLUDED.subregion,
                            geom = EXCLUDED.geom;
                        """
                        sql_queries.append(q)

                    engine = get_engine()
                    raw_conn = engine.raw_connection()
                    try:
                        cursor = raw_conn.cursor()
                        procesadas = 0
                        for query in sql_queries:
                            cursor.execute(query)
                            procesadas += 1
                        raw_conn.commit()
                        st.cache_data.clear()
                        st.success(f"✅ ¡Catálogo Sincronizado! {procesadas} estaciones del SIATA insertadas/actualizadas con geometría PostGIS.")
                        st.balloons()
                    finally:
                        cursor.close()
                        raw_conn.close()

                except Exception as e:
                    st.error(f"🚨 Error sincronizando estaciones: {e}")

    # -------------------------------------------------------------------------
    # 🌧️ PASO 2: INYECTAR MATRIZ DE LLUVIA CONSOLIDADA A SUPABASE (ALTA VELOCIDAD)
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("🌧️ Paso 2: Inyectar Matriz Consolidada de Lluvia a Supabase")
    st.markdown(
        "Sube tu archivo **`Datos_SIATA_Multi_ZIP_Consolidado (3).csv`** (o el CSV del último trimestre). "
        "El sistema filtra falsos ceros (`0.0 mm`), bloquea fechas futuras e inyecta por lotes."
    )

    archivo_csv_siata = st.file_uploader("Sube el CSV de lluvia consolidada:", type=['csv'], key="up_lluvia_consolidada")

    if st.button("💉 Inyectar Lluvia a Supabase (Tabla: precipitacion)", type="primary", use_container_width=True):
        if archivo_csv_siata is None:
            st.error("🚨 Sube el archivo CSV primero.")
        else:
            with st.spinner("Limpiando serie, verificando catálogo e inyectando por lotes..."):
                try:
                    import pandas as pd
                    from modules.db_manager import get_engine

                    # 1. Lectura limpia (elimina BOM y columnas Unnamed)
                    df_csv = pd.read_csv(archivo_csv_siata, sep=';', decimal=',', encoding='utf-8-sig')
                    df_csv.columns = [str(c).replace('\ufeff', '').strip() for c in df_csv.columns]
                    df_csv = df_csv.loc[:, ~df_csv.columns.str.contains('^Unnamed', case=False)]

                    # 2. Validar fechas al día 1 de cada mes y cortar fechas futuras
                    df_csv['fecha_dt'] = pd.to_datetime(df_csv['fecha'], errors='coerce')
                    df_csv = df_csv.dropna(subset=['fecha_dt'])
                    mes_tope = pd.Timestamp.today().to_period('M').to_timestamp()
                    df_csv = df_csv[(df_csv['fecha_dt'] >= pd.Timestamp('2010-01-01')) & (df_csv['fecha_dt'] <= mes_tope)].copy()
                    df_csv['fecha'] = df_csv['fecha_dt'].dt.strftime('%Y-%m-01')
                    df_csv = df_csv.drop(columns=['fecha_dt'])

                    # 3. Transformar de Ancho a Largo
                    df_long = df_csv.melt(id_vars=['fecha'], var_name='id_estacion', value_name='valor')
                    df_long['valor'] = pd.to_numeric(df_long['valor'].astype(str).str.replace(',', '.'), errors='coerce')
                    df_long = df_long.dropna(subset=['valor'])

                    # 4. Filtro vital: solo lluvias reales (> 0 mm y <= 1500 mm/mes) para no inyectar sensores obstruidos (0.0)
                    df_long = df_long[(df_long['valor'] > 0) & (df_long['valor'] <= 1500.0)].copy()
                    df_long['origen'] = 'SIATA (Consolidado Histórico)'

                    engine = get_engine()
                    df_catalogo = pd.read_sql("SELECT id_estacion FROM estaciones", engine)
                    estaciones_validas = set(df_catalogo['id_estacion'].astype(str).tolist())
                    df_long = df_long[df_long['id_estacion'].isin(estaciones_validas)].drop_duplicates(subset=['fecha', 'id_estacion'])

                    if df_long.empty:
                        st.warning("⚠️ No hay datos válidos para inyectar. Asegúrate de haber ejecutado el Paso 1 primero.")
                    else:
                        raw_conn = engine.raw_connection()
                        try:
                            cursor = raw_conn.cursor()
                            pares_borrar = [f"('{r['fecha']}', '{r['id_estacion']}')" for _, r in df_long.iterrows()]
                            filas_insertar = [f"('{r['fecha']}', '{r['id_estacion']}', {round(float(r['valor']), 2)}, '{r['origen']}')" for _, r in df_long.iterrows()]

                            chunk_size = 1500
                            for i in range(0, len(pares_borrar), chunk_size):
                                c_del = pares_borrar[i:i+chunk_size]
                                c_ins = filas_insertar[i:i+chunk_size]
                                cursor.execute(f"DELETE FROM precipitacion WHERE (fecha, id_estacion) IN ({','.join(c_del)});")
                                cursor.execute(f"INSERT INTO precipitacion (fecha, id_estacion, valor, origen) VALUES {','.join(c_ins)};")

                            raw_conn.commit()
                            st.cache_data.clear()
                            st.success(f"✅ ¡Inyección Supersónica Completada! Se cargaron {len(filas_insertar)} registros mensuales limpios en Supabase.")
                            st.balloons()
                        finally:
                            cursor.close()
                            raw_conn.close()

                except Exception as e:
                    st.error(f"🚨 Error en la inyección de lluvia: {e}")

    # -------------------------------------------------------------------------
    # 📡 PASO 3: DESCARGA AUTOMÁTICA DEL ÚLTIMO TRIMESTRE (PUENTE SIATA API)
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📡 Paso 3: Descarga Automática de Meses Recientes (Último Trimestre)")
    st.markdown(
        "Extrae directamente tus estaciones `SIATA_` registradas en Supabase, consulta la lluvia "
        "de los meses posteriores a junio de 2026 y genera el archivo CSV listo para inyectar en el Paso 2."
    )

    meses_recientes = st.slider("📅 Meses recientes a descargar (5 = Julio a Noviembre 2026):", min_value=1, max_value=6, value=5)

    if st.button("🚀 Descargar Lluvia del Último Trimestre (SIATA)", type="primary", use_container_width=True):
        import importlib
        from modules import siata_api
        importlib.reload(siata_api)
        from modules.db_manager import get_engine
        from sqlalchemy import text
        import geopandas as gpd

        with st.spinner("1. Leyendo catálogo de estaciones SIATA desde Supabase..."):
            try:
                engine = get_engine()
                with engine.connect() as conn:
                    query = """
                        SELECT id_estacion as codigo, nombre, latitud as lat, longitud as lon, geom 
                        FROM estaciones 
                        WHERE geom IS NOT NULL AND UPPER(id_estacion) LIKE 'SIATA_%'
                    """
                    gdf_db_siata = gpd.read_postgis(text(query), conn, geom_col="geom")
                    if gdf_db_siata.crs is None:
                        gdf_db_siata = gdf_db_siata.set_crs("EPSG:4326")
            except Exception as e:
                st.error(f"🚨 Error leyendo 'estaciones' en Supabase: {e}")
                st.stop()

        if gdf_db_siata.empty:
            st.warning("⚠️ No se encontraron estaciones 'SIATA_' con geometría en Supabase. Ejecuta primero el Paso 1.")
            st.stop()

        with st.spinner(f"2. Descargando y consolidando los últimos {meses_recientes} meses para {len(gdf_db_siata)} estaciones..."):
            dict_homologacion = siata_api.homologar_por_proximidad(gdf_db_siata)
            df_lluvia_siata = siata_api.extraer_lluvia_reciente_siata(
                dict_homologacion,
                meses_atras=int(meses_recientes),
                gdf_estaciones=gdf_db_siata
            )

            if not df_lluvia_siata.empty:
                st.success(f"✅ ¡Últimos {len(df_lluvia_siata)} meses consolidados con éxito ({df_lluvia_siata['fecha'].min()} a {df_lluvia_siata['fecha'].max()}) para {len(dict_homologacion)} estaciones!")
                st.dataframe(df_lluvia_siata, use_container_width=True)
                csv_siata = df_lluvia_siata.to_csv(sep=';', decimal=',', index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    label="📥 Descargar CSV del Último Trimestre (Subir en Paso 2 para inyectar)",
                    data=csv_siata,
                    file_name="Datos_SIATA_Ultimo_Trimestre.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True
                )
            else:
                st.warning("No se obtuvieron registros nuevos. Verifica tu conexión a internet.")

# =====================================================================
# 🧹 QUIRÓFANO SQL: MANTENIMIENTO Y DEPURACIÓN DE SUPABASE - Tabla Precipitacion
# =====================================================================
st.markdown("---")
with st.expander("🧹 Quirófano SQL: Depuración Profunda de Supabase (Tabla `precipitacion`)", expanded=False):
    st.markdown(
        "Ejecuta limpieza directa en PostgreSQL para eliminar valores imposibles, fechas futuras, "
        "registros SIATA previos a 2010 y duplicados exactos (`ctid`)."
    )

    col_sql1, col_sql2 = st.columns(2)

    with col_sql1:
        if st.button("🧨 Ejecutar Depuración Integral de Anomalías y Duplicados", type="primary", use_container_width=True):
            from modules.db_manager import get_engine
            from sqlalchemy import text

            try:
                engine = get_engine()
                with engine.begin() as conn:
                    res_anomalias = conn.execute(text("""
                        DELETE FROM precipitacion
                        WHERE valor < 0 OR valor > 1500 OR valor IN (999, 999.9, 9999, -999, -99.9);
                    """))
                    res_futuras = conn.execute(text("""
                        DELETE FROM precipitacion WHERE fecha > CURRENT_DATE;
                    """))
                    res_hist = conn.execute(text("""
                        DELETE FROM precipitacion
                        WHERE UPPER(id_estacion) LIKE 'SIATA_%' AND fecha < '2010-01-01';
                    """))
                    res_duplicados = conn.execute(text("""
                        DELETE FROM precipitacion
                        WHERE ctid IN (
                            SELECT ctid
                            FROM (
                                SELECT ctid, ROW_NUMBER() OVER(PARTITION BY id_estacion, fecha) AS fila
                                FROM precipitacion
                            ) t
                            WHERE t.fila > 1
                        );
                    """))
                    total = (
                        res_anomalias.rowcount
                        + res_futuras.rowcount
                        + res_hist.rowcount
                        + res_duplicados.rowcount
                    )

                st.cache_data.clear()
                st.success(f"✅ ¡Cirugía completada! Se eliminaron {total} registros corruptos o redundantes.")
                st.info(
                    f"- **{res_anomalias.rowcount}** valores imposibles / códigos de error.\n"
                    f"- **{res_futuras.rowcount}** fechas futuras fantasmas.\n"
                    f"- **{res_hist.rowcount}** registros SIATA previos a 2010.\n"
                    f"- **{res_duplicados.rowcount}** filas duplicadas exactas."
                )
            except Exception as e:
                st.error(f"Error en la depuración SQL: {e}")

    with col_sql2:
        confirmar_siata = st.checkbox("⚠️ Confirmar borrado total de registros SIATA en `precipitacion`")
        if st.button("🗑️ Borrar ÚNICAMENTE datos del SIATA", disabled=not confirmar_siata, use_container_width=True):
            from modules.db_manager import get_engine
            from sqlalchemy import text

            try:
                engine = get_engine()
                with engine.begin() as conn:
                    res = conn.execute(text("""
                        DELETE FROM precipitacion
                        WHERE UPPER(id_estacion) LIKE 'SIATA_%';
                    """))

                st.cache_data.clear()
                st.success(f"✅ Se borraron {res.rowcount} registros del SIATA. Los datos del IDEAM están a salvo.")
            except Exception as e:
                st.error(f"Error en el borrado: {e}")