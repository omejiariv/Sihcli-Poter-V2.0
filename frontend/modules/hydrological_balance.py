# frontend/modules/hydrological_balance.py
import numpy as np

def calcular_balance_mensual(precipitacion, etp, area_km2, capacidad_campo=100.0, factor_recarga_base=0.15):
    """
    Ejecuta un modelo de Balance Hídrico distribuido mes a mes (Thornthwaite-Mather).
    Retorna ETR, Almacenamiento, Déficit, Exceso, Recarga y Caudal Medio.
    """
    P = np.array(precipitacion)
    PET = np.array(etp)
    
    S = np.zeros(12)
    ETR = np.zeros(12)
    Exc = np.zeros(12)
    
    s_prev = capacidad_campo 
    
    for anio in range(2):
        for i in range(12):
            if P[i] >= PET[i]:
                ETR[i] = PET[i]
                s_new = s_prev + (P[i] - PET[i])
                
                if s_new > capacidad_campo:
                    Exc[i] = s_new - capacidad_campo
                    S[i] = capacidad_campo
                else:
                    Exc[i] = 0.0
                    S[i] = s_new
            else:
                S[i] = s_prev * np.exp(-(PET[i] - P[i]) / capacidad_campo)
                ETR[i] = P[i] + (s_prev - S[i])
                Exc[i] = 0.0
                
            s_prev = S[i]
            
    # 2. SEPARACIÓN DE FLUJOS (¡Ahora es dinámico según la cobertura!)
    recarga_acuiferos = Exc * factor_recarga_base 
    escorrentia_superficial = Exc * (1.0 - factor_recarga_base)
    
    # 3. CÁLCULO DE CAUDAL (m3/s)
    dias_mes = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    segundos_mes = dias_mes * 24 * 3600
    caudal_m3s = (Exc * area_km2 * 1000) / segundos_mes

    return {
        "etr": [round(float(x), 1) for x in ETR],
        "almacenamiento": [round(float(x), 1) for x in S],
        "deficit": [round(float(p - e), 1) for p, e in zip(PET, ETR)],
        "exceso_total": [round(float(x), 1) for x in Exc],
        "escorrentia": [round(float(x), 1) for x in escorrentia_superficial],
        "recarga": [round(float(x), 1) for x in recarga_acuiferos],
        "caudal_m3s": [round(float(x), 2) for x in caudal_m3s]
    }