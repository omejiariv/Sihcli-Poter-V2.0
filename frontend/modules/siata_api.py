# modules/siata_api.py

import pandas as pd
import geopandas as gpd
import requests
import datetime
import streamlit as st
import warnings

warnings.filterwarnings('ignore')

# Endpoints base del SIATA (Sujetos a disponibilidad de su red)
SIATA_URL_CATALOGO = "http://siata.gov.co:8089/estacionesPluviometricas/"
# URL genérica para datos (ajustar si el SIATA cambia su endpoint V2)
SIATA_URL_DATOS = "http://siata.gov.co:8089/api/estaciones/{id_estacion}/datos/"

@st.cache_data(ttl=86400, show_spinner=False)
def descargar_catalogo_siata():
    """
    Descarga el metadato (coordenadas) de todas las estaciones del SIATA.
    """
    try:
        resp = requests.get(SIATA_URL_CATALOGO, timeout=15)
        if resp.status_code == 200:
            datos = resp.json()
            # Asumiendo que la API devuelve una lista de diccionarios con 'codigo', 'latitud', 'longitud'
            # (El formato exacto se ajustará en vivo si el SIATA usa claves diferentes como 'coordenadas')
            lista_estaciones = []
            for est in datos:
                # Extraer lat/lon dependiendo de la estructura del JSON del SIATA
                coords = est.get('coordenadas', [{}])[0] if isinstance(est.get('coordenadas'), list) else est
                lat = coords.get('latitud', coords.get('lat'))
                lon = coords.get('longitud', coords.get('lon'))
                cod = est.get('codigo', est.get('id'))
                
                if lat and lon and cod:
                    lista_estaciones.append({
                        'codigo_siata': str(cod),
                        'lat': float(lat),
                        'lon': float(lon)
                    })
                    
            df_siata = pd.DataFrame(lista_estaciones)
            if not df_siata.empty:
                # Convertimos a GeoDataFrame
                gdf_siata = gpd.GeoDataFrame(
                    df_siata, 
                    geometry=gpd.points_from_xy(df_siata.lon, df_siata.lat),
                    crs="EPSG:4326"
                )
                return gdf_siata
        return None
    except Exception as e:
        print(f"Error conectando al catálogo SIATA: {e}")
        return None

def homologar_por_proximidad(gdf_ideam, gdf_siata, umbral_metros=200):
    """
    Empareja las estaciones IDEAM con las del SIATA si están a menos de X metros.
    Usa el Origen Nacional de Colombia (EPSG:9377) para medir en metros reales.
    """
    if gdf_ideam is None or gdf_siata is None:
        return {}
        
    try:
        # Reproyectar a metros para poder medir distancias reales
        ideam_m = gdf_ideam.to_crs(epsg=9377)
        siata_m = gdf_siata.to_crs(epsg=9377)
        
        # Realizamos un 'Spatial Join' por proximidad (Nearest)
        # sjoin_nearest requiere geopandas reciente
        cruce = gpd.sjoin_nearest(ideam_m, siata_m, how='inner', max_distance=umbral_metros, distance_col='distancia_m')
        
        # Asumiendo que gdf_ideam tiene una columna 'codigo' o 'codigo_estacion'
        col_ideam = next((c for c in cruce.columns if 'codigo' in c.lower() and 'siata' not in c.lower()), None)
        
        if col_ideam and 'codigo_siata' in cruce.columns:
            # Creamos el diccionario: { "codigo_ideam": "codigo_siata" }
            diccionario_homologacion = dict(zip(cruce[col_ideam].astype(str), cruce['codigo_siata'].astype(str)))
            return diccionario_homologacion
        return {}
    except Exception as e:
        print(f"Error en el cruce espacial IDEAM-SIATA: {e}")
        return {}

def extraer_lluvia_reciente_siata(diccionario_homologacion, meses_atras=6):
    """
    Descarga los datos minuto a minuto del SIATA y los suma a nivel mensual.
    Devuelve un DataFrame listo para hacer merge con la historia del IDEAM.
    """
    if not diccionario_homologacion: return pd.DataFrame()
    
    fecha_fin = datetime.datetime.now()
    fecha_inicio = fecha_fin - pd.DateOffset(months=meses_atras)
    str_inicio = fecha_inicio.strftime('%Y-%m-%d')
    str_fin = fecha_fin.strftime('%Y-%m-%d')
    
    resultados_mensuales = []
    
    for cod_ideam, cod_siata in diccionario_homologacion.items():
        url = SIATA_URL_DATOS.format(id_estacion=cod_siata)
        params = {"fecha_inicio": str_inicio, "fecha_fin": str_fin}
        
        try:
            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                datos = res.json()
                if datos:
                    # Convertir a pandas
                    df_est = pd.DataFrame(datos)
                    # Buscar la columna de fecha y de lluvia (suele ser 'fecha' y 'precipitacion')
                    col_f = next((c for c in df_est.columns if 'fecha' in c.lower()), None)
                    col_p = next((c for c in df_est.columns if 'precipi' in c.lower() or 'valor' in c.lower()), None)
                    
                    if col_f and col_p:
                        df_est[col_f] = pd.to_datetime(df_est[col_f])
                        df_est[col_p] = pd.to_numeric(df_est[col_p], errors='coerce')
                        
                        # Agrupamos por mes (Frecuencia 'MS' asegura el día 1 del mes)
                        df_mensual = df_est.set_index(col_f).resample('MS')[col_p].sum(min_count=1).reset_index()
                        
                        # Renombramos la columna de lluvia para que tenga el código del IDEAM (así empatará con tu Matriz)
                        df_mensual = df_mensual.rename(columns={col_f: 'fecha', col_p: cod_ideam})
                        resultados_mensuales.append(df_mensual)
        except Exception:
            pass # Si una estación del SIATA falla, seguimos con la siguiente
            
    # Unificamos todas las estaciones en una sola tabla matriz
    if resultados_mensuales:
        from functools import reduce
        df_fusion = reduce(lambda left, right: pd.merge(left, right, on='fecha', how='outer'), resultados_mensuales)
        return df_fusion.sort_values('fecha').reset_index(drop=True)
    return pd.DataFrame()
    