import sys
import os
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from sqlalchemy import text
import unicodedata
import re
import warnings

# Silenciador de advertencias para mantener tu consola limpia
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)
warnings.simplefilter(action='ignore', category=FutureWarning)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'frontend')))
from backend.app.database import get_engine

def limpiar_texto(texto):
    if pd.isna(texto): return ""
    t = str(texto).upper()
    t = re.sub(r'\(.*?\)', '', t)
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9]', '', t).strip()

print("🌟 FASE 1: Descargando Censo DANE Puro (1985-2042)...")
try:
    url_parquet = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/Poblacion_Colombia_1985_2042_Optimizado.parquet"
    df_dane = pd.read_parquet(url_parquet).copy()
    
    col_mun = next(c for c in df_dane.columns if c.upper() == 'DPMP')
    col_anio = next(c for c in df_dane.columns if c.upper() == 'AÑO')
    col_area = next(c for c in df_dane.columns if c.upper() == 'AREA_GEOGRAFICA')

    df_dane['mun_norm'] = df_dane[col_mun].apply(limpiar_texto)
    df_dane['año'] = pd.to_numeric(df_dane[col_anio], errors='coerce').fillna(1985).astype(int)

    def clasificar_area(x):
        x = str(x).lower()
        if 'cabecera' in x or 'urban' in x: return 'urbana'
        if 'rural' in x or 'centros' in x or 'resto' in x: return 'rural'
        return 'total'

    df_dane['area_limpia'] = df_dane[col_area].apply(clasificar_area)
    cols_pob = [c for c in df_dane.columns if 'Hombre' in c or 'Mujer' in c]
    for c in cols_pob: df_dane[c] = pd.to_numeric(df_dane[c], errors='coerce').fillna(0)
    df_dane['Total'] = pd.concat([df_dane[c] for c in cols_pob], axis=1).sum(axis=1)

    # Base DANE Pivotada: municipio | año | urbana | rural
    df_dane_ur = df_dane[df_dane['area_limpia'].isin(['urbana', 'rural'])].groupby(['mun_norm', 'año', 'area_limpia'], observed=True)['Total'].sum().reset_index()
    df_dane_pivot = df_dane_ur.pivot_table(index=['mun_norm', 'año'], columns='area_limpia', values='Total', fill_value=0, observed=True).reset_index()
    
    if 'urbana' not in df_dane_pivot.columns: df_dane_pivot['urbana'] = 0
    if 'rural' not in df_dane_pivot.columns: df_dane_pivot['rural'] = 0

except Exception as e:
    print(f"Error procesando DANE: {e}"); sys.exit()

print("🏡 FASE 2: Normalizando Matriz de Pesos (Curando micro-fracciones)...")
try:
    df_pesos = pd.read_parquet('backend/app/data/matriz_pesos_veredales.parquet')
    col_terr = 'territorio_norm' if 'territorio_norm' in df_pesos.columns else 'vereda_norm'
    df_pesos = df_pesos.rename(columns={col_terr: 'vereda_norm'})
    for c in ['peso_urbano', 'peso_rural']: df_pesos[c] = pd.to_numeric(df_pesos[c], errors='coerce').fillna(0)

    # Aseguramos que la suma de pesos de un municipio dé exactamente 1.0 (100%)
    sum_u = df_pesos.groupby('mpio_norm')['peso_urbano'].transform('sum').replace(0, 1)
    sum_r = df_pesos.groupby('mpio_norm')['peso_rural'].transform('sum').replace(0, 1)
    
    df_pesos['peso_u_norm'] = df_pesos['peso_urbano'] / sum_u
    df_pesos['peso_r_norm'] = df_pesos['peso_rural'] / sum_r

except Exception as e:
    print(f"Error procesando pesos veredales: {e}"); sys.exit()

print("🌊 FASE 3: Cruzando Geometría (El Santo Grial Dasimétrico)...")
try:
    df_map = pd.read_parquet('backend/app/data/matriz_cuencas_veredas.parquet')
    col_pct = next((c for c in df_map.columns if 'pct' in c.lower()), None)
    df_map['Pct_Raw'] = pd.to_numeric(df_map[col_pct], errors='coerce').fillna(0) if col_pct else 0.0

    # 🛡️ LA CURA AL ERROR DE LOS 0.4 HABITANTES: Normalización Relativa de Áreas
    # Convertimos los "grados" o "metros cuadrados" rotos en Porcentajes Perfectos (0.0 a 1.0)
    sum_area_vereda = df_map.groupby(['mpio_norm', 'vereda_norm'])['Pct_Raw'].transform('sum').replace(0, 1)
    df_map['Pct_Vereda_Real'] = df_map['Pct_Raw'] / sum_area_vereda

    df_cruce = pd.merge(df_map, df_pesos[['mpio_norm', 'vereda_norm', 'peso_u_norm', 'peso_r_norm']], on=['mpio_norm', 'vereda_norm'], how='left')
    df_cruce['peso_u_norm'] = df_cruce['peso_u_norm'].fillna(0)
    df_cruce['peso_r_norm'] = df_cruce['peso_r_norm'].fillna(0)

    # Factor Final Cuenca = (% Demográfico de la Vereda en el Mpio) * (% de Vereda Interceptada)
    df_cruce['Factor_Urbano'] = df_cruce['peso_u_norm'] * df_cruce['Pct_Vereda_Real']
    df_cruce['Factor_Rural'] = df_cruce['peso_r_norm'] * df_cruce['Pct_Vereda_Real']

except Exception as e:
    print(f"Error en cruce espacial: {e}"); sys.exit()

print("🧮 FASE 4: Consolidando Topología Bottom-Up Inquebrantable...")
niveles = ['NSS3', 'NSS2', 'NSS1', 'SZH', 'ZH', 'AH']
def formatear_nombre(row, c_nom, c_id):
    nombre = str(row.get(c_nom, '')).strip()
    codigo = str(row.get(c_id, '')).strip()
    if not nombre or nombre.lower() in ['nan', 'none', '<null>']: return None
    if codigo and codigo.lower() not in ['nan', 'none', '<null>']: return f"{nombre} - ({codigo})"
    return nombre

for niv in niveles:
    col_nom = f"NOM_{niv}" if f"NOM_{niv}" in df_cruce.columns else f"NOM{niv}"
    if col_nom in df_cruce.columns and niv in df_cruce.columns:
        df_cruce[f"FMT_{niv}"] = df_cruce.apply(lambda r: formatear_nombre(r, col_nom, niv), axis=1)

anios_dane = df_dane_pivot['año'].unique()
diccionario_historicos = {}

for niv in niveles:
    col_fmt = f"FMT_{niv}"
    if col_fmt not in df_cruce.columns: continue
    
    # 1. Sumamos factores. Ejemplo: Doña Maria se lleva el 5% de Medellín Urbano y el 90% de Itagüí Urbano.
    df_factores = df_cruce.groupby([col_fmt, 'mpio_norm'])[['Factor_Urbano', 'Factor_Rural']].sum().reset_index()
    df_factores['Factor_Urbano'] = df_factores['Factor_Urbano'].clip(upper=1.0)
    df_factores['Factor_Rural'] = df_factores['Factor_Rural'].clip(upper=1.0)
    
    # 2. Multiplicamos por la masa real histórica del DANE
    df_historico_base = pd.merge(df_factores, df_dane_pivot, left_on='mpio_norm', right_on='mun_norm', how='inner')
    df_historico_base['Pob_Cuenca'] = (df_historico_base['urbana'] * df_historico_base['Factor_Urbano']) + (df_historico_base['rural'] * df_historico_base['Factor_Rural'])
    
    # 3. Sumamos los pedazos municipales
    df_agrupado = df_historico_base.groupby([col_fmt, 'año'])['Pob_Cuenca'].sum().reset_index()
    
    # 4. Esqueleto temporal para que no falte ningún año y el Solver funcione
    entidades_unicas = df_cruce[col_fmt].dropna().unique()
    esqueleto = pd.MultiIndex.from_product([entidades_unicas, anios_dane], names=[col_fmt, 'año']).to_frame(index=False)
    
    df_final_nivel = pd.merge(esqueleto, df_agrupado, on=[col_fmt, 'año'], how='left')
    df_final_nivel['Pob_Cuenca'] = df_final_nivel['Pob_Cuenca'].fillna(0)
    df_final_nivel['año'] = df_final_nivel['año'].astype(int)
    
    diccionario_historicos[niv] = df_final_nivel

print("🧠 FASE 5: Entrenando Regresiones Matemáticas Robustas...")
def f_log(t, k, a, r): return k / (1 + a * np.exp(-r * t))
def f_exp(t, a, b): return a * np.exp(b * t)
def calcular_r2(y_real, y_pred):
    ss_tot = np.sum((y_real - np.mean(y_real)) ** 2)
    return 1 - (np.sum((y_real - y_pred) ** 2) / ss_tot) if ss_tot > 0 else 0

matriz_resultados = []

for escala, df_datos in diccionario_historicos.items():
    territorios = df_datos[f"FMT_{escala}"].dropna().unique()
    
    for terr in territorios:
        df_t = df_datos[df_datos[f"FMT_{escala}"] == terr].sort_values(by='año')
        x = df_t['año'].values.astype(float)
        y = df_t['Pob_Cuenca'].values.astype(float)
        
        if len(x) < 4 or y.sum() == 0:
            matriz_resultados.append({
                'Area': 'Total', 'Nivel': 'Cuenca', 'Territorio': terr, 'Padre': 'N/A',
                'Año_Base': int(x[0]) if len(x)>0 else 1985, 'Pob_Base': 0, 'Log_K': 0, 'Log_a': 0, 'Log_r': 0, 'Log_R2': 0,
                'Exp_a': 0, 'Exp_b': 0, 'Exp_R2': 0, 'Poly_A': 0, 'Poly_B': 0, 'Poly_C': 0, 'Poly_D': 0, 'Poly_R2': 0,
                'Lin_m': 0, 'Lin_b': 0, 'Lin_R2': 0, 'Modelo_Recomendado': 'Ninguno', 'Mejor_R2': 0,
                'LLAVE_UNIVERSAL': f"CUENCA_{limpiar_texto(terr)}_TOTAL"
            })
            continue
        
        x_offset = x[0]
        x_norm = x - x_offset
        p0_val = max(1, y[0])
        max_y = max(y)
        es_creciente = y[-1] >= p0_val
        
        log_k, log_a, log_r, log_r2 = 0, 0, 0, 0
        try:
            k_guess = max_y * 1.1 if es_creciente else max(1, y[-1] * 0.95)
            a_guess = max(-0.999, (k_guess - p0_val) / p0_val if p0_val > 0 else 1)
            limites = ([max_y * 0.8 if es_creciente else y[-1] * 0.5, -0.999, 0.0001], [max_y * 1.5 if es_creciente else max_y * 1.05, np.inf, 0.3])
            popt_log, _ = curve_fit(f_log, x_norm, y, p0=[k_guess, a_guess, 0.02 if es_creciente else -0.02], bounds=limites, maxfev=10000)
            log_k, log_a, log_r = popt_log
            log_r2 = calcular_r2(y, f_log(x_norm, *popt_log))
        except: pass

        exp_a, exp_b, exp_r2 = 0, 0, 0
        try:
            popt_exp, _ = curve_fit(f_exp, x_norm, y, p0=[p0_val, 0.01 if es_creciente else -0.01], maxfev=10000)
            exp_a, exp_b = popt_exp
            exp_r2 = calcular_r2(y, f_exp(x_norm, *popt_exp))
        except: pass

        poly_A, poly_B, poly_C, poly_D, poly_r2 = 0, 0, 0, 0, 0
        try:
            coefs = np.polyfit(x_norm, y, 3)
            poly_A, poly_B, poly_C, poly_D = coefs
            poly_r2 = calcular_r2(y, np.polyval(coefs, x_norm))
        except: pass

        lin_m, lin_b, lin_r2 = 0, 0, 0
        try:
            coefs_lin = np.polyfit(x_norm, y, 1)
            lin_m, lin_b = coefs_lin
            lin_r2 = calcular_r2(y, np.polyval(coefs_lin, x_norm))
        except: pass

        dic_modelos = {'Logístico': log_r2, 'Exponencial': exp_r2, 'Polinomial_3': poly_r2, 'Lineal': lin_r2}
        mejor_modelo = max(dic_modelos, key=dic_modelos.get)

        matriz_resultados.append({
            'Area': 'Total', 'Nivel': 'Cuenca', 'Territorio': terr, 'Padre': 'N/A',
            'Año_Base': int(x_offset), 'Pob_Base': round(p0_val, 0),
            'Log_K': log_k, 'Log_a': log_a, 'Log_r': log_r, 'Log_R2': round(log_r2, 4),
            'Exp_a': exp_a, 'Exp_b': exp_b, 'Exp_R2': round(exp_r2, 4),
            'Poly_A': poly_A, 'Poly_B': poly_B, 'Poly_C': poly_C, 'Poly_D': poly_D, 'Poly_R2': round(poly_r2, 4),
            'Lin_m': lin_m, 'Lin_b': lin_b, 'Lin_R2': round(lin_r2, 4),
            'Modelo_Recomendado': mejor_modelo, 'Mejor_R2': round(dic_modelos[mejor_modelo], 4),
            'LLAVE_UNIVERSAL': f"CUENCA_{limpiar_texto(terr)}_TOTAL"
        })

print("💾 FASE 6: Inyectando al Cerebro PostgreSQL...")
df_nuevas_cuencas = pd.DataFrame(matriz_resultados)
engine = get_engine()

try:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM matriz_maestra_demografica WHERE UPPER(\"Nivel\") = 'CUENCA';"))
        
    df_nuevas_cuencas.to_sql('matriz_maestra_demografica', engine, if_exists='append', index=False, chunksize=500, method='multi')
    print(f"🎉 ¡SISTEMA PERFECTO! {len(df_nuevas_cuencas)} cuencas procesadas con normalización de áreas. El laberinto ha sido superado.")
except Exception as e:
    print(f"🚨 Error en inyección: {e}")