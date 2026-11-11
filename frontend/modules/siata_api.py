# modules/siata_api.py

import pandas as pd
import geopandas as gpd
import requests
import datetime
import streamlit as st
import warnings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

# Batería de Endpoints del SIATA (Intenta desde el más seguro HTTPS hasta el puerto 8089)
SIATA_URLS_CATALOGO = [
    "https://siata.gov.co/api/estaciones/",
    "https://siata.gov.co/estacionesPluviometricas/",
    "http://siata.gov.co:8089/estacionesPluviometricas/",
    "http://siata.gov.co:8089/estacionesMeteorologicas/"
]

SIATA_URLS_DATOS = [
    "https://siata.gov.co/api/estaciones/{id_estacion}/datos/",
    "http://siata.gov.co:8089/api/estaciones/{id_estacion}/datos/"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'application/json'
}

@st.cache_data(ttl=3600, show_spinner=False)
def descargar_catalogo_siata():
    """Descarga el metadato iterando por los servidores del SIATA hasta hallar uno activo."""
    for url in SIATA_URLS_CATALOGO:
        try:
            resp = requests.get(url, headers=HEADERS, verify=False, timeout=10)
            if resp.status_code == 200:
                datos = resp.json()
                lista_estaciones = []
                for est in datos:
                    coords = est.get('coordenadas', [{}])[0] if isinstance(est.get('coordenadas'), list) else est
                    lat = coords.get('latitud', coords.get('lat'))
                    lon = coords.get('longitud', coords.get('lon'))
                    cod = est.get('codigo', est.get('id', est.get('codigo_estacion')))
                    
                    if lat and lon and cod:
                        lista_estaciones.append({
                            'codigo_siata': str(cod),
                            'lat': float(lat),
                            'lon': float(lon)
                        })
                        
                df_siata = pd.DataFrame(lista_estaciones)
                if not df_siata.empty:
                    gdf_siata = gpd.GeoDataFrame(
                        df_siata, 
                        geometry=gpd.points_from_xy(df_siata.lon, df_siata.lat),
                        crs="EPSG:4326"
                    )
                    print(f"✅ Catálogo SIATA descargado exitosamente desde: {url}")
                    return gdf_siata
        except Exception as e:
            print(f"⚠️ Fallo en {url}: {e}")
            continue
            
    print("🚨 Todos los endpoints del SIATA están inactivos o bloqueados por el Firewall.")
    return None

def homologar_por_proximidad(gdf_ideam, gdf_siata, umbral_metros=200):
    if gdf_ideam is None or gdf_siata is None: return {}
    try:
        ideam_m = gdf_ideam.to_crs(epsg=9377)
        siata_m = gdf_siata.to_crs(epsg=9377)
        cruce = gpd.sjoin_nearest(ideam_m, siata_m, how='inner', max_distance=umbral_metros, distance_col='distancia_m')
        
        col_ideam = next((c for c in cruce.columns if 'codigo' in c.lower() and 'siata' not in c.lower()), None)
        if col_ideam and 'codigo_siata' in cruce.columns:
            return dict(zip(cruce[col_ideam].astype(str), cruce['codigo_siata'].astype(str)))
        return {}
    except Exception as e:
        print(f"Error en el cruce espacial IDEAM-SIATA: {e}")
        return {}

def extraer_lluvia_reciente_siata(diccionario_homologacion, meses_atras=6):
    """
    Se conecta al API secreta (Geoportal) del SIATA, extrae la serie de tiempo 
    de los últimos 30 días, compara sensores redundantes y agrupa por mes.
    """
    if not diccionario_homologacion: return pd.DataFrame()
    
    # La URL secreta que descubriste. Intentaremos pedir los últimos 30 días (30d).
    # Si falla, bajamos a 72h o 3h.
    URLS_DATOS = [
        "https://geoportal.siata.gov.co/fastgeoapi/geodata/geographJson/2/pluvio_30d/{id_estacion}",
        "https://geoportal.siata.gov.co/fastgeoapi/geodata/geographJson/2/pluvio_72h/{id_estacion}",
        "https://geoportal.siata.gov.co/fastgeoapi/geodata/geographJson/2/pluvio_3h/{id_estacion}"
    ]
    
    resultados_mensuales = []
    
    for cod_ideam, cod_siata in diccionario_homologacion.items():
        exito_estacion = False
        
        for url_base in URLS_DATOS:
            if exito_estacion: break
            url = url_base.format(id_estacion=cod_siata)
            
            try:
                res = requests.get(url, headers=HEADERS, verify=False, timeout=10)
                if res.status_code == 200:
                    datos = res.json()
                    info = datos.get('info', {})
                    tiempos = info.get('Tiempo', [])
                    
                    if tiempos:
                        df_est = pd.DataFrame({'fecha': tiempos})
                        df_est['fecha'] = pd.to_datetime(df_est['fecha'])
                        
                        # Extraer sensores redundantes (pluvio_1 y pluvio_2)
                        p1 = pd.to_numeric(pd.Series(info.get('pluvio_1', [])), errors='coerce').fillna(0)
                        p2 = pd.to_numeric(pd.Series(info.get('pluvio_2', [])), errors='coerce').fillna(0)
                        
                        # Tomar el mayor valor de lluvia (evita ceros falsos si un sensor falla)
                        df_est['precipitacion'] = pd.DataFrame({'p1': p1, 'p2': p2}).max(axis=1)
                        
                        # Agrupar matemáticamente todo el acumulado por mes
                        df_mensual = df_est.set_index('fecha').resample('MS')['precipitacion'].sum().reset_index()
                        
                        # Bautizar la columna con el código largo del IDEAM
                        df_mensual = df_mensual.rename(columns={'precipitacion': cod_ideam})
                        resultados_mensuales.append(df_mensual)
                        exito_estacion = True
                        
            except Exception as e:
                print(f"Fallo conexión a {url}: {e}")
                continue
                
    # Fusionar las 3 estaciones (o las que encuentre) en una sola tabla maestra
    if resultados_mensuales:
        from functools import reduce
        df_fusion = reduce(lambda left, right: pd.merge(left, right, on='fecha', how='outer'), resultados_mensuales)
        return df_fusion.sort_values('fecha').reset_index(drop=True)
        
    return pd.DataFrame()