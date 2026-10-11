# backend/app/api/router_geomorfologia.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import geopandas as gpd
import json
import traceback

# 1. IMPORTACIONES PESADAS SOLO EN EL BACKEND
import rasterio
from pysheds.grid import Grid

router = APIRouter(prefix="/api/geomorfologia", tags=["Geomorfología"])

class PeticionGeo(BaseModel):
    geojson_str: str

@router.post("/terreno_3d")
def procesar_terreno_3d(peticion: PeticionGeo):
    try:
        # A. Armar el polígono
        datos_geojson = json.loads(peticion.geojson_str)
        gdf_zona = gpd.GeoDataFrame.from_features(datos_geojson["features"])
        gdf_zona.set_crs(epsg=4326, inplace=True)
        
        # B. TOMA TU ANTIGUO CÓDIGO DE STREAMLIT Y PÉGALO AQUÍ
        # Aquí cargarías el DEM desde Supabase y usarías pysheds.
        # Por ahora, inyectaré datos simulados para que pruebes que la tubería funciona.
        
        z_min = 1450.0
        z_max = 2800.0
        z_media = 2100.0
        # Simulación de un array 2D para que Plotly no explote
        matriz_z_lista = [[1500, 1600], [1700, 1800]] 
        
        # C. Retornar JSON puro
        return {
            "z_min": z_min, "z_max": z_max, "z_media": z_media,
            "rango": z_max - z_min, "matriz_z": matriz_z_lista
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))