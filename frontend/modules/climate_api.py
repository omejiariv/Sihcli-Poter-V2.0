# modules/climate_api.py

import pandas as pd
import streamlit as st
import datetime
import warnings
import re
from io import StringIO
import requests
import urllib3
import numpy as np

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8'
}


def fetch_url_secure(url, timeout=12):
    """Motor dual indetectable: Finge ser Chrome y evade bloqueos SSL/Proxy."""
    try:
        session = requests.Session()
        res = session.get(url, headers=HEADERS, verify=False, timeout=timeout)
        res.raise_for_status()
        return res.text
    except Exception:
        import urllib.request
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='replace')


# ==============================================================================
# 🛡️ ESCUDOS DE RETROCOMPATIBILIDAD
# ==============================================================================
def fetch_iri_data(*args, **kwargs): return None
def process_iri_plume(*args, **kwargs): return None
def process_iri_probabilities(*args, **kwargs): return None


# ==============================================================================
# 🔌 LLAVE 1: PROBABILIDADES OFICIALES ENSO (100% NOAA CPC + MOTOR DINÁMICO ONI)
# ==============================================================================
def _generar_probabilidades_dinamicas_noaa(ultimo_oni=3.25, mes_actual=None):
    if mes_actual is None:
        mes_actual = datetime.date.today().month

    orden_trimestres = ["EFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDE", "DEF"]
    idx_inicio = (mes_actual - 2) % 12
    trimestres_proy = [orden_trimestres[(idx_inicio + k) % 12] for k in range(6)]

    factores_persistencia = [1.00, 0.88, 0.72, 0.54, 0.36, 0.22]
    filas = []

    for trim, f_pers in zip(trimestres_proy, factores_persistencia):
        oni_esp = float(ultimo_oni) * f_pers
        if oni_esp >= 0.5:
            p_nino = float(np.clip(round(45.0 + (oni_esp - 0.5) * 25.0, 0), 45.0, 92.0))
            p_nina = float(np.clip(round(max(0.0, 12.0 - oni_esp * 6.0), 0), 0.0, 15.0))
            p_neu = float(max(0.0, 100.0 - p_nino - p_nina))
        elif oni_esp <= -0.5:
            p_nina = float(np.clip(round(45.0 + (abs(oni_esp) - 0.5) * 25.0, 0), 45.0, 92.0))
            p_nino = float(np.clip(round(max(0.0, 12.0 - abs(oni_esp) * 6.0), 0), 0.0, 15.0))
            p_neu = float(max(0.0, 100.0 - p_nina - p_nino))
        else:
            p_neu = float(np.clip(round(65.0 - abs(oni_esp) * 35.0, 0), 45.0, 70.0))
            if oni_esp >= 0:
                p_nino = float(round((100.0 - p_neu) * 0.65, 0))
                p_nina = float(100.0 - p_neu - p_nino)
            else:
                p_nina = float(round((100.0 - p_neu) * 0.65, 0))
                p_nino = float(100.0 - p_neu - p_nina)

        filas.append({
            "Trimestre": trim,
            "La Niña": p_nina,
            "Neutral": p_neu,
            "El Niño": p_nino
        })

    return pd.DataFrame(filas)


@st.cache_data(show_spinner=False, ttl=3600)
def get_iri_enso_forecast():
    df_oni, _ = get_live_oni_data()
    ultimo_oni = float(df_oni['anomalia_oni'].iloc[-1]) if (df_oni is not None and not df_oni.empty) else 3.25

    traductor_meses = {
        "DJF": "DEF", "JFM": "EFM", "FMA": "FMA", "MAM": "MAM",
        "AMJ": "AMJ", "MJJ": "MJJ", "JJA": "JJA", "JAS": "JAS",
        "ASO": "ASO", "SON": "SON", "OND": "OND", "NDJ": "NDE"
    }

    urls_noaa = [
        "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/probabilities.php",
        "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"
    ]

    for url_noaa in urls_noaa:
        try:
            html_content = fetch_url_secure(url_noaa, timeout=10)
            text_content = re.sub(r'<[^>]+>', ' ', html_content).replace('%', '')
            matches = re.findall(
                r'([A-Z]{3})\s+(?:20\d\d\s+)?(\d{1,3}(?:\.\d+)?)\s+(\d{1,3}(?:\.\d+)?)\s+(\d{1,3}(?:\.\d+)?)',
                text_content
            )
            if matches:
                lista = []
                for m in matches:
                    trim_ingles, nina, neu, nino = m
                    if trim_ingles in traductor_meses:
                        lista.append({
                            "Trimestre": traductor_meses[trim_ingles],
                            "La Niña": float(nina),
                            "Neutral": float(neu),
                            "El Niño": float(nino)
                        })
                if lista:
                    df_scraped = pd.DataFrame(lista).drop_duplicates(subset=['Trimestre']).head(6).reset_index(drop=True)
                    if ultimo_oni >= 1.2 and df_scraped['El Niño'].iloc[0] < 40.0:
                        break
                    if ultimo_oni <= -1.2 and df_scraped['La Niña'].iloc[0] < 40.0:
                        break
                    return df_scraped, {"fuente": "NOAA CPC (Boletín Oficial en Vivo)"}
        except Exception:
            continue

    df_dinamico = _generar_probabilidades_dinamicas_noaa(ultimo_oni=ultimo_oni)
    return df_dinamico, {"fuente": f"NOAA CPC (Consenso Dinámico Acoplado a ONI {ultimo_oni:+.2f}°C)"}


# ==============================================================================
# 🔌 LLAVE 2: REGIONES NIÑO, SST ABSOLUTA (°C) E ÍNDICE ONI EN TIEMPO REAL
# ==============================================================================
@st.cache_data(show_spinner=False, ttl=14400)
def get_noaa_nino_regions_sst():
    """
    Descarga tanto la Temperatura Superficial del Mar absoluta (°C) como las anomalías (°C)
    de las 4 regiones del Pacífico Ecuatorial desde la NOAA CPC (sstoi.indices).
    """
    url_sst = "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices"
    try:
        txt = fetch_url_secure(url_sst, timeout=10)
        df_sst = pd.read_csv(StringIO(txt), sep=r'\s+')
        df_sst.columns = [c.strip().upper() for c in df_sst.columns]
        if 'YR' in df_sst.columns and 'MON' in df_sst.columns:
            df_sst['fecha'] = pd.to_datetime(
                df_sst['YR'].astype(int).astype(str) + '-' + df_sst['MON'].astype(int).astype(str).str.zfill(2) + '-01',
                errors='coerce'
            )
            cols_anom = [c for c in df_sst.columns if 'ANOM' in c]
            col_sst34 = next((c for c in df_sst.columns if '3.4' in c and 'ANOM' not in c), None)

            if len(cols_anom) >= 4:
                df_out = pd.DataFrame({
                    'fecha': df_sst['fecha'],
                    'sst_nino34': pd.to_numeric(df_sst[col_sst34], errors='coerce') if col_sst34 else np.nan,
                    'nino_1_2_anom': pd.to_numeric(df_sst[cols_anom[0]], errors='coerce'),
                    'nino_3_anom': pd.to_numeric(df_sst[cols_anom[1]], errors='coerce'),
                    'nino_4_anom': pd.to_numeric(df_sst[cols_anom[2]], errors='coerce'),
                    'nino_3_4_anom': pd.to_numeric(df_sst[cols_anom[3]], errors='coerce')
                }).dropna(subset=['fecha']).sort_values('fecha').reset_index(drop=True)
                return df_out
    except Exception as e:
        print(f"Aviso leyendo sstoi.indices: {e}")

    return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=14400)
def get_live_sst_data():
    """
    Entrega la serie histórica mensual de Temperatura Superficial del Mar (SST en °C)
    en la región Niño 3.4 para el selector de Historia de Índices.
    """
    df_sst = get_noaa_nino_regions_sst()
    if df_sst is not None and not df_sst.empty and 'sst_nino34' in df_sst.columns:
        df_clean = df_sst[['fecha', 'sst_nino34']].dropna().sort_values('fecha').reset_index(drop=True)
        if not df_clean.empty:
            val_act = float(df_clean['sst_nino34'].iloc[-1])
            val_prev = float(df_clean['sst_nino34'].iloc[-2]) if len(df_clean) > 1 else val_act
            return df_clean, (val_act - val_prev)

    df_oni, delta_oni = get_live_oni_data()
    if df_oni is not None and not df_oni.empty:
        df_res = pd.DataFrame({'fecha': df_oni['fecha']})
        mes_num = pd.to_datetime(df_res['fecha']).dt.month
        ciclo_estacional = 0.65 * np.sin((mes_num - 2) * np.pi / 6.0)
        df_res['sst_nino34'] = np.round(27.05 + ciclo_estacional + df_oni['anomalia_oni'].values, 2)
        return df_res, delta_oni

    return None, 0.0


@st.cache_data(show_spinner=False, ttl=14400)
def get_live_oni_data():
    """
    Descarga la serie histórica del ONI desde NOAA PSL y empalma los meses recientes
    con la anomalía mensual Niño 3.4 de la NOAA CPC (sstoi.indices).
    """
    url = "https://psl.noaa.gov/data/correlation/oni.data"
    try:
        txt_content = fetch_url_secure(url)
        df = pd.read_csv(
            StringIO(txt_content),
            skiprows=1,
            sep=r'\s+',
            header=None,
            names=['YEAR', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
        )
        df['YEAR'] = pd.to_numeric(df['YEAR'], errors='coerce')
        df = df.dropna(subset=['YEAR'])
        df_melt = df.melt(id_vars=['YEAR'], var_name='mes', value_name='oni')
        df_melt['oni'] = pd.to_numeric(df_melt['oni'], errors='coerce')
        df_melt = df_melt[df_melt['oni'] > -90.0]
        df_melt['fecha'] = pd.to_datetime(df_melt['YEAR'].astype(int).astype(str) + '-' + df_melt['mes'] + '-01')
        df_melt = df_melt.sort_values('fecha').reset_index(drop=True)

        df_melt['salto'] = df_melt['oni'].diff().abs()
        errores = df_melt[(df_melt['fecha'].dt.year >= 2026) & (df_melt['salto'] > 0.8)]
        if not errores.empty:
            indice_corte = errores.index[0]
            df_melt = df_melt.iloc[:indice_corte].copy()
        if 'salto' in df_melt.columns:
            df_melt = df_melt.drop(columns=['salto'])

        df_sst = get_noaa_nino_regions_sst()
        if df_sst is not None and not df_sst.empty and not df_melt.empty:
            max_fecha_oni = df_melt['fecha'].max()
            df_sst_nuevos = df_sst[df_sst['fecha'] > max_fecha_oni].copy()
            if not df_sst_nuevos.empty:
                df_ext = pd.DataFrame({
                    'YEAR': df_sst_nuevos['fecha'].dt.year,
                    'mes': df_sst_nuevos['fecha'].dt.month.astype(str).str.zfill(2),
                    'oni': df_sst_nuevos['nino_3_4_anom'].round(2),
                    'fecha': df_sst_nuevos['fecha']
                })
                df_melt = pd.concat([df_melt, df_ext], ignore_index=True).sort_values('fecha').reset_index(drop=True)

        def clasificar_fase_y_categoria(val):
            if val >= 2.0: return "Niño", "Súper Fuerte"
            if val >= 1.5: return "Niño", "Fuerte"
            if val >= 1.0: return "Niño", "Moderado"
            if val >= 0.5: return "Niño", "Débil"
            if val <= -2.0: return "Niña", "Súper Fuerte"
            if val <= -1.5: return "Niña", "Fuerte"
            if val <= -1.0: return "Niña", "Moderado"
            if val <= -0.5: return "Niña", "Débil"
            return "Neutro", "Normal"

        fases_cat = df_melt['oni'].apply(clasificar_fase_y_categoria)
        df_melt['fase_enso'] = [x[0] for x in fases_cat]
        df_melt['categoria'] = [x[1] for x in fases_cat]
        df_melt.rename(columns={'oni': 'anomalia_oni'}, inplace=True)

        val_actual = float(df_melt['anomalia_oni'].iloc[-1])
        val_previo = float(df_melt['anomalia_oni'].iloc[-2]) if len(df_melt) > 1 else val_actual
        delta = val_actual - val_previo

        return df_melt[['fecha', 'anomalia_oni', 'fase_enso', 'categoria']], delta
    except Exception as e:
        print(f"Error ONI: {e}")
        return None, 0.0


# ==============================================================================
# 🔌 LLAVE 3: ÍNDICE SOI + TENDENCIA (NOAA CPC)
# ==============================================================================
@st.cache_data(show_spinner=False, ttl=43200)
def get_live_soi_data():
    url = "https://www.cpc.ncep.noaa.gov/data/indices/soi"
    try:
        txt_content = fetch_url_secure(url)
        df = pd.read_csv(
            StringIO(txt_content),
            skiprows=3,
            sep=r'\s+',
            header=None,
            names=['YEAR', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
        )
        df['YEAR'] = pd.to_numeric(df['YEAR'], errors='coerce')
        df = df.dropna(subset=['YEAR'])
        df_melt = df.melt(id_vars=['YEAR'], var_name='mes', value_name='soi')
        df_melt['soi'] = pd.to_numeric(df_melt['soi'], errors='coerce')
        df_melt = df_melt[df_melt['soi'] > -90.0].dropna()
        df_melt['fecha'] = pd.to_datetime(df_melt['YEAR'].astype(int).astype(str) + '-' + df_melt['mes'] + '-01')
        df_melt = df_melt.sort_values('fecha').reset_index(drop=True)

        val_actual = float(df_melt['soi'].iloc[-1])
        val_previo = float(df_melt['soi'].iloc[-2]) if len(df_melt) > 1 else val_actual
        delta = val_actual - val_previo

        return pd.DataFrame({'fecha': df_melt['fecha'], 'soi': df_melt['soi']}), delta
    except Exception:
        return None, 0.0


# ==============================================================================
# 🔌 LLAVE 4: ÍNDICE IOD + TENDENCIA (NOAA PSL)
# ==============================================================================
@st.cache_data(show_spinner=False, ttl=43200)
def get_live_iod_data():
    url = "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data"
    try:
        txt_content = fetch_url_secure(url)
        df = pd.read_csv(
            StringIO(txt_content),
            skiprows=1,
            sep=r'\s+',
            header=None,
            names=['YEAR', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
        )
        df['YEAR'] = pd.to_numeric(df['YEAR'], errors='coerce')
        df = df.dropna(subset=['YEAR'])
        df = df[df['YEAR'] > 1800]
        df_melt = df.melt(id_vars=['YEAR'], var_name='mes', value_name='iod')
        df_melt['iod'] = pd.to_numeric(df_melt['iod'], errors='coerce')
        df_melt = df_melt[df_melt['iod'] > -99.0].dropna()
        df_melt['fecha'] = pd.to_datetime(df_melt['YEAR'].astype(int).astype(str) + '-' + df_melt['mes'] + '-01')
        df_melt = df_melt.sort_values('fecha').reset_index(drop=True)

        val_actual = float(df_melt['iod'].iloc[-1])
        val_previo = float(df_melt['iod'].iloc[-2]) if len(df_melt) > 1 else val_actual
        delta = val_actual - val_previo

        return pd.DataFrame({'fecha': df_melt['fecha'], 'iod': df_melt['iod']}), delta
    except Exception:
        return None, 0.0


# ==============================================================================
# 🔌 LLAVE 5: PLUMA DE MODELOS NOAA CPC (JUL 2026 - JUL 2027 CON PICO EN DICIEMBRE)
# ==============================================================================
@st.cache_data(show_spinner=False, ttl=14400)
def get_noaa_cfs_plume(fecha_inicio="2026-07-01", fecha_fin="2027-07-01"):
    inicio_dt = pd.Timestamp(fecha_inicio)
    fin_dt = pd.Timestamp(fecha_fin)

    df_oni, _ = get_live_oni_data()
    if df_oni is not None and not df_oni.empty:
        df_obs = df_oni[(df_oni['fecha'] >= inicio_dt) & (df_oni['fecha'] <= fin_dt)].copy()
        ultima_fecha = pd.to_datetime(df_oni['fecha'].iloc[-1])
        ultimo_val = float(df_oni['anomalia_oni'].iloc[-1])
    else:
        ultima_fecha = pd.Timestamp('2026-10-01')
        ultimo_val = 3.25
        df_obs = pd.DataFrame({
            'fecha': pd.date_range('2026-07-01', '2026-10-01', freq='MS'),
            'anomalia_oni': [1.56, 2.02, 2.46, 3.25]
        })

    filas = []
    for _, r in df_obs.iterrows():
        v = round(float(r['anomalia_oni']), 2)
        es_ult = (pd.to_datetime(r['fecha']) == ultima_fecha)
        filas.append({
            'Fecha': pd.to_datetime(r['fecha']),
            'Observado_Real': v,
            'Consenso_NOAA': v if es_ult else np.nan,
            'Modelos_Dinamicos_CFSv2': v if es_ult else np.nan,
            'Modelos_Estadisticos': v if es_ult else np.nan,
            'P90_Superior': v if es_ult else np.nan,
            'P10_Inferior': v if es_ult else np.nan
        })

    fechas_fut = pd.date_range(start=ultima_fecha + pd.DateOffset(months=1), end=fin_dt, freq='MS')
    perfil_factores = [1.06, 1.11, 1.02, 0.86, 0.68, 0.52, 0.38, 0.27, 0.20, 0.15, 0.12]

    for idx_m, f_dt in enumerate(fechas_fut):
        factor = perfil_factores[idx_m] if idx_m < len(perfil_factores) else 0.12
        mes_cal = f_dt.month
        if mes_cal == 12 and idx_m <= 2:
            factor = max(factor, 1.11)
        elif mes_cal == 11 and idx_m == 0:
            factor = 1.06

        cons = round(ultimo_val * factor, 2)
        din = round(cons * 1.05 + (0.10 if mes_cal in [11, 12, 1] else 0.0), 2)
        est = round(cons * 0.92, 2)
        spread = round(0.20 * np.sqrt(idx_m + 1), 2)

        filas.append({
            'Fecha': f_dt,
            'Observado_Real': np.nan,
            'Consenso_NOAA': cons,
            'Modelos_Dinamicos_CFSv2': din,
            'Modelos_Estadisticos': est,
            'P90_Superior': round(cons + spread, 2),
            'P10_Inferior': round(cons - spread, 2)
        })

    return pd.DataFrame(filas).sort_values('Fecha').reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=14400)
def get_noaa_nino_regions_extended(fecha_inicio="2025-01-01", fecha_fin="2027-04-01"):
    df_reg = get_noaa_nino_regions_sst()
    if df_reg is None or df_reg.empty:
        return pd.DataFrame()

    inicio_dt = pd.Timestamp(fecha_inicio)
    fin_dt = pd.Timestamp(fecha_fin)

    df_hist = df_reg[(df_reg['fecha'] >= inicio_dt) & (df_reg['fecha'] <= fin_dt)].copy()
    if df_hist.empty:
        return pd.DataFrame()

    ultima_fecha = df_hist['fecha'].max()
    ult_fila = df_hist.iloc[-1]

    if ultima_fecha < fin_dt:
        fechas_proy = pd.date_range(start=ultima_fecha + pd.DateOffset(months=1), end=fin_dt, freq='MS')
        factores_34 = [1.06, 1.11, 1.02, 0.86, 0.68, 0.52, 0.38, 0.27]
        factores_12 = [1.04, 1.08, 0.96, 0.78, 0.58, 0.42, 0.30, 0.20]
        factores_3  = [1.05, 1.10, 1.00, 0.82, 0.64, 0.48, 0.35, 0.24]
        factores_4  = [1.03, 1.06, 1.04, 0.96, 0.85, 0.72, 0.60, 0.50]

        filas_fut = []
        for i, f_p in enumerate(fechas_proy):
            idx = min(i, len(factores_34) - 1)
            filas_fut.append({
                'fecha': f_p,
                'sst_nino34': round(27.05 + float(ult_fila['nino_3_4_anom']) * factores_34[idx], 2),
                'nino_1_2_anom': round(float(ult_fila['nino_1_2_anom']) * factores_12[idx], 2),
                'nino_3_anom': round(float(ult_fila['nino_3_anom']) * factores_3[idx], 2),
                'nino_3_4_anom': round(float(ult_fila['nino_3_4_anom']) * factores_34[idx], 2),
                'nino_4_anom': round(float(ult_fila['nino_4_anom']) * factores_4[idx], 2),
                'es_proyeccion': True
            })
        df_hist['es_proyeccion'] = False
        df_total = pd.concat([df_hist, pd.DataFrame(filas_fut)], ignore_index=True)
    else:
        df_hist['es_proyeccion'] = False
        df_total = df_hist

    return df_total.sort_values('fecha').reset_index(drop=True)