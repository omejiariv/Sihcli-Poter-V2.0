import requests
import pandas as pd
import unicodedata

def normalizar_texto(t):
    if pd.isna(t): return ""
    t = str(t).upper().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')

url_maestro = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson"
url_pob = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/PoblacionBarrioCorregimiento_optimizado.geojson"

print("⏳ Descargando Territorio Maestro...")
resp_maestro = requests.get(url_maestro).json()
print("⏳ Descargando Población (Edades)...")
resp_pob = requests.get(url_pob).json()

# 1. Extraer Nombres de TerritorioMaestro (Solo Medellín)
maestro_data = []
for f in resp_maestro.get('features', []):
    props = f.get('properties', {})
    mpio = str(props.get('mpio_cnmbr', '')).upper()
    
    if 'MEDELLIN' in normalizar_texto(mpio):
        tipo = str(props.get('tipo', '')).upper()
        barrio_vereda = str(props.get('bar_ccnmbr', '')).strip()
        comuna_correg = str(props.get('comu_nmbre', '')).strip()
        
        # Simulamos la lógica del menú
        nombre_extraido = ""
        if tipo == "BARRIO":
            nombre_extraido = barrio_vereda
        elif tipo == "CORREGIMIENTO":
            # Para veredas, tomamos el nombre de la vereda. Si no hay, tomamos el corregimiento.
            nombre_extraido = barrio_vereda if barrio_vereda and barrio_vereda.upper() not in ["NONE", "NAN", ""] else comuna_correg
            
        if nombre_extraido and nombre_extraido.upper() not in ["NONE", "NAN", ""]:
            norm = normalizar_texto(nombre_extraido)
            maestro_data.append({
                'Nombre_Original': nombre_extraido,
                'ID_Cruce': norm,
                'Tipo': tipo,
                'Padre': comuna_correg
            })

df_maestro = pd.DataFrame(maestro_data)

# 2. Extraer Nombres de Datos Demográficos (Edades)
pob_data = []
for f in resp_pob.get('features', []):
    props = f.get('properties', {})
    nombre = props.get('NombreBarr', '')
    if nombre:
        norm = normalizar_texto(nombre)
        pob_data.append({
            'Nombre_Demografico': nombre,
            'ID_Cruce': norm,
            'Pob_Total': props.get('Pob_Total', 0)
        })

df_pob = pd.DataFrame(pob_data)

# 3. Cruzar Bases de Datos
cruce = pd.merge(df_maestro, df_pob, on='ID_Cruce', how='outer', indicator=True)

solo_maestro = cruce[cruce['_merge'] == 'left_only'].sort_values('ID_Cruce')
solo_pob = cruce[cruce['_merge'] == 'right_only'].sort_values('ID_Cruce')
duplicados = cruce[cruce.duplicated(subset=['ID_Cruce'], keep=False)].sort_values('ID_Cruce')

# 4. REPORTE FORENSE
print("\n" + "="*50)
print("📊 REPORTE DE AUDITORÍA DEMOGRÁFICA")
print("="*50)
print(f"Total en Maestro (Medellín): {len(df_maestro)}")
print(f"Total en Datos Población: {len(df_pob)}")
print(f"Cruces Perfectos: {len(cruce[cruce['_merge'] == 'both'])}\n")

print("🚨 FANTASMAS EN DEMOGRAFÍA (Están en población pero no en el mapa):")
for _, r in solo_pob.iterrows():
    print(f"  - {r['Nombre_Demografico']} (ID_Cruce: {r['ID_Cruce']})")

print("\n🚨 REBELDES EN EL MAPA (Están en el mapa pero no tienen población):")
for _, r in solo_maestro.iterrows():
    print(f"  - {r['Nombre_Original']} (Padre: {r['Padre']})")

print("\n⚠️ DUPLICADOS (Nombres repetidos que causarán conflictos):")
if not duplicados.empty:
    for _, r in duplicados.iterrows():
        n1 = str(r['Nombre_Original'])
        n2 = str(r['Nombre_Demografico'])
        print(f"  - ID_Cruce: {r['ID_Cruce']} | Mapa: {n1} | Población: {n2}")
else:
    print("  - Ninguno. Todo limpio.")