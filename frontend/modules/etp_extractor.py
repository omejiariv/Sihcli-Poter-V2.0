import os
import rasterio
from rasterio.mask import mask
import numpy as np

# 🚀 FIX 1: ¡Borramos el @st.cache_data por completo!
# También quitamos el guion bajo, ya que sin caché no hay colapso de memoria.
def extraer_etp_mensual(gdf_poligono):
    """
    Recorta los 12 mapas de ETP (TerraClimate) usando el polígono exacto
    y calcula el promedio mensual multianual puro en vivo y en directo.
    """
    etp_mensual = []
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dir_rasters = os.path.join(base_dir, "data", "rasters", "etp")

    # Reproyectamos a EPSG:4326 si es necesario
    if gdf_poligono.crs.to_epsg() != 4326:
        gdf_poligono = gdf_poligono.to_crs(epsg=4326)
        
    geometrias = [geom for geom in gdf_poligono.geometry]
    meses_nombres = ['01_Ene', '02_Feb', '03_Mar', '04_Abr', '05_May', '06_Jun', 
                     '07_Jul', '08_Ago', '09_Sep', '10_Oct', '11_Nov', '12_Dic']

    for mes in meses_nombres:
        ruta_raster = os.path.join(dir_rasters, f"ETP_TerraClimate_{mes}.tif")
        
        if not os.path.exists(ruta_raster):
            etp_mensual.append(100.0) 
            continue
            
        try:
            with rasterio.open(ruta_raster) as src:
                # ✂️ Cortador de galletas: Solo extrae lo que está dentro de la línea
                out_image, out_transform = mask(src, geometrias, crop=True)
                
                # 🚀 FIX 2: BLINDAJE MATEMÁTICO
                # Convertimos la matriz a float para que no confunda ceros con datos reales
                out_image = out_image.astype(float)
                
                # Averiguamos cuál es el código de "vacío" (usualmente 0.0 o un número raro)
                nodata_val = src.nodata if src.nodata is not None else 0.0
                
                # Forzamos lo que quedó fuera del municipio a ser "Nada" (NaN)
                out_image[out_image == nodata_val] = np.nan
                
                # Promediamos matemáticamente ignorando los NaN
                promedio_mes = np.nanmean(out_image)
                
                if np.isnan(promedio_mes):
                    etp_mensual.append(100.0) 
                else:
                    etp_mensual.append(round(float(promedio_mes), 1))
                    
        except Exception as e:
            print(f"Error procesando el mes {mes}: {e}")
            etp_mensual.append(100.0)

    return etp_mensual