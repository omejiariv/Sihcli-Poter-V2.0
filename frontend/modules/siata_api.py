# modules/siata_api.py

import pandas as pd
import numpy as np
import geopandas as gpd
import requests
import streamlit as st
import warnings
import urllib3
from functools import reduce

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

SIATA_URLS_CATALOGO = [
    "https://siata.gov.co/api/estaciones/",
    "https://siata.gov.co/estacionesPluviometricas/",
    "http://siata.gov.co:8089/estacionesPluviometricas/",
    "http://siata.gov.co:8089/estacionesMeteorologicas/"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*'
}

@st.cache_data(ttl=3600, show_spinner=False)
def descargar_catalogo_siata():
    """Descarga el metadato iterando por los servidores del SIATA hasta hallar uno activo."""
    for url in SIATA_URLS_CATALOGO:
        try:
            resp = requests.get(url, headers=HEADERS, verify=False, timeout=8)
            if resp.status_code == 200:
                datos = resp.json()
                lista_estaciones = []
                for est in datos:
                    coords = est.get('coordenadas', [{}])[0] if isinstance(est.get('coordenadas'), list) else est
                    lat = coords.get('latitud', coords.get('lat'))
                    lon = coords.get('longitud', coords.get('lon'))
                    cod = est.get('codigo', est.get('id', est.get('codigo_estacion')))
                    
                    if lat is not None and lon is not None and cod is not None:
                        lista_estaciones.append({
                            'codigo_siata': str(cod).split('.')[0].strip(),
                            'lat': float(lat),
                            'lon': float(lon)
                        })
                        
                df_siata = pd.DataFrame(lista_estaciones)
                if not df_siata.empty:
                    df_siata = df_siata.drop_duplicates(subset=['codigo_siata'])
                    gdf_siata = gpd.GeoDataFrame(
                        df_siata, 
                        geometry=gpd.points_from_xy(df_siata.lon, df_siata.lat),
                        crs="EPSG:4326"
                    )
                    return gdf_siata
        except Exception:
            continue
            
    return None


def homologar_por_proximidad(gdf_db, gdf_siata=None, umbral_metros=200):
    """
    Vincula las estaciones de Supabase con los códigos de sensor del SIATA:
    1. Si la estación en Supabase ya tiene prefijo 'SIATA_xxx', extrae su código directamente.
    2. Si es una estación IDEAM y existe gdf_siata, empareja gemelas espaciales a menos de umbral_metros.
    """
    if gdf_db is None or gdf_db.empty:
        return {}
        
    diccionario = {}
    col_id = next((c for c in gdf_db.columns if c.lower() in ['codigo', 'id_estacion']), None)
    if not col_id:
        return {}

    for val in gdf_db[col_id].dropna().astype(str).unique():
        val_clean = val.strip()
        if val_clean.upper().startswith('SIATA_'):
            cod_num = val_clean.split('_', 1)[1].split('.')[0].strip()
            if cod_num.isdigit():
                diccionario[val_clean] = cod_num

    if gdf_siata is not None and not gdf_siata.empty:
        try:
            gdf_otras = gdf_db[~gdf_db[col_id].astype(str).str.upper().str.startswith('SIATA_')].copy()
            if not gdf_otras.empty:
                ideam_m = gdf_otras.to_crs(epsg=9377)
                siata_m = gdf_siata.to_crs(epsg=9377)
                cruce = gpd.sjoin_nearest(ideam_m, siata_m, how='inner', max_distance=umbral_metros, distance_col='distancia_m')
                if 'codigo_siata' in cruce.columns:
                    for _, r in cruce.iterrows():
                        diccionario[str(r[col_id]).strip()] = str(r['codigo_siata']).split('.')[0].strip()
        except Exception:
            pass

    return diccionario


def _procesar_sensores_siata(p1_raw, p2_raw):
    """Limpia códigos nulos (-999) y conmuta entre p1 y p2 sin duplicar pulsos de balancín."""
    codigos_nulos = [-999, -999.0, -99.9, 999, 999.9, 9999, -9999]
    p1 = pd.to_numeric(pd.Series(p1_raw).astype(str).str.replace(',', '.'), errors='coerce').replace(codigos_nulos, np.nan)
    p2 = pd.to_numeric(pd.Series(p2_raw).astype(str).str.replace(',', '.'), errors='coerce').replace(codigos_nulos, np.nan)
    
    p1 = p1.where((p1 >= 0) & (p1 < 50))
    p2 = p2.where((p2 >= 0) & (p2 < 50))
    
    sum1, sum2 = p1.sum(skipna=True), p2.sum(skipna=True)
    if sum1 <= 0.2 * sum2 and sum2 > 0:
        return p2.fillna(0.0)
    elif sum2 <= 0.2 * sum1 and sum1 > 0:
        return p1.fillna(0.0)
    else:
        return p1.fillna(p2).fillna(0.0)


def extraer_lluvia_reciente_siata(
    diccionario_homologacion,
    meses_atras=5,
    gdf_estaciones=None,
    usar_reanalisis=True,
    formato="ancho",
):
    """
    Extrae la precipitación mensual de los últimos `meses_atras` meses diferenciando origen:
    - Capa 1: 'SIATA (Telemetría Real)' desde el Geoportal SIATA.
    - Capa 2 (opcional): 'Open-Meteo (Reanálisis ERA5)' para completar meses faltantes.

    Parámetros:
    - formato='ancho': retorna matriz (fecha x estaciones) y adjunta trazabilidad en df.attrs['detalle_origen'].
    - formato='largo': retorna DataFrame ['fecha', 'id_estacion', 'valor', 'origen'] listo para Supabase.
    """
    if not diccionario_homologacion:
        return pd.DataFrame()

    hoy = pd.Timestamp.today().normalize()
    mes_actual_tope = hoy.to_period("M").to_timestamp()
    fecha_inicio_trim = (hoy - pd.DateOffset(months=int(meses_atras))).to_period("M").to_timestamp()

    URLS_DATOS = [
        "https://geoportal.siata.gov.co/fastgeoapi/geodata/geographJson/2/pluvio_30d/{id_estacion}",
        "https://geoportal.siata.gov.co/fastgeoapi/geodata/geographJson/2/pluvio_72h/{id_estacion}",
    ]

    registros_reales = []
    items_est = list(diccionario_homologacion.items())

    geoportal_activo = False
    if items_est:
        try:
            test_url = URLS_DATOS[0].format(id_estacion=items_est[0][1])
            r_test = requests.get(test_url, headers=HEADERS, verify=False, timeout=3)
            if r_test.status_code == 200 and "info" in r_test.json():
                geoportal_activo = True
        except Exception:
            geoportal_activo = False

    # --- CAPA 1: TELEMETRÍA REAL SIATA ---
    if geoportal_activo:
        for cod_destino, cod_siata in items_est:
            for url_base in URLS_DATOS:
                url = url_base.format(id_estacion=cod_siata)
                try:
                    res = requests.get(url, headers=HEADERS, verify=False, timeout=3)
                    if res.status_code == 200:
                        info = res.json().get("info", {})
                        tiempos = info.get("Tiempo", [])
                        if tiempos:
                            df_est = pd.DataFrame({"fecha_dt": pd.to_datetime(tiempos, errors="coerce")})
                            df_est["precipitacion"] = _procesar_sensores_siata(
                                info.get("pluvio_1", []),
                                info.get("pluvio_2", []),
                            )
                            df_est = df_est.dropna(subset=["fecha_dt"])
                            if not df_est.empty:
                                df_est["dia"] = df_est["fecha_dt"].dt.date
                                df_est["fecha"] = df_est["fecha_dt"].dt.to_period("M").dt.to_timestamp()
                                resumen_m = df_est.groupby("fecha", as_index=False).agg(
                                    valor=("precipitacion", "sum"),
                                    n_dias=("dia", "nunique"),
                                )
                                # Meses cerrados: >= 15 días; mes actual en curso: >= 10 días
                                mask_dias = np.where(
                                    resumen_m["fecha"] < mes_actual_tope,
                                    resumen_m["n_dias"] >= 15,
                                    resumen_m["n_dias"] >= 10,
                                )
                                resumen_m = resumen_m[mask_dias & (resumen_m["valor"] > 0) & (resumen_m["valor"] <= 1500.0)]
                                for _, r in resumen_m.iterrows():
                                    registros_reales.append({
                                        "fecha": r["fecha"],
                                        "id_estacion": cod_destino,
                                        "valor": round(float(r["valor"]), 2),
                                        "origen": "SIATA (Telemetría Real)",
                                    })
                            break
                except Exception:
                    continue

    df_largo_real = pd.DataFrame(registros_reales, columns=["fecha", "id_estacion", "valor", "origen"])

    # --- CAPA 2: RESPALDO REANÁLISIS (OPEN-METEO ERA5 + FORECAST) ---
    registros_reanalisis = []
    if usar_reanalisis and gdf_estaciones is not None and not gdf_estaciones.empty:
        try:
            col_id = next((c for c in gdf_estaciones.columns if c.lower() in ["codigo", "id_estacion"]), None)
            df_coords = gdf_estaciones.copy()

            if "lat" in df_coords.columns:
                df_coords["lat"] = pd.to_numeric(df_coords["lat"], errors="coerce")
            elif "latitud" in df_coords.columns:
                df_coords["lat"] = pd.to_numeric(df_coords["latitud"], errors="coerce")
            elif hasattr(df_coords, "geometry"):
                df_coords["lat"] = df_coords.geometry.y

            if "lon" in df_coords.columns:
                df_coords["lon"] = pd.to_numeric(df_coords["lon"], errors="coerce")
            elif "longitud" in df_coords.columns:
                df_coords["lon"] = pd.to_numeric(df_coords["longitud"], errors="coerce")
            elif hasattr(df_coords, "geometry"):
                df_coords["lon"] = df_coords.geometry.x

            df_coords = df_coords[df_coords[col_id].astype(str).isin(diccionario_homologacion.keys())].dropna(subset=["lat", "lon"])

            if not df_coords.empty:
                df_coords["lat_r"] = df_coords["lat"].round(1)
                df_coords["lon_r"] = df_coords["lon"].round(1)

                start_str = fecha_inicio_trim.strftime("%Y-%m-%d")
                end_archive_str = max(fecha_inicio_trim, hoy - pd.Timedelta(days=6)).strftime("%Y-%m-%d")

                for (lat_c, lon_c), df_grp in df_coords.groupby(["lat_r", "lon_r"]):
                    partes_diarias = []

                    try:
                        url_arch = (
                            f"https://archive-api.open-meteo.com/v1/archive?"
                            f"latitude={lat_c}&longitude={lon_c}&start_date={start_str}&end_date={end_archive_str}"
                            f"&daily=precipitation_sum&timezone=America%2FBogota"
                        )
                        r_arch = requests.get(url_arch, headers=HEADERS, verify=False, timeout=10)
                        if r_arch.status_code == 200:
                            d_arch = r_arch.json().get("daily", {})
                            if "time" in d_arch and "precipitation_sum" in d_arch:
                                partes_diarias.append(pd.DataFrame({
                                    "fecha_dt": pd.to_datetime(d_arch["time"]),
                                    "ppt": pd.to_numeric(d_arch["precipitation_sum"], errors="coerce"),
                                }))
                    except Exception:
                        pass

                    try:
                        url_fc = (
                            f"https://api.open-meteo.com/v1/forecast?"
                            f"latitude={lat_c}&longitude={lon_c}&past_days=14&forecast_days=1"
                            f"&daily=precipitation_sum&timezone=America%2FBogota"
                        )
                        r_fc = requests.get(url_fc, headers=HEADERS, verify=False, timeout=10)
                        if r_fc.status_code == 200:
                            d_fc = r_fc.json().get("daily", {})
                            if "time" in d_fc and "precipitation_sum" in d_fc:
                                partes_diarias.append(pd.DataFrame({
                                    "fecha_dt": pd.to_datetime(d_fc["time"]),
                                    "ppt": pd.to_numeric(d_fc["precipitation_sum"], errors="coerce"),
                                }))
                    except Exception:
                        pass

                    if partes_diarias:
                        df_d = pd.concat(partes_diarias, ignore_index=True).dropna(subset=["fecha_dt"])
                        df_d = df_d.sort_values("fecha_dt").drop_duplicates(subset=["fecha_dt"], keep="first")
                        df_d["ppt"] = df_d["ppt"].fillna(0.0)
                        df_d = df_d[df_d["fecha_dt"] <= hoy]
                        df_d["fecha"] = df_d["fecha_dt"].dt.to_period("M").dt.to_timestamp()
                        s_mes = df_d.groupby("fecha")["ppt"].sum().round(2)
                        s_mes = s_mes[(s_mes > 0) & (s_mes <= 1500.0)]
                        for est_id in df_grp[col_id].astype(str):
                            for f_mes, val_mes in s_mes.items():
                                registros_reanalisis.append({
                                    "fecha": f_mes,
                                    "id_estacion": est_id,
                                    "valor": float(val_mes),
                                    "origen": "Open-Meteo (Reanálisis ERA5)",
                                })
        except Exception as e:
            print(f"Aviso en malla trimestral: {e}")

    df_largo_re = pd.DataFrame(registros_reanalisis, columns=["fecha", "id_estacion", "valor", "origen"])

    # Prioridad absoluta a la telemetría real SIATA sobre el reanálisis
    df_largo = pd.concat([df_largo_real, df_largo_re], ignore_index=True)
    if df_largo.empty:
        return pd.DataFrame()

    df_largo["fecha"] = pd.to_datetime(df_largo["fecha"]).dt.to_period("M").dt.to_timestamp()
    df_largo = df_largo[
        (df_largo["fecha"] >= fecha_inicio_trim) & (df_largo["fecha"] <= mes_actual_tope)
    ].drop_duplicates(subset=["fecha", "id_estacion"], keep="first")
    df_largo = df_largo.sort_values(["fecha", "id_estacion"]).reset_index(drop=True)
    df_largo["fecha"] = df_largo["fecha"].dt.strftime("%Y-%m-%d")

    if str(formato).lower() == "largo":
        return df_largo

    df_ancho = df_largo.pivot(index="fecha", columns="id_estacion", values="valor").reset_index()
    df_ancho = df_ancho.sort_values("fecha").reset_index(drop=True)
    df_ancho.attrs["detalle_origen"] = df_largo
    return df_ancho
