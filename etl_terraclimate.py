import os
import xarray as xr
import rioxarray
import pystac_client
import planetary_computer as pc

def descargar_climatologia_etp_colombia():
    print("🛰️ Conectando al Supercomputador Geoespacial (Microsoft Planetary Computer)...")
    
    try:
        # 1. Conexión al catálogo (Firma automática de TODO el ecosistema)
        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=pc.sign_inplace, 
        )
        
        # 2. Obtenemos Terraclimate
        collection = catalog.get_collection("terraclimate")
        
        # Usamos el protocolo nativo de Azure (ABFS)
        asset = collection.assets["zarr-abfs"]
        
        print("🌍 Abriendo el Cubo Zarr Global (Vía Protocolo Nativo Azure ABFS)...")
        
        kwargs = asset.extra_fields.get("xarray:open_kwargs", {}).copy()
        kwargs.pop("engine", None)
        
        if "storage_options" not in kwargs:
            kwargs["storage_options"] = asset.extra_fields.get("xarray:storage_options", {})
        
        ds = xr.open_zarr(asset.href, **kwargs)
        
        # 3. ✂️ CROP ESPACIAL (Bounding Box de Colombia)
        min_lon, max_lon = -80.0, -66.0
        min_lat, max_lat = -5.0, 13.5
        
        print("✂️ Recortando coordenadas para Colombia...")
        ds_colombia = ds.sel(lon=slice(min_lon, max_lon), lat=slice(max_lat, min_lat))
        
        # 4. ⏳ CROP TEMPORAL: Periodo climatológico base
        print("⏳ Extrayendo 20 años de historia climática (2000 a 2020)...")
        ds_reciente = ds_colombia.sel(time=slice("2000-01-01", "2030-12-31"))
        
        # 5. 🧮 LA MAGIA MATEMÁTICA
        print("🧮 Calculando promedios multianuales mensuales de ETP...")
        climatologia = ds_reciente.groupby("time.month").mean("time")
        
        pet_raster = climatologia['pet']
        
        # 🧹 FIX CRÍTICO: Borramos la etiqueta antigua de Microsoft para poder guardar el TIF
        pet_raster.attrs.pop("grid_mapping", None)
        
        # Configuramos el sistema espacial para los TIF limpios
        pet_raster = pet_raster.rio.write_crs("EPSG:4326")
        pet_raster.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
        
        # 6. 🗺️ EXPORTACIÓN
        output_dir = os.path.join("frontend", "data", "rasters", "etp")
        os.makedirs(output_dir, exist_ok=True)
        
        meses_nombres = ['01_Ene', '02_Feb', '03_Mar', '04_Abr', '05_May', '06_Jun', 
                         '07_Jul', '08_Ago', '09_Sep', '10_Oct', '11_Nov', '12_Dic']
                         
        print("\n💾 Descargando y guardando 12 Rasters (TIF) físicamente:")
        for mes_idx in range(1, 13):
            mes_data = pet_raster.sel(month=mes_idx)
            nombre_archivo = f"ETP_TerraClimate_{meses_nombres[mes_idx-1]}.tif"
            ruta_salida = os.path.join(output_dir, nombre_archivo)
            
            mes_data.rio.to_raster(ruta_salida)
            print(f"   ✅ Guardado: {nombre_archivo}")
            
        print(f"\n🎉 ¡Operación satelital completada! Rasters listos en: {output_dir}")

    except Exception as e:
        print(f"❌ Error crítico: {e}")

if __name__ == "__main__":
    descargar_climatologia_etp_colombia()