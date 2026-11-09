import requests
import unicodedata

def normalizar_texto(t):
    if t is None: return ""
    t = str(t).upper().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')

url_maestro = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson"
url_demografia = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/PoblacionBarrioCorregimiento_optimizado.geojson"

print("⏳ Descargando Territorio Maestro...")
maestro = requests.get(url_maestro).json()
print("⏳ Descargando Base Demográfica...")
demografia = requests.get(url_demografia).json()

# --- CASO 1: GEOMORFOLOGÍA (Altavista / Aldea Pablo VI) ---
print("\n" + "="*50)
print("🏔️ DIAGNÓSTICO: CARGADOR ESPACIAL (Geomorfología / Clima)")
print("="*50)

casos_geo = [("ALDEA PABLO VI", "BARRIO"), ("ALTAVISTA", "VEREDA")]

for target, nivel in casos_geo:
    print(f"\nBuscando: '{target}' (Nivel: {nivel})")
    encontrado = False
    
    for f in maestro.get("features", []):
        props = f.get("properties", {})
        mpio = normalizar_texto(props.get("mpio_cnmbr", ""))
        tipo = str(props.get("tipo", "")).upper()
        nom_barrio = normalizar_texto(props.get("bar_ccnmbr", ""))
        nom_comuna = normalizar_texto(props.get("comu_nmbre", ""))
        
        # Filtramos para imprimir los candidatos que más se parecen
        if mpio == "MEDELLIN" and (target in nom_barrio or target in nom_comuna):
            print(f"  -> Candidato Visto: tipo='{tipo}', bar_ccnmbr='{nom_barrio}', comu_nmbre='{nom_comuna}'")
            
            # Simulamos el filtro exacto actual de utils.py
            if nivel == "BARRIO" and tipo == "BARRIO" and nom_barrio == target:
                print("  ✅ MATCH EXACTO LOGRADO!")
                encontrado = True
            elif nivel == "VEREDA" and tipo == "CORREGIMIENTO" and nom_comuna == target:
                print("  ✅ MATCH EXACTO LOGRADO!")
                encontrado = True
                
    if not encontrado:
        print("  ❌ FRACASO: Ningún candidato superó el filtro exacto.")

# --- CASO 2: DEMOGRAFÍA (Laureles) ---
print("\n" + "="*50)
print("📈 DIAGNÓSTICO: EXTRACTOR DEMOGRÁFICO (Comunas)")
print("="*50)

target_demo = "LAURELES"
print(f"Buscando Comuna: '{target_demo}' en el archivo demográfico")

# 1. Simular la detección del código de comuna
dict_comunas = {
    "01": "POPULAR", "02": "SANTA CRUZ", "03": "MANRIQUE", "04": "ARANJUEZ",
    "05": "CASTILLA", "06": "DOCE DE OCTUBRE", "07": "ROBLEDO", "08": "VILLA HERMOSA",
    "09": "BUENOS AIRES", "10": "LA CANDELARIA", "11": "LAURELES - ESTADIO", "12": "LA AMERICA",
    "13": "SAN JAVIER", "14": "EL POBLADO", "15": "GUAYABAL", "16": "BELEN"
}

codigo_encontrado = None
for cod, nom in dict_comunas.items():
    nom_norm = normalizar_texto(nom)
    if nom_norm == target_demo or target_demo in nom_norm or nom_norm in target_demo:
        codigo_encontrado = cod
        print(f"  ✅ Diccionario: '{target_demo}' hace match con la clave '{nom_norm}' (Código: {cod})")
        break

if not codigo_encontrado:
    print(f"  ❌ FRACASO: '{target_demo}' no superó la lógica difusa del diccionario.")
else:
    # 2. Simular el agrupamiento de barrios por ese código
    barrios_agrupados = 0
    for f in demografia.get("features", []):
        props = f.get("properties", {})
        cod_b = str(props.get("Cod_Barrio", "")).zfill(4)
        
        if cod_b.startswith(codigo_encontrado):
            barrios_agrupados += 1
            
    print(f"  -> Barrios agrupados con el código {codigo_encontrado}: {barrios_agrupados}")
    if barrios_agrupados == 0:
        print(f"  ❌ FRACASO: El código {codigo_encontrado} no hizo match con ningún 'Cod_Barrio' (revisar si el código en el JSON es diferente, ej. '11' vs '1101').")