
# modules/ideam_api.py

import pandas as pd
import requests
import streamlit as st


def extraer_datos_ideam(estaciones_ids, fecha_inicio, min_dias=20):
    """
    Se conecta a la API de Datos Abiertos Colombia (IDEAM, dataset s54a-sgyg).
    Agrupa registros de 10 min en totales mensuales validando días mínimos reportados
    y filtrando picos erróneos de sensor.
    """
    url = "https://www.datos.gov.co/resource/s54a-sgyg.json"

    if not estaciones_ids:
        return False, "No se proporcionaron estaciones."

    estaciones_str = [str(e).replace(".0", "").split(".")[0].strip() for e in estaciones_ids]
    BATCH_SIZE = 30
    all_data = []

    progreso = st.progress(0, text="📡 IDEAM: Consolidando totales mensuales y validando cobertura diaria...")

    for i in range(0, len(estaciones_str), BATCH_SIZE):
        lote = estaciones_str[i:i + BATCH_SIZE]
        lista_sql = ",".join([f"'{e}'" for e in lote])

        query = {
            "$select": (
                "codigoestacion, "
                "date_trunc_ym(fechaobservacion) as mes_ano, "
                "sum(valorobservado) as valor_mensual, "
                "count(distinct date_trunc_ymd(fechaobservacion)) as n_dias"
            ),
            "$where": (
                f"codigoestacion in ({lista_sql}) "
                f"AND fechaobservacion >= '{fecha_inicio}T00:00:00.000' "
                f"AND valorobservado >= 0 AND valorobservado < 100"
            ),
            "$group": "codigoestacion, date_trunc_ym(fechaobservacion)",
            "$limit": 50000,
        }

        try:
            response = requests.get(url, params=query, timeout=45)
            if response.status_code == 200:
                data = response.json()
                if data:
                    all_data.extend(data)
            else:
                print(f"Error IDEAM (Lote {i // BATCH_SIZE + 1}): HTTP {response.status_code}")
        except Exception as e:
            print(f"Fallo de red IDEAM (Lote {i // BATCH_SIZE + 1}): {e}")

        progreso.progress(min((i + BATCH_SIZE) / len(estaciones_str), 1.0))

    progreso.empty()

    if not all_data:
        return False, "El IDEAM no retornó datos consolidados para estas fechas."

    df = pd.DataFrame(all_data)
    df["fecha"] = pd.to_datetime(df["mes_ano"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    df["valor_mensual"] = pd.to_numeric(df["valor_mensual"], errors="coerce")
    df["n_dias"] = pd.to_numeric(df.get("n_dias", min_dias), errors="coerce").fillna(0).astype(int)
    df = df.dropna(subset=["fecha", "valor_mensual"])

    # Control de integridad: exigir días mínimos reportados y rango físico mensual válido
    df = df[
        (df["n_dias"] >= int(min_dias))
        & (df["valor_mensual"] > 0)
        & (df["valor_mensual"] <= 1500.0)
    ].copy()

    if df.empty:
        return False, f"Ningún mes superó el filtro de integridad (≥ {min_dias} días reportados)."

    df["valor_mensual"] = df["valor_mensual"].round(2)
    df_ancha = df.pivot(index="fecha", columns="codigoestacion", values="valor_mensual").reset_index()
    df_ancha = df_ancha.sort_values("fecha").reset_index(drop=True)
    df_ancha["fecha"] = df_ancha["fecha"].dt.strftime("%Y-%m-%d")

    return True, df_ancha