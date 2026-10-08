# modules/geomorfologia_tools.py

import streamlit as st
import os

def render_motor_hidrologico(gdf_zona):
    """Motor hidrológico blindado: Rastreador seguro + Bypass de CRS."""
    import streamlit as st
    import os
    import pyproj
    
    # 🛡️ Vacuna PROJ
    os.environ["PROJ_DATA"] = pyproj.datadir.get_data_dir()
    os.environ["PROJ_LIB"] = pyproj.datadir.get_data_dir()
    os.environ["PROJ_NETWORK"] = "ON"
    
    col_btn1, col_btn2 = st.columns([1, 2])
    with col_btn1:
        sensibilidad = st.slider("Sensibilidad de Drenaje:", min_value=50, max_value=99, value=85, step=5, key="geom_slider")
        
    with col_btn2:
        st.write("") 
        st.write("") 
        if st.button("🌊 Generar Red Hídrica Aquí", width="stretch"):
            with st.spinner("Procesando topografía con Bypass Local Extremo..."):
                try:
                    import rasterio
                    import numpy as np
                    from rasterio.mask import mask
                    import geopandas as gpd
                    from scipy.ndimage import gaussian_filter
                    from rasterio.features import shapes
                    from shapely.geometry import shape, LineString, Polygon
                    
                    from modules.config import Config
                    # 🚀 FIX: RESTAURAMOS EL DESCARGADOR SEGURO
                    from modules.hydro_physics import download_raster_secure
                    
                    # Usamos la herramienta segura para ubicar o descargar el raster
                    safe_path = download_raster_secure(Config.DEM_FILE_PATH)
                    
                    # Ahora sí validamos que la ruta segura exista
                    if safe_path and os.path.exists(safe_path) and gdf_zona is not None:
                        # 1. Forzamos CRS base a WGS84
                        if getattr(gdf_zona, 'crs', None) is None:
                            gdf_zona = gdf_zona.set_crs("EPSG:4326")
                            
                        # 2. BYPASS ABSOLUTO: Obligamos matemáticamente a proyectar al Origen Nacional (9377)
                        try:
                            gdf_raster_crs = gdf_zona.to_crs("EPSG:9377")
                        except:
                            gdf_raster_crs = gdf_zona.to_crs(epsg=9377)
                            
                        # 3. Buffer de seguridad (1500 metros)
                        gdf_buffered = gdf_raster_crs.copy()
                        gdf_buffered['geometry'] = gdf_buffered.buffer(1500)
                        
                        # 4. Recorte limpio
                        with rasterio.open(safe_path) as src:
                            try:
                                out_image, out_transform = mask(src, gdf_buffered.geometry.values, crop=True)
                            except ValueError:
                                from shapely.geometry import box
                                bounds = src.bounds
                                dem_box = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
                                safe_geom = gdf_buffered.intersection(dem_box)
                                safe_geom = safe_geom[~safe_geom.is_empty]
                                out_image, out_transform = mask(src, safe_geom.geometry.values, crop=True)
                                
                            dem_clean = out_image[0]
                        
                        # 5. Motor Topográfico TPI
                        dem_safe = np.where((dem_clean <= 0) | (dem_clean == -9999.0) | np.isnan(dem_clean), np.nan, dem_clean)
                        dem_filled = np.nan_to_num(dem_safe, nan=np.nanmean(dem_safe))
                        dem_smooth = gaussian_filter(dem_filled, sigma=4)
                        tpi = dem_smooth - dem_safe
                        
                        if np.any(tpi > 0):
                            tpi_threshold = np.nanpercentile(tpi[tpi > 0], sensibilidad)
                            mask_rivers = (tpi > tpi_threshold).astype(np.uint8)
                            
                            geoms = []
                            for geom, val in shapes(mask_rivers, mask=(mask_rivers == 1), transform=out_transform):
                                poly = shape(geom)
                                if isinstance(poly, Polygon) and poly.exterior:
                                    line = LineString(poly.exterior.coords).simplify(10.0)
                                    if line.length > 10.0:
                                        geoms.append(line)
                                        
                            if geoms:
                                r_raw = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:9377")
                                r_clip = gpd.clip(r_raw, gdf_raster_crs)
                                r_clip = r_clip[r_clip.geometry.type.isin(['LineString', 'MultiLineString'])]
                                
                                if not r_clip.empty:
                                    r_clip['longitud_km'] = (r_clip.length / 2) / 1000.0 
                                    r_clip['Orden_Strahler'] = np.where(
                                        r_clip['longitud_km'] > 2.0, 4, 
                                        np.where(r_clip['longitud_km'] > 1.0, 3, 
                                        np.where(r_clip['longitud_km'] > 0.4, 2, 1))
                                    )
                                    st.session_state['gdf_rios'] = r_clip
                                    st.success("✅ Red hídrica extraída exitosamente.")
                                    st.rerun() 
                                else:
                                    st.warning("⚠️ Los ríos quedaron fuera del límite.")
                            else:
                                st.warning("⚠️ No se detectaron valles.")
                        else:
                            st.warning("⚠️ Terreno plano.")
                    else:
                        st.error("❌ No se encontró el archivo DEM local en la ruta configurada.")
                except Exception as e:
                    import traceback
                    st.error(f"Error crítico en el motor local: {e}")
                    with st.expander("🛠️ Detalles técnicos"):
                        st.code(traceback.format_exc())