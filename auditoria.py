import pandas as pd
import re
import unicodedata

def aplanador_extremo(txt):
    if not txt: return ""
    t = str(txt).upper().replace("Ñ", "N")
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9]', '', t)

# Cargamos las matrices de tu backend
df_inter = pd.read_parquet("backend/app/data/matriz_cuencas_veredas.parquet")
df_pesos = pd.read_parquet("backend/app/data/matriz_pesos_veredales.parquet")

cuenca = aplanador_extremo("R. GRANDE - CHICO - NSS")
mask = df_inter['nom_nss1'].astype(str).apply(aplanador_extremo) == cuenca
df_c = df_inter[mask]

df_cruce = df_c.merge(df_pesos, on=['mpio_norm', 'vereda_norm'])
df_cruce['factor_urb'] = df_cruce['Pct_Vereda_en_Cuenca'] * df_cruce['peso_urbano']
df_cruce['factor_rur'] = df_cruce['Pct_Vereda_en_Cuenca'] * df_cruce['peso_rural']

print(f"\n🌍 --- AUDITORÍA DASIMÉTRICA: {cuenca} ---")
print(f"Total de polígonos (veredas/cabeceras) que toca el río: {len(df_cruce)}")

urb = df_cruce[df_cruce['factor_urb'] > 0]
print("\n🏙️ 1. POBLACIÓN URBANA INYECTADA (Cabeceras interceptadas):")
if urb.empty:
    print(">> NINGUNA. El polígono de esta cuenca NO toca el casco urbano de ningún municipio.")
    print(">> (El 100% de la población de la ciudad quedó correctamente excluida).")
else:
    print(urb[['mpio_norm', 'vereda_norm', 'factor_urb']])

rur = df_cruce[df_cruce['factor_rur'] > 0].groupby('mpio_norm')['factor_rur'].sum().reset_index()
print("\n🌾 2. POBLACIÓN RURAL INYECTADA (% del campo que cubre la cuenca):")
print(rur)