# backend/app/api/router_geomorfologia.py

import gc
import json
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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

        # 2. Lectura decimada directa por ventana (Ahorra >90% de RAM en Render)
        env_opts = {
            "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif"
        }
        with rasterio.Env(**env_opts):
            with rasterio.open(peticion.ruta_dem) as src:
                gdf_proy = gdf_zona.to_crs(src.crs)
                minx, miny, maxx, maxy = gdf_proy.total_bounds

                # Ventana espacial recortada a los límites reales del raster
                win = from_bounds(minx, miny, maxx, maxy, transform=src.transform)
                win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))

                if win.width <= 0 or win.height <= 0:
                    raise ValueError("El polígono está fuera de la cobertura del DEM.")

                # Calculamos dimensiones reducidas ANTES de leer a RAM (máx 220x220 px)
                max_dim = 220
                escala = max(1.0, max(win.height, win.width) / max_dim)
                out_h = max(2, int(round(win.height / escala)))
                out_w = max(2, int(round(win.width / escala)))

                # Lectura directa en float32 ya comprimida
                dem_array = src.read(
                    1,
                    window=win,
                    out_shape=(out_h, out_w),
                    resampling=Resampling.bilinear
                ).astype(np.float32)

                # Transformada exacta de la matriz reducida para aplicar la máscara vectorial
                win_transform = src.window_transform(win)
                scale_x = win.width / out_w
                scale_y = win.height / out_h
                reduced_transform = win_transform * win_transform.scale(scale_x, scale_y)

                # Enmascarar píxeles fuera del polígono
                mascara_fuera = geometry_mask(
                    gdf_proy.geometry.values,
                    out_shape=(out_h, out_w),
                    transform=reduced_transform,
                    invert=False
                )

                nodata_val = src.nodata
                invalido = mascara_fuera | (dem_array < -10)
                if nodata_val is not None:
                    invalido = invalido | (dem_array == nodata_val)

                dem_array = np.where(invalido, np.nan, dem_array)

        # 3. Estadísticas sobre datos válidos
        elevs_valid = dem_array[~np.isnan(dem_array)]
        if elevs_valid.size == 0:
            raise ValueError("El polígono no intersecta con datos válidos del DEM.")

        z_min = float(np.min(elevs_valid))
        z_max = float(np.max(elevs_valid))
        z_media = float(np.mean(elevs_valid))

        # 4. Convertir NaN a None para JSON válido
        matriz_lista = [
            [None if np.isnan(v) else round(float(v), 1) for v in fila]
            for fila in dem_array
        ]

        # Liberación explícita de RAM
        del dem_array, elevs_valid, gdf_zona, gdf_proy
        gc.collect()

        return {
            "z_min": z_min,
            "z_max": z_max,
            "z_media": z_media,
            "matriz_z": matriz_lista
        }
    except Exception as e:
        gc.collect()
        raise HTTPException(status_code=500, detail=str(e))