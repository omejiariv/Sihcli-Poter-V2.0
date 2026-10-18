# backend/app/api/router_geomorfologia.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import geopandas as gpd
import json
import numpy as np
import rasterio
from rasterio.mask import mask

router = APIRouter(prefix="/api/geomorfologia", tags=["Geomorfología"])

class PeticionGeo(BaseModel):
    geojson_str: str
    ruta_dem: str

@router.post("/terreno_3d")
def procesar_terreno_3d(peticion: PeticionGeo):
    try:
        # 1. Armar el polígono
        datos_geojson = json.loads(peticion.geojson_str)
        gdf_zona = gpd.GeoDataFrame.from_features(datos_geojson["features"])
        gdf_zona.set_crs(epsg=4326, inplace=True)
        
        # 2. Recortar el DEM
        with rasterio.open(peticion.ruta_dem) as src:
            gdf_proy = gdf_zona.to_crs(src.crs)
            out_image, out_transform = mask(src, gdf_proy.geometry.values, crop=True)
            dem_array = out_image[0]
            
            # Limpiar nodata
            dem_array = np.where((dem_array == src.nodata) | (dem_array < -10), np.nan, dem_array)
            
        # 3. Estadísticas
        elevs_valid = dem_array[~np.isnan(dem_array)]
        if len(elevs_valid) == 0:
            raise ValueError("El polígono no intersecta con datos válidos del DEM.")
            
        z_min = float(np.min(elevs_valid))
        z_max = float(np.max(elevs_valid))
        z_media = float(np.mean(elevs_valid))
        
        # 4. Reducir la matriz para enviarla por internet (Factor de compresión)
        h, w = dem_array.shape
        factor = max(1, int(max(h, w) / 200)) # Mismo factor que usas en tu app
        matriz_reducida = dem_array[::factor, ::factor]
        
        # Reemplazar NaN por None para que sea un JSON válido
        matriz_lista = np.where(np.isnan(matriz_reducida), None, matriz_reducida).tolist()

        return {
            "z_min": z_min, 
            "z_max": z_max, 
            "z_media": z_media,
            "matriz_z": matriz_lista
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))