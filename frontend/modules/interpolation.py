
# modules/interpolation.py

import os
# =========================================================================
# 🛡️ VACUNA ANTI-COLISIÓN PROJ (Blindaje del Motor Espacial)
# =========================================================================
for var in ['PROJ_LIB', 'PROJ_DATA', 'PROJ_DEBUG']:
    if var in os.environ:
        del os.environ[var]
try:
    import pyproj
    pyproj.datadir.set_data_dir(pyproj.datadir.get_data_dir())
    os.environ['PROJ_DATA'] = pyproj.datadir.get_data_dir()
except Exception:
    pass
# =========================================================================

import gstools as gs
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy.interpolate import Rbf, griddata
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import LeaveOneOut

from modules.config import Config


# =========================================================================
# 1. UTILIDADES INTERNAS (LIMPIEZA DETERMINÍSTICA Y VARIOGRAMA)
# =========================================================================
def _limpiar_y_agrupar_puntos(lons, lats, vals, elevs=None):
    """
    Elimina NaN/Inf y promedia estaciones con coordenadas idénticas (~1 m)
    para evitar colapsos matriciales sin inyectar ruido aleatorio.
    """
    df = pd.DataFrame({
        "lon": np.asarray(lons, dtype=float),
        "lat": np.asarray(lats, dtype=float),
        "val": np.asarray(vals, dtype=float),
    })
    if elevs is not None:
        df["elev"] = np.asarray(elevs, dtype=float)

    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    if df.empty:
        return np.array([]), np.array([]), np.array([]), (np.array([]) if elevs is not None else None)

    df["lon_r"] = df["lon"].round(5)
    df["lat_r"] = df["lat"].round(5)

    agg_dict = {"lon": "mean", "lat": "mean", "val": "mean"}
    if elevs is not None:
        agg_dict["elev"] = "mean"

    df_agg = df.groupby(["lon_r", "lat_r"], as_index=False).agg(agg_dict)
    out_elev = df_agg["elev"].values if elevs is not None else None
    return df_agg["lon"].values, df_agg["lat"].values, df_agg["val"].values, out_elev


def _ajustar_variograma(lons, lats, vals, modelo_variograma="spherical"):
    """Ajusta un modelo de variograma GSTools con respaldo teórico si hay pocos puntos."""
    model_map = {
        "gaussian": gs.Gaussian(dim=2),
        "exponential": gs.Exponential(dim=2),
        "spherical": gs.Spherical(dim=2),
        "linear": gs.Linear(dim=2),
    }
    model = model_map.get(str(modelo_variograma).lower(), gs.Spherical(dim=2))

    varianza = float(np.var(vals))
    if varianza < 1e-4 or np.isnan(varianza):
        varianza = 1.0

    dist_mat = np.sqrt((lons[:, None] - lons[None, :]) ** 2 + (lats[:, None] - lats[None, :]) ** 2)
    max_dist = float(np.max(dist_mat)) if dist_mat.size > 0 else 0.1
    rango_teorico = max(max_dist / 2.0, 0.05)

    if len(vals) < 12:
        model.var = varianza
        model.len_scale = rango_teorico
        model.nugget = varianza * 0.05
        return model, None, None

    try:
        bin_center, gamma = gs.vario_estimate((lons, lats), vals)
        model.fit_variogram(bin_center, gamma, nugget=True)
        if model.var < 1e-4 or np.isnan(model.var) or model.len_scale <= 0:
            model.var = varianza
            model.len_scale = rango_teorico
            model.nugget = varianza * 0.05
        return model, bin_center, gamma
    except Exception:
        model.var = varianza
        model.len_scale = rango_teorico
        model.nugget = varianza * 0.05
        return model, None, None


def _interpolar_idw_flat(lons, lats, vals, xi_flat, yi_flat, power=2.0):
    """IDW real vectorizado (1 / d^p) inmune a divisiones por cero."""
    dist = np.sqrt((xi_flat[:, None] - lons[None, :]) ** 2 + (yi_flat[:, None] - lats[None, :]) ** 2)
    dist = np.where(dist < 1e-10, 1e-10, dist)
    weights = 1.0 / (dist ** power)
    return np.sum(weights * vals[None, :], axis=1) / np.sum(weights, axis=1)


# =========================================================================
# 2. MOTOR DE INTERPOLACIÓN UNIFICADO (BLINDADO Y MULTIMÉTODO)
# =========================================================================
def interpolador_maestro(
    df_puntos,
    col_val,
    grid_x,
    grid_y,
    metodo="kriging",
    modelo_variograma="spherical",
    dem_grid=None,
):
    """
    Motor geoestadístico unificado. Soporta mallas generadas tanto con
    np.meshgrid (indexing='xy') como con np.mgrid (indexing='ij').
    Retorna: (matriz_z, matriz_std_o_None) con la misma forma que grid_x.
    """
    if hasattr(df_puntos, "geometry") and df_puntos.geometry is not None:
        raw_lons = df_puntos.geometry.x.values
        raw_lats = df_puntos.geometry.y.values
    else:
        col_lon = next((c for c in ["longitude", "longitud", "lon"] if c in df_puntos.columns), None)
        col_lat = next((c for c in ["latitude", "latitud", "lat"] if c in df_puntos.columns), None)
        raw_lons = df_puntos[col_lon].values
        raw_lats = df_puntos[col_lat].values

    raw_vals = pd.to_numeric(df_puntos[col_val], errors="coerce").values
    lons, lats, vals, _ = _limpiar_y_agrupar_puntos(raw_lons, raw_lats, raw_vals)

    if len(vals) == 0:
        return np.zeros_like(grid_x, dtype=float), None

    if len(vals) < 3:
        z = griddata((lons, lats), vals, (grid_x, grid_y), method="nearest")
        return np.nan_to_num(z, nan=float(np.mean(vals))), None

    val_min, val_max = float(np.min(vals)), float(np.max(vals))
    metodo_norm = str(metodo).lower().strip()

    # Detección automática de orientación de malla (meshgrid xy vs mgrid ij)
    es_meshgrid_xy = (
        grid_x.ndim == 2
        and grid_x.shape[1] > 1
        and not np.allclose(grid_x[0, 0], grid_x[0, 1])
    )
    if es_meshgrid_xy:
        grid_lon_1d = grid_x[0, :]
        grid_lat_1d = grid_y[:, 0]
    else:
        grid_lon_1d = grid_x[:, 0]
        grid_lat_1d = grid_y[0, :]

    try:
        if metodo_norm == "ked" and dem_grid is None:
            metodo_norm = "kriging"

        # --- A. KRIGING ORDINARIO ---
        if metodo_norm == "kriging":
            model, _, _ = _ajustar_variograma(lons, lats, vals, modelo_variograma)
            krig = gs.krige.Ordinary(model, (lons, lats), vals)
            z_krig, ss_krig = krig.structured([grid_lon_1d, grid_lat_1d], return_var=True)

            if es_meshgrid_xy:
                z_krig, ss_krig = z_krig.T, ss_krig.T

            if np.isnan(z_krig).all():
                raise ValueError("Kriging devolvió matriz vacía.")

            z_krig = np.clip(z_krig, a_min=max(0.0, val_min * 0.85), a_max=val_max * 1.15)
            return z_krig, np.sqrt(np.abs(ss_krig))

        # --- B. KRIGING CON DERIVA EXTERNA (KED) ---
        elif metodo_norm == "ked" and dem_grid is not None:
            elev_stations = griddata(
                (grid_x.ravel(), grid_y.ravel()), dem_grid.ravel(), (lons, lats), method="linear"
            )
            mask_nan_elev = np.isnan(elev_stations)
            if np.any(mask_nan_elev):
                elev_stations[mask_nan_elev] = griddata(
                    (grid_x.ravel(), grid_y.ravel()),
                    dem_grid.ravel(),
                    (lons[mask_nan_elev], lats[mask_nan_elev]),
                    method="nearest",
                )

            model, _, _ = _ajustar_variograma(lons, lats, vals, modelo_variograma)
            krig = gs.krige.ExtDrift(model, (lons, lats), vals, drift_src=elev_stations)
            drift_in = dem_grid.T if es_meshgrid_xy else dem_grid
            z_ked, ss_ked = krig.structured([grid_lon_1d, grid_lat_1d], drift_tgt=drift_in, return_var=True)

            if es_meshgrid_xy:
                z_ked, ss_ked = z_ked.T, ss_ked.T

            if np.isnan(z_ked).all():
                raise ValueError("KED devolvió matriz vacía.")

            # En KED solo recortamos negativos para preservar máximos orográficos en cumbres
            z_ked = np.maximum(z_ked, 0.0)
            return z_ked, np.sqrt(np.abs(ss_ked))

        # --- C. IDW REAL (1 / d^2) ---
        elif metodo_norm == "idw":
            z_idw = _interpolar_idw_flat(lons, lats, vals, grid_x.ravel(), grid_y.ravel(), power=2.0)
            z_idw = z_idw.reshape(grid_x.shape)
            return np.clip(z_idw, a_min=val_min, a_max=val_max), None

        # --- D. SPLINE (THIN PLATE REAL) ---
        elif metodo_norm in ["spline", "rbf"]:
            rbf = Rbf(lons, lats, vals, function="thin_plate", smooth=0.05)
            z_rbf = rbf(grid_x, grid_y)
            return np.clip(z_rbf, a_min=max(0.0, val_min * 0.85), a_max=val_max * 1.15), None

        # --- E. TENDENCIA LINEAL ---
        elif metodo_norm in ["trend", "linear"]:
            z_trend = griddata((lons, lats), vals, (grid_x, grid_y), method="linear")
            mask_nan = np.isnan(z_trend)
            if np.any(mask_nan):
                z_trend[mask_nan] = griddata(
                    (lons, lats), vals, (grid_x[mask_nan], grid_y[mask_nan]), method="nearest"
                )
            return np.clip(z_trend, a_min=val_min, a_max=val_max), None

    except Exception as e:
        print(f"Fallback activado en interpolador_maestro ({metodo_norm}): {e}")

    # --- FALLBACK 100% SEGURO ---
    z_lin = griddata((lons, lats), vals, (grid_x, grid_y), method="linear")
    mask_nan = np.isnan(z_lin)
    if np.any(mask_nan):
        z_lin[mask_nan] = griddata(
            (lons, lats), vals, (grid_x[mask_nan], grid_y[mask_nan]), method="nearest"
        )
    return np.clip(np.nan_to_num(z_lin, nan=float(np.mean(vals))), a_min=val_min, a_max=val_max), None


# =========================================================================
# 3. VALIDACIÓN CRUZADA (LOOCV OPTIMIZADO: VARIOGRAMA ÚNICO)
# =========================================================================
def _perform_loocv(method, lons, lats, vals, elevs=None):
    """Leave-One-Out Cross-Validation con variograma pre-ajustado y métodos reales."""
    lons, lats, vals, elevs = _limpiar_y_agrupar_puntos(lons, lats, vals, elevs)
    if len(vals) < 4:
        return {"RMSE": np.nan, "MAE": np.nan}

    # Ajustamos el variograma UNA sola vez fuera del bucle (hasta 50x más rápido)
    model_global = None
    if method in ["Kriging Ordinario", "Kriging con Deriva Externa (KED)"]:
        model_global, _, _ = _ajustar_variograma(lons, lats, vals, "spherical")

    loo = LeaveOneOut()
    y_true, y_pred = [], []

    for train_idx, test_idx in loo.split(lons):
        lons_tr, lats_tr, vals_tr = lons[train_idx], lats[train_idx], vals[train_idx]
        lon_te, lat_te, val_te = lons[test_idx[0]], lats[test_idx[0]], vals[test_idx[0]]

        if len(vals_tr) < 3:
            continue

        pred_val = np.nan
        try:
            if method == "Kriging Ordinario":
                krig = gs.krige.Ordinary(model_global, (lons_tr, lats_tr), vals_tr)
                res, _ = krig([lon_te, lat_te])
                pred_val = float(res[0])

            elif method == "Kriging con Deriva Externa (KED)" and elevs is not None:
                krig = gs.krige.ExtDrift(model_global, (lons_tr, lats_tr), vals_tr, drift_src=elevs[train_idx])
                res, _ = krig([lon_te, lat_te], drift_tgt=[elevs[test_idx[0]]])
                pred_val = float(res[0])

            elif method == "IDW":
                res = _interpolar_idw_flat(lons_tr, lats_tr, vals_tr, np.array([lon_te]), np.array([lat_te]))
                pred_val = float(res[0])

            elif method == "Spline (Thin Plate)":
                rbf = Rbf(lons_tr, lats_tr, vals_tr, function="thin_plate", smooth=0.05)
                pred_val = float(rbf(lon_te, lat_te))

            if np.isfinite(pred_val):
                y_true.append(val_te)
                y_pred.append(pred_val)
        except Exception:
            continue

    if not y_true:
        return {"RMSE": np.nan, "MAE": np.nan}

    return {
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "MAE": float(mean_absolute_error(y_true, y_pred)),
    }


def perform_loocv_for_year(year, method, gdf_metadata, df_anual_non_na):
    """Ejecuta LOOCV para un año y método específicos."""
    df_year = pd.merge(
        df_anual_non_na[df_anual_non_na[Config.YEAR_COL] == year],
        gdf_metadata,
        on=Config.STATION_NAME_COL,
    )
    clean_cols = [Config.LONGITUDE_COL, Config.LATITUDE_COL, Config.PRECIPITATION_COL]
    if method == "Kriging con Deriva Externa (KED)" and Config.ELEVATION_COL in df_year.columns:
        clean_cols.append(Config.ELEVATION_COL)

    df_clean = df_year.dropna(subset=clean_cols).copy()
    if len(df_clean) < 4:
        return {"RMSE": np.nan, "MAE": np.nan}

    elevs = df_clean[Config.ELEVATION_COL].values if Config.ELEVATION_COL in df_clean.columns else None
    return _perform_loocv(
        method,
        df_clean[Config.LONGITUDE_COL].values,
        df_clean[Config.LATITUDE_COL].values,
        df_clean[Config.PRECIPITATION_COL].values,
        elevs,
    )


@st.cache_data(ttl=3600, max_entries=10, show_spinner=False)
def perform_loocv_for_all_methods(_year, _gdf_metadata, _df_anual_non_na):
    """Ejecuta LOOCV para todos los métodos en un año dado."""
    methods = ["Kriging Ordinario", "IDW", "Spline (Thin Plate)"]
    if Config.ELEVATION_COL in _gdf_metadata.columns:
        methods.insert(1, "Kriging con Deriva Externa (KED)")

    results = []
    for method in methods:
        metrics = perform_loocv_for_year(_year, method, _gdf_metadata, _df_anual_non_na)
        if metrics:
            results.append({"Método": method, "Año": _year, "RMSE": metrics.get("RMSE"), "MAE": metrics.get("MAE")})
    return pd.DataFrame(results)


# =========================================================================
# 4. SUPERFICIES DE INTERPOLACIÓN Y WRAPPERS DE COMPATIBILIDAD
# =========================================================================
@st.cache_data(ttl=3600, max_entries=10, show_spinner=False)
def create_interpolation_surface(df_period_mean, period_name, method, variogram_model, gdf_bounds, gdf_metadata):
    """Genera el mapa de contornos Plotly con orientación consistente (ny, nx) en todos los métodos."""
    df_clean = pd.merge(df_period_mean, gdf_metadata, on=Config.STATION_NAME_COL, how="inner")
    for col in [Config.LONGITUDE_COL, Config.LATITUDE_COL, Config.PRECIPITATION_COL]:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

    df_clean = df_clean.dropna(subset=[Config.LONGITUDE_COL, Config.LATITUDE_COL, Config.PRECIPITATION_COL]).copy()
    if len(df_clean) < 4:
        msg = f"Se necesitan al menos 4 estaciones válidas para {period_name} (encontradas: {len(df_clean)})."
        return go.Figure().update_layout(title=msg, xaxis_visible=False, yaxis_visible=False), None, msg

    if gdf_bounds is None or len(gdf_bounds) != 4 or not all(np.isfinite(gdf_bounds)):
        msg = "Límites geográficos (bounds) inválidos."
        return go.Figure().update_layout(title=msg, xaxis_visible=False, yaxis_visible=False), None, msg

    grid_lon = np.linspace(gdf_bounds[0] - 0.1, gdf_bounds[2] + 0.1, 150)
    grid_lat = np.linspace(gdf_bounds[1] - 0.1, gdf_bounds[3] + 0.1, 150)
    grid_x, grid_y = np.meshgrid(grid_lon, grid_lat)  # Forma (ny, nx)

    map_metodo = {
        "Kriging Ordinario": "kriging",
        "Kriging con Deriva Externa (KED)": "ked",
        "IDW": "idw",
        "Spline (Thin Plate)": "spline",
    }
    metodo_key = map_metodo.get(method, "kriging")

    dem_grid = None
    if metodo_key == "ked" and Config.ELEVATION_COL in df_clean.columns:
        elevs = pd.to_numeric(df_clean[Config.ELEVATION_COL], errors="coerce").values
        lons_e = df_clean[Config.LONGITUDE_COL].values
        lats_e = df_clean[Config.LATITUDE_COL].values
        valid_e = np.isfinite(elevs)
        if np.sum(valid_e) >= 4:
            dem_grid = griddata((lons_e[valid_e], lats_e[valid_e]), elevs[valid_e], (grid_x, grid_y), method="linear")
            mask_n = np.isnan(dem_grid)
            if np.any(mask_n):
                dem_grid[mask_n] = griddata(
                    (lons_e[valid_e], lats_e[valid_e]),
                    elevs[valid_e],
                    (grid_x[mask_n], grid_y[mask_n]),
                    method="nearest",
                )

    z_grid, _ = interpolador_maestro(
        df_puntos=df_clean,
        col_val=Config.PRECIPITATION_COL,
        grid_x=grid_x,
        grid_y=grid_y,
        metodo=metodo_key,
        modelo_variograma=variogram_model,
        dem_grid=dem_grid,
    )

    # z_grid ya tiene forma exacta (ny, nx) acorde a x=grid_lon, y=grid_lat (sin .T erróneo)
    fig = go.Figure(
        data=go.Contour(
            z=z_grid,
            x=grid_lon,
            y=grid_lat,
            colorscale=px.colors.sequential.YlGnBu,
            colorbar_title="Precipitación (mm)",
            contours=dict(coloring="heatmap", showlabels=True, labelfont=dict(size=10, color="white"), labelformat=".0f"),
            line_smoothing=0.85,
            line_color="black",
            line_width=0.5,
        )
    )

    hover_texts = [
        f"<b>{row[Config.STATION_NAME_COL]}</b><br>"
        f"Municipio: {row.get(Config.MUNICIPALITY_COL, 'N/A')}<br>"
        f"Altitud: {row.get(Config.ALTITUDE_COL, 'N/A')} m<br>"
        f"Ppt. Promedio: {row[Config.PRECIPITATION_COL]:.0f} mm"
        for _, row in df_clean.iterrows()
    ]
    fig.add_trace(
        go.Scatter(
            x=df_clean[Config.LONGITUDE_COL],
            y=df_clean[Config.LATITUDE_COL],
            mode="markers",
            marker=dict(color="red", size=5, line=dict(width=1, color="black")),
            name="Estaciones",
            hoverinfo="text",
            text=hover_texts,
        )
    )
    fig.update_layout(
        title=f"Precipitación Promedio en {period_name} ({method})",
        xaxis_title="Longitud",
        yaxis_title="Latitud",
        height=600,
        legend=dict(x=0.01, y=0.01, bgcolor="rgba(0,0,0,0)"),
    )
    return fig, None, None


@st.cache_data(ttl=3600, max_entries=10, show_spinner=False)
def create_kriging_by_basin(_gdf_points, grid_lon, grid_lat, value_col="Valor"):
    """Wrapper limpio de Kriging Ordinario sobre cuenca (sin widgets de UI dentro del caché)."""
    grid_x, grid_y = np.meshgrid(grid_lon, grid_lat)
    z_grid, std_grid = interpolador_maestro(_gdf_points, value_col, grid_x, grid_y, metodo="kriging")
    variance = (std_grid ** 2) if std_grid is not None else np.zeros_like(z_grid)
    return z_grid, variance


def interpolate_idw(lons, lats, vals, grid_lon, grid_lat, method="idw"):
    """Wrapper de compatibilidad usando IDW real."""
    lons, lats, vals, _ = _limpiar_y_agrupar_puntos(lons, lats, vals)
    grid_x, grid_y = np.meshgrid(grid_lon, grid_lat)
    if len(vals) == 0:
        return np.zeros_like(grid_x)
    z = _interpolar_idw_flat(lons, lats, vals, grid_x.ravel(), grid_y.ravel(), power=2.0)
    return z.reshape(grid_x.shape)


def generate_grid_coordinates(bounds, resolution=100j):
    """Genera malla (gx, gy) a partir de bounds (minx, maxx, miny, maxy)."""
    minx, maxx, miny, maxy = bounds
    return np.mgrid[minx:maxx:resolution, miny:maxy:resolution]


def interpolate_spatial(df_points, val_col, gx, gy, method="linear"):
    """Wrapper de compatibilidad delegado a interpolador_maestro."""
    z, _ = interpolador_maestro(df_points, val_col, gx, gy, metodo=method)
    return z