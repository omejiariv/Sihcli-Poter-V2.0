# modules/geomorfologia_tools.py

import streamlit as st
import os

def render_motor_hidrologico(gdf_zona):
    """Motor hidrológico a prueba de fallos mediante Índice de Posición Topográfica (TPI)."""
    
    col_btn1, col_btn2 = st.columns([1, 2])
    with col_btn1:
        sensibilidad = st.slider(
            "Sensibilidad de Drenaje:", 
            min_value=50, max_value=99, value=85, step=5,
            help="Mayor sensibilidad = Solo ríos principales. Menor sensibilidad = Muchos riachuelos.",
            key="geom_slider"
        )
        
    with col_btn2:
        st.write("") 
        st.write("") 
        if st.button("🌊 Generar Red Hídrica Aquí", use_container_width=True):
            with st.spinner("Encendiendo motor topográfico (Modo Blindado Scipy)..."):
                try:
                    import rasterio
                    import numpy as np
                    from rasterio.mask import mask
                    import geopandas as gpd
                    from scipy.ndimage import gaussian_filter
                    from rasterio.features import shapes
                    from shapely.geometry import shape, LineString, Polygon
                    
                    from modules.config import Config
                    from modules.hydro_physics import download_raster_secure
                    
                    DEM_PATH = Config.DEM_FILE_PATH
                    safe_path = download_raster_secure(DEM_PATH)
                    
                    if safe_path and gdf_zona is not None:
                        # 🚀 FIX 1: EFECTO ANTI-BORDE. Le damos un buffer de 1.5 km (aprox) para que TPI no confunda el borde con un río.
                        geom_expandida = gdf_zona.copy()
                        geom_expandida = geom_expandida.to_crs(epsg=3116)
                        geom_expandida['geometry'] = geom_expandida.buffer(1500) 
                        geom_expandida = geom_expandida.to_crs(epsg=4326)
                        
                        with rasterio.open(safe_path) as src:
                            try:
                                # Recortamos con la zona EXPANDIDA
                                out_image, out_transform = mask(src, geom_expandida.to_crs(src.crs).geometry.values, crop=True)
                            except ValueError:
                                from shapely.geometry import box
                                bounds = src.bounds
                                dem_box = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
                                safe_geom = geom_expandida.to_crs(src.crs).intersection(dem_box)
                                safe_geom = safe_geom[~safe_geom.is_empty]
                                
                                if safe_geom.empty:
                                    st.error("❌ El área está completamente fuera del mapa de elevación disponible.")
                                    st.stop()
                                out_image, out_transform = mask(src, safe_geom.geometry.values, crop=True)
                                
                            out_meta = src.meta.copy()
                            dem_clean = out_image[0]
                        
                            # 🚀 FIX 2: CURA DE ESTALACTITAS (Se ignora basura negativa o ceros)
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
                                        # Devolvemos LÍNEAS simplificadas para PyDeck
                                        line = LineString(poly.exterior.coords).simplify(0.001)
                                        if line.length > 0.001:
                                            geoms.append(line)
                                            
                                if geoms:
                                    r_raw = gpd.GeoDataFrame(geometry=geoms, crs=out_meta['crs'])
                                    # 🚀 AHORA SÍ: Recortamos los ríos hallados al tamaño exacto de la cuenca original
                                    r_clip = gpd.clip(r_raw, gdf_zona.to_crs(out_meta['crs']))
                                    
                                    # Limpiamos los fragmentos sueltos que quedan en el borde exacto
                                    r_clip = r_clip[r_clip.geometry.type.isin(['LineString', 'MultiLineString'])]
                                    
                                    if not r_clip.empty:
                                        r_clip_m = r_clip.to_crs(epsg=3116)
                                        # La longitud se aproxima porque extrajimos el contorno de un valle ancho
                                        r_clip['longitud_km'] = (r_clip_m.length / 2) / 1000.0 
                                        
                                        r_clip['Orden_Strahler'] = np.where(
                                            r_clip['longitud_km'] > 2.0, 4, 
                                            np.where(r_clip['longitud_km'] > 1.0, 3, 
                                            np.where(r_clip['longitud_km'] > 0.4, 2, 1))
                                        )
                                        
                                        st.session_state['gdf_rios'] = r_clip
                                        st.success("✅ Red hídrica calculada exitosamente sin efecto de borde.")
                                        st.rerun() 
                                    else:
                                        st.warning("⚠️ Los ríos quedaron fuera del límite tras el recorte final.")
                                else:
                                    st.warning("⚠️ No se detectaron valles claros.")
                            else:
                                st.warning("⚠️ Terreno plano.")
                    else:
                        st.error("❌ No se pudo descargar el modelo de elevación.")
                except Exception as e:
                    st.error(f"Error crítico: {e}")