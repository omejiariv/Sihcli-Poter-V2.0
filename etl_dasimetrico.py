import pandas as pd
import geopandas as gpd
import unicodedata
import re
import numpy as np
import warnings

# Ignorar advertencias de Pandas/Geopandas para consola limpia
warnings.filterwarnings('ignore')

# --- 1. FUNCIÓN DE LIMPIEZA DE TEXTOS ---
def normalizar_texto(texto):
    if pd.isna(texto) or not texto: return ""
    t = str(texto).strip().upper()
    t = t.replace("Ñ", "N")
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9 ]', '', t).strip()

# --- 2. MOTOR ETL DE PESOS DASIMÉTRICOS V3 ---
def construir_matriz_pesos_v3():
    # ⚠️ Cambia esta URL/Ruta por la ruta real de tu archivo local o de Supabase
    ruta_maestro = "TerritorioMaestro.geojson" 
    
    print("\n📥 [1/5] Cargando Territorio Maestro MGN...")
    ruta_maestro = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson"
    gdf = gpd.read_file(ruta_maestro)

    print("🗺️ [2/5] Proyectando a EPSG:3116 (MAGNA-SIRGAS) para áreas métricas exactas...")
    gdf = gdf.to_crs(epsg=3116)
    # Calculamos el área real matemática, ignorando columnas corruptas del pasado
    gdf['Area_Calc_m2'] = gdf.geometry.area

    print("🧹 [3/5] Normalizando atributos y armando topología MGN...")
    gdf['mpio_norm'] = gdf['mpio_cnmbr'].apply(normalizar_texto)
    
    # Detección estricta de Cabecera (Urbano) vs Rural
    gdf['clase_suelo_norm'] = gdf['clase_suel'].astype(str).str.strip().str.upper()
    gdf['es_urbano'] = gdf['clase_suelo_norm'] == 'CABECERA'
    
    # Inyección inteligente de nombres (Barrios, Veredas, Comunas)
    def extraer_nombre(row):
        nombre_base = str(row.get('bar_ccnmbr', '')).strip().title()
        if not nombre_base or nombre_base.lower() in ['null', 'nan', 'none']:
            return "Sector General"
        
        if row['es_urbano']:
            comuna = str(row.get('comu_nmbre', '')).strip().title()
            if comuna and comuna.lower() not in ['null', 'nan', 'none']:
                return f"Barrio {nombre_base} ({comuna})"
            return f"Barrio / Sector {nombre_base}"
        else:
            return f"Vereda {nombre_base}"

    gdf['territorio_nombre'] = gdf.apply(extraer_nombre, axis=1)
    gdf['territorio_norm'] = gdf['territorio_nombre'].apply(normalizar_texto)

    print("⚖️ [4/5] Calculando sumatorias de área por municipio (Distribución Dasimétrica)...")
    # Sumamos toda el área Urbana de cada municipio
    area_urb = gdf[gdf['es_urbano']].groupby('mpio_norm')['Area_Calc_m2'].sum().reset_index()
    area_urb.rename(columns={'Area_Calc_m2': 'area_urb_total'}, inplace=True)
    
    # Sumamos toda el área Rural de cada municipio
    area_rur = gdf[~gdf['es_urbano']].groupby('mpio_norm')['Area_Calc_m2'].sum().reset_index()
    area_rur.rename(columns={'Area_Calc_m2': 'area_rur_total'}, inplace=True)

    # Fusionamos los totales de vuelta a la matriz principal
    gdf = gdf.merge(area_urb, on='mpio_norm', how='left').merge(area_rur, on='mpio_norm', how='left')
    gdf['area_urb_total'] = gdf['area_urb_total'].fillna(0)
    gdf['area_rur_total'] = gdf['area_rur_total'].fillna(0)

    # FRACCIONES POBLACIONALES (Pesos):
    # ¿Qué porcentaje del casco urbano representa este barrio? 
    gdf['peso_urbano'] = np.where(
        gdf['es_urbano'] & (gdf['area_urb_total'] > 0),
        gdf['Area_Calc_m2'] / gdf['area_urb_total'],
        0.0
    )
    
    # ¿Qué porcentaje de todo el campo municipal representa esta vereda?
    gdf['peso_rural'] = np.where(
        ~gdf['es_urbano'] & (gdf['area_rur_total'] > 0),
        gdf['Area_Calc_m2'] / gdf['area_rur_total'],
        0.0
    )

    print("💾 [5/5] Exportando matriz a formato Parquet ultraligero...")
    # Solo guardamos la metadata y la matemática. Dejamos la geometría para no pesar.
    df_final = pd.DataFrame(gdf[[
        'mpio_norm', 'territorio_nombre', 'territorio_norm', 
        'clase_suel', 'Area_Calc_m2', 'peso_urbano', 'peso_rural'
    ]])
    
    output_path = "backend/app/data/matriz_pesos_veredales.parquet"
    df_final.to_parquet(output_path, index=False)
    
    print(f"\n✅ ¡ÉXITO! Operación Quirúrgica Completada.")
    print(f"📊 Registros procesados: {len(df_final)}")
    print(f"📁 Archivo guardado: {output_path}")

if __name__ == "__main__":
    construir_matriz_pesos_v3()