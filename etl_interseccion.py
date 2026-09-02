import geopandas as gpd
import pandas as pd
import unicodedata
import re
import os
import warnings
import requests
from shapely import wkb

warnings.filterwarnings('ignore')

def normalizar_texto(texto):
    if pd.isna(texto) or not texto: return ""
    t = str(texto).strip().upper()
    t = t.replace("Ñ", "N")
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9 ]', '', t).strip()

def extraer_nombre_mgn(row):
    nombre_base = str(row.get('bar_ccnmbr', '')).strip().title()
    if not nombre_base or nombre_base.lower() in ['null', 'nan', 'none']:
        return "Sector General"
    
    es_urbano = str(row.get('clase_suel', '')).strip().upper() == 'CABECERA'
    
    if es_urbano:
        comuna = str(row.get('comu_nmbre', '')).strip().title()
        if comuna and comuna.lower() not in ['null', 'nan', 'none']:
            return f"Barrio {nombre_base} ({comuna})"
        return f"Barrio {nombre_base}"
    else:
        return f"Vereda {nombre_base}"

def descargar_cuencas_magia():
    """Escanea los archivos de secretos y descarga la tabla 'cuencas' de Supabase automáticamente"""
    rutas = [".env", "backend/app/.env", "secrets.toml", ".streamlit/secrets.toml"]
    contenido = ""
    for ruta in rutas:
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                contenido += f.read() + "\n"

    # Intento 1: Conexión vía PostgreSQL (SQLAlchemy)
    match_sql = re.search(r'(postgresql://[^\'\"\s]+)', contenido)
    if match_sql or os.getenv("DATABASE_URL"):
        db_url = os.getenv("DATABASE_URL") or match_sql.group(1)
        from sqlalchemy import create_engine
        print("🔗 Conectando a Supabase vía PostgreSQL...")
        return gpd.read_postgis("SELECT * FROM cuencas;", create_engine(db_url), geom_col='geometry')

    # Intento 2: Conexión vía REST API de Supabase (Paginación + Conversión Geométrica WKB)
    match_jwt = re.search(r'(eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)', contenido)
    if match_jwt or os.getenv("SUPABASE_KEY"):
        print("🌐 Conectando a Supabase vía REST API...")
        key = os.getenv("SUPABASE_KEY") or match_jwt.group(1)
        url = "https://ldunpssoxvifemoyeuac.supabase.co"
        
        datos = []
        offset = 0
        while True:
            headers = {"apikey": key, "Authorization": f"Bearer {key}", "Range-Unit": "items", "Range": f"{offset}-{offset+999}"}
            res = requests.get(f"{url}/rest/v1/cuencas?select=*", headers=headers)
            if res.status_code != 200: raise Exception(f"Error API: {res.text}")
            data_json = res.json()
            if not data_json: break
            datos.extend(data_json)
            offset += 1000
            if len(data_json) < 1000: break
            
        df = pd.DataFrame(datos)
        # La magia: Convertimos el texto Hex de PostGIS en polígonos reales
        df['geometry'] = df['geometry'].apply(lambda x: wkb.loads(x, hex=True))
        gdf = gpd.GeoDataFrame(df, geometry='geometry')
        gdf.set_crs(epsg=4326, inplace=True)
        return gdf

    raise ValueError("❌ No encontré credenciales de Supabase en tus archivos .env ni secrets.toml")

def generar_interseccion_maestra_v3():
    print("⏳ [1/7] Descargando Territorio Maestro MGN desde Supabase...")
    gdf_mgn = gpd.read_file("https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson")

    print("⏳ [2/7] Descargando Cartografía de Cuencas...")
    gdf_cuencas = descargar_cuencas_magia()

    print("🗺️ [3/7] Proyectando capas a EPSG:3116 (MAGNA-SIRGAS)...")
    gdf_mgn = gdf_mgn.to_crs(epsg=3116)
    if gdf_cuencas.crs is None: gdf_cuencas.set_crs(epsg=4326, inplace=True)
    gdf_cuencas = gdf_cuencas.to_crs(epsg=3116)

    print("🧹 [4/7] Preparando topología y limpiando nombres...")
    gdf_mgn['mpio_norm'] = gdf_mgn['mpio_cnmbr'].apply(normalizar_texto)
    gdf_mgn['vereda_norm'] = gdf_mgn.apply(extraer_nombre_mgn, axis=1).apply(normalizar_texto)
    
    gdf_mgn['geometry'] = gdf_mgn.geometry.buffer(0)
    gdf_cuencas['geometry'] = gdf_cuencas.geometry.buffer(0)

    gdf_mgn['Area_Original_m2'] = gdf_mgn.geometry.area

    print("✂️ [5/7] Ejecutando Intersección Espacial (Corte de polígonos)... Esto tomará unos minutos.")
    interseccion = gpd.overlay(gdf_mgn, gdf_cuencas, how='intersection')

    print("⚖️ [6/7] Calculando proporciones de área resultantes...")
    interseccion['Area_Fragmento_m2'] = interseccion.geometry.area
    interseccion['Pct_Vereda_en_Cuenca'] = interseccion['Area_Fragmento_m2'] / interseccion['Area_Original_m2']

    interseccion = interseccion[interseccion['Pct_Vereda_en_Cuenca'] > 0.001]
    
    print("💾 [7/7] Exportando matriz a formato Parquet ultraligero...")
    cols_retener = [
        'mpio_norm', 'vereda_norm', 
        'nss3', 'nom_nss3', 'nss2', 'nom_nss2', 
        'nss1', 'nom_nss1', 'szh', 'nom_szh',
        'zh', 'nomzh', 'ah', 'nomah', 'Pct_Vereda_en_Cuenca'
    ]
    
    cols_finales = [col for col in cols_retener if col in interseccion.columns]
    df_final = pd.DataFrame(interseccion[cols_finales])
    
    mapeo_renombre = {
        'nss3': 'NSS3', 'nom_nss3': 'NOM_NSS3', 'nss2': 'NSS2', 'nom_nss2': 'NOM_NSS2',
        'nss1': 'NSS1', 'nom_nss1': 'NOM_NSS1', 'szh': 'SZH', 'nom_szh': 'NOM_SZH',
        'zh': 'ZH', 'nomzh': 'NOMZH', 'ah': 'AH', 'nomah': 'NOMAH'
    }
    df_final.rename(columns=mapeo_renombre, inplace=True)
    
    ruta_salida = "backend/app/data/matriz_cuencas_veredas.parquet"
    df_final.to_parquet(ruta_salida, index=False)
    print("🎉 ¡ÉXITO! Matriz de Intersección Cuencas-MGN V3 generada.")

if __name__ == "__main__":
    generar_interseccion_maestra_v3()