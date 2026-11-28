# modules/charts_engine.py

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

MESES_ORDEN = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MESES_MAPA = {i + 1: m for i, m in enumerate(MESES_ORDEN)}


# ==============================================================================
# 1. GRÁFICOS DE SERIES DE TIEMPO Y TENDENCIAS
# ==============================================================================

def plot_serie_anual(df, col_anio, col_valor, col_estacion):
    """Serie anual con banda P10-P90 y promedio regional superpuesto."""
    df_clean = df.dropna(subset=[col_anio, col_valor]).sort_values([col_estacion, col_anio]).copy()
    n_est = df_clean[col_estacion].nunique()

    fig = px.line(
        df_clean,
        x=col_anio,
        y=col_valor,
        color=col_estacion,
        markers=(n_est <= 12),
        labels={col_valor: "Lluvia Anual (mm)", col_anio: "Año"},
    )
    if n_est > 12:
        fig.update_traces(opacity=0.35, line=dict(width=1.2))

    # Promedio regional y banda interdecil (P10 - P90)
    stats_yr = df_clean.groupby(col_anio)[col_valor].agg(
        media="mean",
        p10=lambda s: np.percentile(s, 10),
        p90=lambda s: np.percentile(s, 90),
    ).reset_index()

    if len(stats_yr) > 1 and n_est >= 3:
        fig.add_trace(go.Scatter(
            x=pd.concat([stats_yr[col_anio], stats_yr[col_anio][::-1]]),
            y=pd.concat([stats_yr["p90"], stats_yr["p10"][::-1]]),
            fill="toself",
            fillcolor="rgba(52, 152, 219, 0.14)",
            line=dict(color="rgba(255,255,255,0)"),
            name="Banda P10–P90",
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=stats_yr[col_anio],
            y=stats_yr["media"],
            mode="lines+markers",
            name="PROMEDIO REGIONAL",
            line=dict(color="#111827", width=3.2),
            marker=dict(size=5),
        ))

    fig.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>Año: %{x}<br>Lluvia: %{y:,.0f} mm<extra></extra>",
        selector=dict(mode="lines"),
    )
    fig.update_layout(
        hovermode="closest",
        margin=dict(l=20, r=20, t=40, b=20),
        height=480,
    )
    return fig


def plot_ranking_multianual(df, col_estacion, col_valor, sort_opt, top_n=25):
    """Ranking de precipitación media. Usa barras horizontales legibles cuando hay muchas estaciones."""
    df_plot = df.dropna(subset=[col_valor]).copy()
    df_plot = df_plot[df_plot[col_valor] > 0]

    if sort_opt == "Mayor a Menor":
        df_plot = df_plot.sort_values(col_valor, ascending=False)
    elif sort_opt == "Menor a Mayor":
        df_plot = df_plot.sort_values(col_valor, ascending=True)
    else:
        df_plot = df_plot.sort_values(col_estacion)

    if len(df_plot) > top_n:
        df_plot = df_plot.head(top_n)
        titulo = f"Top {top_n} Estaciones ({sort_opt})"
    else:
        titulo = f"Ranking de Precipitación Media ({len(df_plot)} estaciones)"

    if len(df_plot) > 15:
        df_plot = df_plot.iloc[::-1]  # Para que el #1 quede arriba en barras horizontales
        fig = px.bar(
            df_plot,
            y=col_estacion,
            x=col_valor,
            orientation="h",
            color=col_valor,
            color_continuous_scale="Blues",
            text_auto=".0f",
            title=titulo,
        )
        fig.update_layout(height=max(460, len(df_plot) * 24), margin=dict(l=20, r=20, t=45, b=20))
    else:
        fig = px.bar(
            df_plot,
            x=col_estacion,
            y=col_valor,
            color=col_valor,
            color_continuous_scale="Blues",
            text_auto=".0f",
            title=titulo,
        )
        fig.update_layout(height=450, margin=dict(l=20, r=20, t=45, b=20))

    return fig


def plot_serie_mensual(df, show_markers, show_regional):
    """Serie histórica mensual ordenada estrictamente por estación y fecha."""
    df_clean = df.dropna(subset=["fecha", "valor"]).sort_values(["id_estacion", "fecha"]).copy()
    n_est = df_clean["id_estacion"].nunique()

    fig = px.line(
        df_clean,
        x="fecha",
        y="valor",
        color="id_estacion",
        markers=show_markers,
        title="Precipitación Mensual",
        labels={"valor": "Lluvia (mm)", "fecha": "Fecha"},
    )
    if n_est > 12:
        fig.update_traces(opacity=0.45, line=dict(width=1.1))

    if show_regional:
        reg_mean = df_clean.groupby("fecha")["valor"].mean().reset_index().sort_values("fecha")
        fig.add_trace(go.Scatter(
            x=reg_mean["fecha"],
            y=reg_mean["valor"],
            mode="lines",
            name="PROMEDIO REGIONAL",
            line=dict(color="#111827", width=3, dash="dash"),
        ))

    fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20), height=460)
    return fig


# ==============================================================================
# 2. GRÁFICOS DE CICLO ANUAL Y ESTACIONALIDAD
# ==============================================================================

def plot_ciclo_anual(df, year_comp=None):
    """Régimen de lluvias con orden calendario estricto (Ene-Dic) y mediana regional."""
    df_clean = df.dropna(subset=["Mes", "valor"]).copy()
    df_clean["Nombre_Mes"] = df_clean["Mes"].map(MESES_MAPA)

    ciclo = (
        df_clean.groupby(["Mes", "Nombre_Mes", "id_estacion"], as_index=False)["valor"]
        .mean()
        .sort_values(["id_estacion", "Mes"])
    )
    n_est = ciclo["id_estacion"].nunique()

    fig = px.line(
        ciclo,
        x="Nombre_Mes",
        y="valor",
        color="id_estacion",
        markers=(n_est <= 15),
        category_orders={"Nombre_Mes": MESES_ORDEN},
        title="Ciclo Anual Promedio (Régimen Climatológico)",
        labels={"valor": "Lluvia Media (mm/mes)", "Nombre_Mes": "Mes"},
    )
    if n_est > 15:
        fig.update_traces(opacity=0.32, line=dict(width=1.1))

    # Mediana regional destacada
    reg_clim = df_clean.groupby(["Mes", "Nombre_Mes"], as_index=False)["valor"].median().sort_values("Mes")
    fig.add_trace(go.Scatter(
        x=reg_clim["Nombre_Mes"],
        y=reg_clim["valor"],
        mode="lines+markers",
        name="MEDIANA REGIONAL",
        line=dict(color="#111827", width=3.5),
        marker=dict(size=7),
    ))

    if year_comp:
        df_year = df_clean[df_clean["Año"] == year_comp].groupby(["Mes", "Nombre_Mes"], as_index=False)["valor"].mean().sort_values("Mes")
        if not df_year.empty:
            fig.add_trace(go.Scatter(
                x=df_year["Nombre_Mes"],
                y=df_year["valor"],
                mode="lines+markers",
                name=f"Promedio Regional ({year_comp})",
                line=dict(color="#dc2626", dash="dot", width=3),
                marker=dict(symbol="diamond", size=7),
            ))

    fig.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>Año: %{x}<br>Lluvia: %{y:,.0f} mm<extra></extra>",
        selector=dict(mode="lines"),
    )
    fig.update_layout(
        hovermode="closest",
        margin=dict(l=20, r=20, t=40, b=20),
        height=480,
    )
    return fig

def plot_spaghetti_estacional(df_st, col_anio, col_valor, hl_year=None):
    """Spaghetti Plot del ciclo anual comparativo."""
    years = sorted(df_st[col_anio].unique(), reverse=True)
    fig = go.Figure()

    for yr in years:
        df_y = df_st[df_st[col_anio] == yr].sort_values("MES_NUM")
        color, width, opacity, show_leg = "rgba(180, 180, 180, 0.45)", 1, 0.5, False
        if hl_year and yr == hl_year:
            color, width, opacity, show_leg = "#dc2626", 4, 1.0, True

        fig.add_trace(go.Scatter(
            x=df_y["Nombre_Mes"],
            y=df_y[col_valor],
            mode="lines",
            name=str(yr),
            line=dict(color=color, width=width),
            opacity=opacity,
            showlegend=show_leg,
        ))

    clim = df_st.groupby("MES_NUM")[col_valor].mean().sort_index()
    names_clim = [MESES_MAPA.get(m, str(m)) for m in clim.index]

    fig.add_trace(go.Scatter(
        x=names_clim,
        y=clim.values,
        mode="lines+markers",
        name="Promedio Histórico",
        line=dict(color="black", width=3, dash="dot"),
    ))

    fig.update_xaxes(categoryorder="array", categoryarray=MESES_ORDEN, title="Mes")
    fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=20, b=20))
    return fig


def plot_cajas_estacional(df_st, col_valor):
    """Boxplot de variabilidad estacional."""
    fig = px.box(
        df_st,
        x="Nombre_Mes",
        y=col_valor,
        color="Nombre_Mes",
        points="all",
        category_orders={"Nombre_Mes": MESES_ORDEN},
    )
    fig.update_layout(showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
    return fig


# ==============================================================================
# 3. GRÁFICOS ESTADÍSTICOS
# ==============================================================================

def plot_distribucion_estadistica(df, col_x, col_y, chart_typ, sort_ord, max_estaciones=20):
    """Genera Violín (sin valores negativos), Histograma o ECDF."""
    df_clean = df.dropna(subset=[col_x, col_y]).copy()

    # Limitar a las estaciones con más datos si hay demasiadas para mantener legibilidad
    if df_clean[col_x].nunique() > max_estaciones:
        top_ests = df_clean[col_x].value_counts().head(max_estaciones).index
        df_clean = df_clean[df_clean[col_x].isin(top_ests)]

    cat_orders = {}
    if sort_ord != "Alfabético":
        medians = df_clean.groupby(col_x)[col_y].median()
        cat_orders = {col_x: medians.sort_values(ascending=False).index.tolist()}

    if "Violín" in chart_typ:
        fig = px.violin(
            df_clean, x=col_x, y=col_y, color=col_x,
            box=True, points="outliers", category_orders=cat_orders
        )
        fig.update_traces(spanmode="hard")  # Impide colas negativas imposibles (< 0 mm)
    elif "Histograma" in chart_typ:
        fig = px.histogram(
            df_clean, x=col_y, color=col_x,
            marginal="box", barmode="overlay", category_orders=cat_orders
        )
    else:
        fig = px.ecdf(df_clean, x=col_y, color=col_x)

    fig.update_layout(height=550, showlegend=(chart_typ != "Violín"), margin=dict(l=20, r=20, t=40, b=20))
    return fig


# ==============================================================================
# 4. MOTOR DE DIAGNÓSTICO AUTOMÁTICO (CAPA 1: ML + ESTADÍSTICA)
# ==============================================================================

def calcular_diagnostico_ml(df_monthly, df_anual, gdf_stations, col_estacion, col_anio, col_valor):
    """
    Calcula un diagnóstico hidroclimático sintético en tiempo real:
    - Régimen de lluvias (Bimodal vs Unimodal) y meses pico/seco
    - Tendencia regional (Theil-Sen / Mann-Kendall en mm/década)
    - Clustering K-Means (Núcleo Húmedo / Transición / Sombra de Lluvia) y gradiente orográfico
    """
    diag = {}

    # 1. Régimen climatológico
    clim = df_monthly.groupby("Mes")[col_valor].mean().reindex(range(1, 13))
    mes_max = int(clim.idxmax()) if clim.notna().any() else 5
    mes_min = int(clim.idxmin()) if clim.notna().any() else 1

    # Detección simple de bimodalidad: dos picos separados (Abr-May y Sep-Nov) con valle en Jul-Ago
    p1 = clim.loc[[4, 5]].mean()
    p2 = clim.loc[[9, 10, 11]].mean()
    valle_jul = clim.loc[[7, 8]].mean()
    es_bimodal = pd.notna(valle_jul) and (p1 > valle_jul * 1.15) and (p2 > valle_jul * 1.15)

    diag["regimen"] = "Bimodal Andino" if es_bimodal else "Unimodal / Transicional"
    diag["mes_pico"] = f"{MESES_MAPA[mes_max]} ({clim.loc[mes_max]:.0f} mm)"
    diag["mes_seco"] = f"{MESES_MAPA[mes_min]} ({clim.loc[mes_min]:.0f} mm)"

    # 2. Tendencia regional (Mann-Kendall + Pendiente de Sen)
    serie_reg = df_anual.groupby(col_anio)[col_valor].mean().sort_index()
    diag["media_anual"] = float(serie_reg.mean()) if not serie_reg.empty else 0.0
    diag["tendencia_txt"] = "Sin datos suficientes"
    diag["pendiente_decada"] = 0.0

    if len(serie_reg) >= 8:
        try:
            import pymannkendall as mk
            res = mk.original_test(serie_reg.values)
            pend_dec = float(res.slope) * 10.0
            diag["pendiente_decada"] = pend_dec
            sig = "Significativa" if res.p < 0.05 else "No significativa"
            flecha = "📈" if pend_dec > 5 else ("📉" if pend_dec < -5 else "➡️")
            diag["tendencia_txt"] = f"{flecha} {pend_dec:+.1f} mm/década ({sig}, p={res.p:.3f})"
        except Exception:
            pass

    # 3. Clustering K-Means (Estaciones por Precipitación Media) + Gradiente Orográfico
    est_media = df_anual.groupby(col_estacion)[col_valor].mean().dropna().reset_index()
    est_media.columns = ["estacion", "ppt_media"]
    diag["n_estaciones"] = len(est_media)
    diag["clusters_df"] = pd.DataFrame()
    diag["gradiente_txt"] = None

    if len(est_media) >= 6:
        try:
            from sklearn.cluster import KMeans
            km = KMeans(n_clusters=3, n_init=10, random_state=42)
            est_media["cluster_id"] = km.fit_predict(est_media[["ppt_media"]])
            orden = est_media.groupby("cluster_id")["ppt_media"].mean().sort_values().index.tolist()
            etiquetas = {
                orden[0]: "🌵 Sombra de Lluvia",
                orden[1]: "⚖️ Transición",
                orden[2]: "🌧️ Núcleo Húmedo",
            }
            est_media["Zona"] = est_media["cluster_id"].map(etiquetas)
            diag["clusters_df"] = (
                est_media.groupby("Zona", as_index=False)
                .agg(Estaciones=("estacion", "count"), Media_mm=("ppt_media", "mean"), Max_mm=("ppt_media", "max"))
                .sort_values("Media_mm", ascending=False)
            )
        except Exception:
            pass

    # Gradiente orográfico si hay altitud en gdf_stations
    if gdf_stations is not None and not gdf_stations.empty and "altitud" in gdf_stations.columns:
        col_nom_g = next((c for c in [col_estacion, "nombre", "id_estacion"] if c in gdf_stations.columns), None)
        if col_nom_g:
            m_alt = pd.merge(
                est_media,
                gdf_stations[[col_nom_g, "altitud"]].drop_duplicates(),
                left_on="estacion",
                right_on=col_nom_g,
            )
            m_alt["altitud"] = pd.to_numeric(m_alt["altitud"], errors="coerce")
            m_alt = m_alt.dropna(subset=["altitud", "ppt_media"])
            m_alt = m_alt[m_alt["altitud"] > 0]
            if len(m_alt) >= 5 and m_alt["altitud"].std() > 50:
                slope_alt = np.polyfit(m_alt["altitud"], m_alt["ppt_media"], 1)[0] * 100.0
                diag["gradiente_txt"] = f"{slope_alt:+.1f} mm por cada 100 m de elevación"

    # 4. Tabla georreferenciada de estaciones por clúster (con rescate DEM de altitudes en 0)
    diag["estaciones_clusters_df"] = pd.DataFrame()
    if "Zona" in est_media.columns and gdf_stations is not None and not gdf_stations.empty:
        col_nom_g = next((c for c in [col_estacion, "nombre", "id_estacion"] if c in gdf_stations.columns), None)
        if col_nom_g:
            gdf_geo = gdf_stations.drop_duplicates(subset=[col_nom_g]).copy()
            if "latitud" in gdf_geo.columns:
                gdf_geo["_lat"] = pd.to_numeric(gdf_geo["latitud"], errors="coerce")
            elif "latitude" in gdf_geo.columns:
                gdf_geo["_lat"] = pd.to_numeric(gdf_geo["latitude"], errors="coerce")
            else:
                gdf_geo["_lat"] = gdf_geo.geometry.y

            if "longitud" in gdf_geo.columns:
                gdf_geo["_lon"] = pd.to_numeric(gdf_geo["longitud"], errors="coerce")
            elif "longitude" in gdf_geo.columns:
                gdf_geo["_lon"] = pd.to_numeric(gdf_geo["longitude"], errors="coerce")
            else:
                gdf_geo["_lon"] = gdf_geo.geometry.x

            cols_geo = [col_nom_g, "_lat", "_lon"] + (["altitud"] if "altitud" in gdf_geo.columns else [])
            df_map_cl = pd.merge(est_media, gdf_geo[cols_geo], left_on="estacion", right_on=col_nom_g, how="inner")
            df_map_cl = df_map_cl.dropna(subset=["_lat", "_lon", "ppt_media"]).copy()

            # Rescate de altitudes faltantes o en 0 usando el DEM
            if "altitud" not in df_map_cl.columns:
                df_map_cl["altitud"] = np.nan
            else:
                df_map_cl["altitud"] = pd.to_numeric(df_map_cl["altitud"], errors="coerce")
                df_map_cl.loc[df_map_cl["altitud"] <= 0, "altitud"] = np.nan

            if df_map_cl["altitud"].isna().any():
                try:
                    from modules.dem_extractor import completar_altitudes_con_dem
                    df_map_cl = completar_altitudes_con_dem(
                        df_estaciones=df_map_cl,
                        col_lat="_lat",
                        col_lon="_lon",
                        col_alt="altitud",
                    )
                except Exception:
                    pass

            diag["estaciones_clusters_df"] = df_map_cl

    return diag

def plot_mapa_clusters_kmeans(df_clusters, gdf_zona=None):
    """Mapa interactivo de estaciones clasificadas por K-Means con límite territorial."""
    colores_zona = {
        "🌧️ Núcleo Húmedo": "#1d4ed8",
        "⚖️ Transición": "#10b981",
        "🌵 Sombra de Lluvia": "#ea580c",
    }
    df_plot = df_clusters.copy()
    hover_cols = {"ppt_media": ":.0f", "Zona": True, "_lat": False, "_lon": False}
    if "altitud" in df_plot.columns and df_plot["altitud"].notna().any():
        hover_cols["altitud"] = ":.0f"

    fig = px.scatter_mapbox(
        df_plot,
        lat="_lat",
        lon="_lon",
        color="Zona",
        size="ppt_media",
        size_max=16,
        hover_name="estacion",
        hover_data=hover_cols,
        color_discrete_map=colores_zona,
        category_orders={"Zona": ["🌧️ Núcleo Húmedo", "⚖️ Transición", "🌵 Sombra de Lluvia"]},
        mapbox_style="open-street-map",
        zoom=9.5,
        height=480,
        labels={"ppt_media": "Media Anual (mm)", "altitud": "Altitud (msnm)"},
        title="Distribución Espacial de Estaciones por Zona Climática (K-Means)",
    )

    # Capa del límite del polígono seleccionado
    if gdf_zona is not None and not gdf_zona.empty:
        try:
            zona_4326 = gdf_zona.to_crs("EPSG:4326") if (gdf_zona.crs and gdf_zona.crs.to_epsg() != 4326) else gdf_zona
            poly_union = zona_4326.geometry.make_valid().unary_union
            geoms = list(poly_union.geoms) if hasattr(poly_union, "geoms") else [poly_union]

            lons_poly, lats_poly = [], []
            for g in geoms:
                if hasattr(g, "exterior"):
                    x, y = g.exterior.xy
                    lons_poly.extend(list(x) + [None])
                    lats_poly.extend(list(y) + [None])

            if lons_poly:
                fig.add_trace(go.Scattermapbox(
                    lon=lons_poly,
                    lat=lats_poly,
                    mode="lines",
                    line=dict(color="#111827", width=2.8),
                    name="Límite Territorial",
                    hoverinfo="skip",
                ))
        except Exception:
            pass

    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    return fig

def generar_dictamen_ia(diag, nombre_zona, periodo_str, api_key):
    """
    Capa 2: Envía el resumen JSON de la Capa 1 a Gemini y retorna un dictamen
    hidroclimático ejecutivo (2-3 párrafos) orientado a seguridad hídrica y gestión del riesgo.
    """
    import json
    import requests

    clusters_resumen = []
    if not diag.get("clusters_df", pd.DataFrame()).empty:
        for _, r in diag["clusters_df"].iterrows():
            clusters_resumen.append({
                "zona": r["Zona"],
                "estaciones": int(r["Estaciones"]),
                "media_anual_mm": round(float(r["Media_mm"]), 0),
                "max_grupo_mm": round(float(r["Max_mm"]), 0),
            })

    payload_datos = {
        "territorio": nombre_zona,
        "periodo_analizado": periodo_str,
        "estaciones_activas": diag.get("n_estaciones", 0),
        "media_anual_regional_mm": round(float(diag.get("media_anual", 0)), 1),
        "regimen_lluvias": diag.get("regimen", "N/D"),
        "mes_mas_humedo": diag.get("mes_pico", "N/D"),
        "mes_mas_seco": diag.get("mes_seco", "N/D"),
        "tendencia_mann_kendall": diag.get("tendencia_txt", "N/D"),
        "gradiente_orografico": diag.get("gradiente_txt", "No disponible"),
        "zonificacion_kmeans": clusters_resumen,
    }

    prompt = (
        "Eres un hidroclimatólogo especialista en cuencas andinas de Antioquia, Colombia. "
        "Con base únicamente en el siguiente resumen estadístico en JSON, redacta un dictamen ejecutivo "
        "técnico y concreto en exactamente 3 párrafos cortos:\n"
        "1) Síntesis del régimen de lluvias, volumen medio y gradiente espacial/orográfico.\n"
        "2) Lectura de la tendencia histórica (Theil-Sen / Mann-Kendall) y contraste entre el núcleo húmedo y la sombra de lluvia.\n"
        "3) Implicaciones prácticas para seguridad hídrica, estiaje y gestión del riesgo en este territorio.\n"
        "Usa un tono técnico claro, sin saludos ni encabezados innecesarios.\n\n"
        f"DATOS JSON:\n{json.dumps(payload_datos, ensure_ascii=False, indent=2)}"
    )

    api_key = str(api_key).strip()
    body = {
    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096},
    }

    modelos = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.5-flash", "gemini-2.5-flash-lite"]
    urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        for m in modelos
    ]

    ultimo_error = None
    for url in urls:
        try:
            resp = requests.post(url, json=body, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                parts = data["candidates"][0]["content"].get("parts", [])
                texto = "".join(p.get("text", "") for p in parts if not p.get("thought", False)).strip()
                if texto:
                    return texto
            ultimo_error = f"{resp.status_code}: {resp.text[:250]}"
        except requests.exceptions.RequestException as e:
            ultimo_error = str(e)

    raise RuntimeError(ultimo_error)