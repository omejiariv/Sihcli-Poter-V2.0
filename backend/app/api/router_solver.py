# backend/app/api/router_solver.py
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import warnings

# Silenciamos warnings de scipy por desbordamientos matemáticos temporales
warnings.filterwarnings('ignore')

router = APIRouter(prefix="/api/solver", tags=["Motor Matemático y Optimización"])

# Estructura de datos que esperamos recibir desde Streamlit
class DatosHistoricos(BaseModel):
    anios: List[float]
    poblacion: List[float]
    anio_destino: int
    horizonte_extra: int = 30 # Años extra para proyectar por defecto

# =================================================================
# 🧮 FÓRMULAS MATEMÁTICAS (Rescatadas de V1)
# =================================================================
def f_exp(t, p0, r): return p0 * np.exp(r * t)
def f_log(t, k, a, r): return k / (1 + a * np.exp(-r * t))
def f_geom(t, p0, r): return p0 * (1 + r)**t
def f_poly2(t, a, b, c): return a*t**2 + b*t + c
def f_poly3(t, a, b, c, d): return a*t**3 + b*t**2 + c*t + d
def f_lin(t, m, b): return m*t + b

def calcular_r2(y_real, y_prediccion):
    ss_res = np.sum((y_real - y_prediccion) ** 2)
    ss_tot = np.sum((y_real - np.mean(y_real)) ** 2)
    return 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

# =================================================================
# 🚀 RUTA DEL SOLVER (Cálculo Dinámico)
# =================================================================
@router.post("/optimizar")
def optimizar_curvas(datos: DatosHistoricos):
    if len(datos.anios) < 3:
        raise HTTPException(status_code=400, detail="Se requieren al menos 3 puntos históricos para optimizar.")

    try:
        from scipy.optimize import curve_fit
        
        t_data_raw = np.array(datos.anios, dtype=float)
        p_data = np.array(datos.poblacion, dtype=float)
        
        x_offset = t_data_raw.min()
        t_data = t_data_raw - x_offset
        p0_val = max(1e-5, p_data[0])
        max_y = max(p_data)
        es_creciente = p_data[-1] >= p0_val

        # Configurar eje de tiempo para proyecciones
        año_maximo = max(datos.anio_destino, int(t_data_raw.max()) + datos.horizonte_extra)
        t_total_raw = np.arange(x_offset, año_maximo + 1)
        t_total = t_total_raw - x_offset

        resultados = {
            "anios_proyeccion": t_total_raw.tolist(),
            "modelos": {}
        }

        # 1. EXPONENCIAL
        try:
            r_guess = 0.01 if es_creciente else -0.01
            popt_exp, _ = curve_fit(f_exp, t_data, p_data, p0=[p0_val, r_guess], maxfev=10000)
            y_pred = f_exp(t_total, *popt_exp)
            r2_val = calcular_r2(p_data, f_exp(t_data, *popt_exp))
            resultados["modelos"]["Exponencial"] = {
                "popt": popt_exp.tolist(), "r2": float(r2_val), "proyeccion": y_pred.tolist()
            }
        except: pass

        # 2. LOGÍSTICO (Con tu corsé y límites anti-explosión)
        try:
            k_guess = max_y * 1.5 if es_creciente else max(1, p_data[-1] * 0.95)
            a_guess = max(-0.999, (k_guess - p0_val) / p0_val)
            r_guess = 0.02 if es_creciente else -0.02
            k_min = max_y * 0.8 if es_creciente else p_data[-1] * 0.5
            limites = ([k_min, -0.999, -0.2], [max_y * 5, np.inf, 0.3])
            
            popt_log, _ = curve_fit(f_log, t_data, p_data, p0=[k_guess, a_guess, r_guess], bounds=limites, maxfev=25000)
            y_pred = f_log(t_total, *popt_log)
            r2_val = calcular_r2(p_data, f_log(t_data, *popt_log))
            resultados["modelos"]["Logístico"] = {
                "popt": popt_log.tolist(), "r2": float(r2_val), "proyeccion": y_pred.tolist()
            }
        except: pass

        # 3. GEOMÉTRICO
        try:
            popt_geom, _ = curve_fit(f_geom, t_data, p_data, p0=[p0_val, 0.01], maxfev=10000)
            y_pred = f_geom(t_total, *popt_geom)
            r2_val = calcular_r2(p_data, f_geom(t_data, *popt_geom))
            resultados["modelos"]["Geométrico"] = {
                "popt": popt_geom.tolist(), "r2": float(r2_val), "proyeccion": y_pred.tolist()
            }
        except: pass

        # 4. POLINOMIAL (Grado 2 y 3)
        try:
            popt_p2, _ = curve_fit(f_poly2, t_data, p_data)
            y_pred = f_poly2(t_total, *popt_p2)
            r2_val = calcular_r2(p_data, f_poly2(t_data, *popt_p2))
            resultados["modelos"]["Polinómico (Grado 2)"] = {
                "popt": popt_p2.tolist(), "r2": float(r2_val), "proyeccion": y_pred.tolist()
            }
            
            popt_p3, _ = curve_fit(f_poly3, t_data, p_data)
            y_pred = f_poly3(t_total, *popt_p3)
            r2_val = calcular_r2(p_data, f_poly3(t_data, *popt_p3))
            resultados["modelos"]["Polinómico (Grado 3)"] = {
                "popt": popt_p3.tolist(), "r2": float(r2_val), "proyeccion": y_pred.tolist()
            }
        except: pass

        # 5. LINEAL
        try:
            popt_lin, _ = curve_fit(f_lin, t_data, p_data)
            y_pred = f_lin(t_total, *popt_lin)
            r2_val = calcular_r2(p_data, f_lin(t_data, *popt_lin))
            resultados["modelos"]["Lineal"] = {
                "popt": popt_lin.tolist(), "r2": float(r2_val), "proyeccion": y_pred.tolist()
            }
        except: pass

        # Determinar el ganador
        mejor_r2 = -1.0
        mejor_modelo = "Ninguno"
        for mod, metricas in resultados["modelos"].items():
            if metricas["r2"] > mejor_r2:
                mejor_r2 = metricas["r2"]
                mejor_modelo = mod
                
        resultados["ganador"] = {"modelo": mejor_modelo, "r2": float(mejor_r2)}
        
        return resultados

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el motor matemático: {str(e)}")