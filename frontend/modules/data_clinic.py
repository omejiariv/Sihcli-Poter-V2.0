# modules/data_clinic.py

import pandas as pd
import numpy as np
import streamlit as st

def sanar_matriz_espacial(df_long, gdf_estaciones=None, col_fecha='fecha', col_valor='valor', col_id='id_estacion', mostrar_alerta=True):
    """
    Motor del Aleph: Construye la malla espacio-temporal completa del período,
    detecta meses faltantes (NaN) o falsos ceros y los reconstruye mediante IDW
    basado en las estaciones vecinas sanas.
    """
    if df_long is None or df_long.empty:
        return pd.DataFrame()

    df_work = df_long.copy()
    df_work[col_fecha] = pd.to_datetime(df_work[col_fecha]).dt.to_period('M').dt.to_timestamp()
    df_work = df_work[df_work[col_fecha] <= pd.Timestamp.today().to_period('M').to_timestamp()]

    # 1. Catálogo de coordenadas de las estaciones presentes en la consulta
    if 'latitud' in df_work.columns and 'longitud' in df_work.columns:
        cat_coords = df_work[[col_id, 'latitud', 'longitud']].drop_duplicates(subset=[col_id]).copy()
    elif gdf_estaciones is not None and not gdf_estaciones.empty:
        cat_coords = gdf_estaciones[[col_id, 'latitud', 'longitud']].drop_duplicates(subset=[col_id]).copy()
    else:
        return df_work

    estaciones_unicas = cat_coords[col_id].dropna().unique()
    meses_unicos = np.sort(df_work[col_fecha].dropna().unique())

    if len(estaciones_unicas) == 0 or len(meses_unicos) == 0:
        return df_work

    # 2. MALLA CARTESIANA COMPLETA (Hace visibles los meses ausentes en SQL como NaN)
    malla_completa = pd.MultiIndex.from_product(
        [estaciones_unicas, meses_unicos],
        names=[col_id, col_fecha]
    ).to_frame().reset_index(drop=True)

    df_mensual = df_work.groupby([col_id, col_fecha], as_index=False)[col_valor].sum(min_count=1)
    df_healed = pd.merge(malla_completa, df_mensual, on=[col_id, col_fecha], how='left')
    df_healed = pd.merge(df_healed, cat_coords, on=col_id, how='left')

    df_healed['es_imputado'] = False
    df_healed['valor_crudo'] = df_healed[col_valor]

    registros_sanados = 0

    # 3. Curación mes a mes mediante IDW (Inverso de la Distancia al Cuadrado)
    for mes in meses_unicos:
        mask_mes = df_healed[col_fecha] == mes
        df_mes = df_healed[mask_mes]

        vals_validos = df_mes[col_valor].dropna()
        mediana_regional = vals_validos.median() if not vals_validos.empty else 0.0

        # Umbral dinámico: respeta meses secos reales, pero atrapa falsos ceros en meses lluviosos
        umbral_enfermedad = max(2.0, mediana_regional * 0.15) if mediana_regional > 40.0 else 0.0

        coords_ok = df_mes['latitud'].notna() & df_mes['longitud'].notna()
        mask_sanos = coords_ok & df_mes[col_valor].notna() & (df_mes[col_valor] > umbral_enfermedad)
        mask_enfermos = coords_ok & (df_mes[col_valor].isna() | (df_mes[col_valor] <= umbral_enfermedad))

        sanos = df_mes[mask_sanos]
        enfermos = df_mes[mask_enfermos]

        if len(sanos) >= 3 and len(enfermos) > 0:
            lons_s = sanos['longitud'].values
            lats_s = sanos['latitud'].values
            vals_s = sanos[col_valor].values

            lons_e = enfermos['longitud'].values
            lats_e = enfermos['latitud'].values

            # Distancia euclidiana y pesos IDW (p = 2)
            dist = np.sqrt((lons_e[:, None] - lons_s[None, :])**2 + (lats_e[:, None] - lats_s[None, :])**2)
            dist = np.where(dist < 1e-9, 1e-9, dist)
            pesos = 1.0 / (dist ** 2)
            vals_predichos = np.sum(pesos * vals_s[None, :], axis=1) / np.sum(pesos, axis=1)

            df_healed.loc[enfermos.index, col_valor] = np.round(vals_predichos, 1)
            df_healed.loc[enfermos.index, 'es_imputado'] = True
            registros_sanados += len(enfermos)

    if mostrar_alerta:
        st.caption(f"✨ **Aleph ({pd.to_datetime(meses_unicos[0]).year}):** {registros_sanados} meses faltantes o anómalos reconstruidos espacialmente.")

    return df_healed