import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'frontend')))

import pandas as pd
from sqlalchemy import text
from backend.app.database import get_engine
import unicodedata
import re

def limpiar_fuerte(texto):
    if not texto or pd.isna(texto): return ""
    t = str(texto).upper()
    t = re.sub(r'\(.*?\)', '', t)
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9]', '', t).strip()

def reparar_numero_corrupto(val):
    if pd.isna(val): return None
    val = str(val).strip()
    if val in ["", "None", "nan"]: return None
    
    try:
        # Si es un número normal (ej: 0.9933) pasa directo
        if val.count('.') <= 1: return float(val)
        
        # Desencriptador de la corrupción de Excel (9 decimales)
        clean_str = val.replace('.', '')
        is_neg = clean_str.startswith('-')
        if is_neg: clean_str = clean_str[1:]
        
        if len(clean_str) > 9:
            integer_part = clean_str[:-9]
            if not integer_part: integer_part = '0'
            decimal_part = clean_str[-9:]
            final_str = integer_part + '.' + decimal_part
            return float('-' + final_str if is_neg else final_str)
        else:
            return float(val.replace('.', '', val.count('.') - 1))
    except:
        return None

print("🌟 1. Cargando la Matriz Base de Marzo...")
# Asegúrate de que el archivo esté en la raíz donde corres el script
df_marzo = pd.read_csv('Matriz_Maestra_Demografica.csv', sep=';', dtype=str)

columnas_numericas = [
    'Pob_Base', 'Log_K', 'Log_a', 'Log_r', 'Log_R2', 
    'Exp_a', 'Exp_b', 'Exp_R2', 'Poly_A', 'Poly_B', 
    'Poly_C', 'Poly_D', 'Poly_R2', 'Mejor_R2'
]

print("🛠️ 2. Desencriptando y reparando números corruptos de Excel...")
for col in columnas_numericas:
    if col in df_marzo.columns:
        df_marzo[col] = df_marzo[col].apply(reparar_numero_corrupto)

print("🔑 3. Reconstruyendo Llaves Universales...")
df_marzo['LLAVE_UNIVERSAL'] = df_marzo.apply(
    lambda r: f"{str(r['Nivel']).upper()}_{limpiar_fuerte(r['Territorio'])}_{str(r['Area']).upper()}", axis=1
)

print("🚀 4. Inyectando la Matriz Sanada al Cerebro PostgreSQL...")
engine = get_engine()
try:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE matriz_maestra_demografica;"))
        
    df_marzo.to_sql('matriz_maestra_demografica', engine, if_exists='append', index=False, chunksize=500, method='multi')
    print("🎉 ¡MATRIZ DE MARZO RESTAURADA CON ÉXITO! La pesadilla numérica ha terminado.")
except Exception as e:
    print(f"🚨 Error en inyección: {e}")