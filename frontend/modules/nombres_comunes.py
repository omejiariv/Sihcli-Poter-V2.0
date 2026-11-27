# frontend/modules/nombres_comunes.py
import re
import pandas as pd

# Diccionario curado de nombres comunes en Antioquia / Colombia (clave: género especie en minúscula)
NOMBRES_COMUNES_ANTIOQUIA = {
    # --- FLORA NATIVA, AMENAZADA Y ENDÉMICA ---
    "quercus humboldtii": "Roble andino",
    "cedrela odorata": "Cedro amargo / Cedro rojo",
    "swietenia macrophylla": "Caoba",
    "aniba perutilis": "Comino crespo",
    "cariniana pyriformis": "Abarco",
    "handroanthus chrysanthus": "Guayacán amarillo / Araguaney",
    "handroanthus ochraceus": "Guayacán amarillo",
    "guazuma ulmifolia": "Guásimo",
    "bursera simaruba": "Indio desnudo / Resbalamono",
    "cordia alliodora": "Nogal cafetero / Laurel",
    "gliricidia sepium": "Matarratón",
    "espeletia frontinoensis": "Frailejón de Frontino",
    "espeletia praefrontina": "Frailejón",
    "clusia alata": "Chagualo / Chagualón",
    "vismia laevis": "Carate / Punta de lanza",
    "jacaranda hesperia": "Gualanday",
    "brunellia amayensis": "Cedrillo",
    "persea chrysophylla": "Aguacatillo",
    "croton aristophlebius": "Drago / Sangregao",
    "linochilus antioquensis": "Romerillo de Antioquia",
    "epidendrum uribei": "Orquídea de Uribe",
    "catasetum tabulare": "Orquídea catasetum",
    "elaeis oleifera": "Palma nolí / Corozo",
    "ceroxylon quindiuense": "Palma de cera del Quindío",
    "retrophyllum rospigliosii": "Pino romerón",
    "alnus acuminata": "Aliso",
    "juglans neotropica": "Cedro negro / Nogal",
    "magnolia espinalii": "Magnolia de Espinal / Hojarasco",
    "magnolia yarumalensis": "Almanegra de Yarumal",
    "ingo edulis": "Guamo santafereño",
    "inga edulis": "Guamo santafereño",
    "erythrina poeppigiana": "Cámbulo / Pízamo",
    "cecropia peltata": "Yarumo",
    "cecropia teleincana": "Yarumo blanco",
    "trichanthera gigantea": "Nacedero / Quiebrabarrigo",
    "montanoa quadrangularis": "Árboloco",
    "weinmannia pubescens": "Encenillo",
    "tibouchina lepidota": "Sietecueros",
    "andesanthus lepidotus": "Sietecueros",
    "freziera canescens": "Cerezo de monte",

    # --- FLORA EXÓTICA E INVASORA (ALERTA EN RESTAURACIÓN) ---
    "thunbergia alata": "Ojo de poeta (Invasora)",
    "acacia melanoxylon": "Acacia negra (Riesgo invasión)",
    "leucaena leucocephala": "Leucaena (Riesgo invasión)",
    "eucalyptus grandis": "Eucalipto (Exótica)",
    "pinus patula": "Pino pátula (Exótica)",
    "ulex europaeus": "Retamo espinoso (Invasora)",
    "hedychium coronarium": "Matandrea / Jengibre blanco (Invasora)",
    "syzygium jambos": "Pomarrosa (Exótica)",
    "psidium guajava": "Guayabo",
    "coffea arabica": "Café",

    # --- AVES ---
    "hypopyrrhus pyrohypogaster": "Cacique candela",
    "ara militaris": "Guacamaya verde",
    "ognorhynchus icterotis": "Loro orejiamarillo",
    "lipaugus weberi": "Arriero antioqueño",
    "capito hypoleucus": "Torito dorsiblanco",
    "thryophilus sernai": "Cucarachero paisa",
    "setophaga cerulea": "Reinita cerúlea",
    "setophaga fusca": "Reinita gorjinaranja",
    "setophaga castanea": "Reinita castaña",
    "setophaga petechia": "Reinita amarilla",
    "scytalopus stilesi": "Tapaculo de Stiles",
    "icterus icterus": "Turpial",
    "sicalis flaveola": "Canario costeño / Chirigüe",
    "tyrannus melancholicus": "Sirirí común",
    "thraupis episcopus": "Azulejo común",
    "thraupis palmarum": "Azulejo palmero",
    "coragyps atratus": "Gallinazo / Chulo",
    "cathartes aura": "Guala cabecirroja",
    "pitangus sulphuratus": "Bichofué",
    "turdus ignobilis": "Mirla embarradora",
    "rupornis magnirostris": "Gavilán caminero",
    "ortalis columbiana": "Guacharaca colombiana",
    "amazilia tzacatl": "Colibrí colirrufo",
    "colibri coruscans": "Colibrí chillón",
    "forpus conspicillatus": "Periquito de anteojos",
    "brotogeris jugularis": "Perico bronceado",
    "pionus chalcopterus": "Cotorra maicera",
    "pionus menstruus": "Cotorra cabeciazul",
    "piranga rubra": "Piranga roja",
    "bubulcus ibis": "Garza bueyera",
    "columba livia": "Paloma doméstica (Exótica)",

    # --- MAMÍFEROS, ANFIBIOS, REPTILES Y PECES ---
    "didelphis marsupialis": "Zarigüeya / Chucha común",
    "tremarctos ornatus": "Oso de anteojos / Oso andino",
    "puma concolor": "Puma",
    "leopardus pardalis": "Ocelote / Tigrillo",
    "alouatta seniculus": "Mono aullador rojo",
    "saguinus leucopus": "Tití gris",
    "prochilodus magdalenae": "Bocachico",
    "pimelodus grosskopfii": "Capaz / Barbudo",
    "pseudoplatystoma magdaleniatum": "Bagre rayado del Magdalena",
    "sorubim cuspicaudus": "Blanquillo",
    "leporinus muyscorum": "Comelón / Liseta",
    "ichthyoelephas longirostris": "Pataló",
    "brycon moorei": "Dorada",
    "oreochromis niloticus": "Tilapia nilótica (Invasora)",
    "dendrobates truncatus": "Rana venenosa de rayas amarillas",
    "andinobates opisthomelas": "Rana venenosa andina",
    "oophaga histrionica": "Rana arlequín",
    "bolitoglossa hypacra": "Salamandra de Frontino",
    "pristimantis paisa": "Rana de lluvia paisa",
    "lithobates catesbeianus": "Rana toro (Invasora)",
    "chelonoidis carbonarius": "Morrocoy",
    "iguana iguana": "Iguana verde",
    "apis mellifera": "Abeja melífera (Exótica)",
    "tetragonisca angustula": "Abeja angelita (Nativa)",
}

# Paleta técnica de restauración eco-hidrológica por Zona de Vida (Holdridge)
PALETA_RESTAURACION_HOLDRIDGE = {
    "bh-MB": [
        ("Quercus humboldtii", "Roble andino", "Dosel estructural y alta retención hídrica"),
        ("Alnus acuminata", "Aliso", "Fijador de nitrógeno en franjas riparias"),
        ("Juglans neotropica", "Cedro negro", "Especie amenazada de alto valor ecológico"),
        ("Weinmannia pubescens", "Encenillo", "Regulación hídrica de suelos de ladera"),
        ("Andesanthus lepidotus", "Sietecueros", "Pionera melífera para bordes de bosque"),
        ("Retrophyllum rospigliosii", "Pino romerón", "Conífera nativa de bosques de niebla"),
    ],
    "bmh-MB": [
        ("Quercus humboldtii", "Roble andino", "Especie sombrilla y regulación de escorrentía"),
        ("Magnolia espinalii", "Magnolia de Espinal", "Endémica amenazada de bosques húmedos"),
        ("Alnus acuminata", "Aliso", "Estabilización de taludes y rondas hídricas"),
        ("Clusia alata", "Chagualo", "Alta captura de niebla y refugio de avifauna"),
        ("Cecropia teleincana", "Yarumo blanco", "Pionera rápida para recuperación de claros"),
    ],
    "bh-PM": [
        ("Cedrela odorata", "Cedro amargo", "Especie amenazada clave en corredores riparios"),
        ("Trichanthera gigantea", "Nacedero / Quiebrabarrigo", "Protector de nacimientos de agua"),
        ("Aniba perutilis", "Comino crespo", "Especie en Peligro Crítico (Res. 0126)"),
        ("Inga edulis", "Guamo santafereño", "Sombra rápida, nitrógeno y alimento para fauna"),
        ("Montanoa quadrangularis", "Árboloco", "Control de erosión en laderas cafeteras"),
        ("Cordia alliodora", "Nogal cafetero", "Especie maderable nativa multipropósito"),
    ],
    "bmh-PM": [
        ("Aniba perutilis", "Comino crespo", "Prioridad máxima de conservación (CR)"),
        ("Trichanthera gigantea", "Nacedero", "Amortiguamiento de rondas y quebradas"),
        ("Cedrela odorata", "Cedro amargo", "Enriquecimiento de rastrojos altos"),
        ("Erythrina poeppigiana", "Cámbulo", "Sombra y conectividad para aves migratorias"),
        ("Inga edulis", "Guamo", "Recuperación de suelos degradados"),
    ],
    "bh-T": [
        ("Cariniana pyriformis", "Abarco", "Especie en Peligro Crítico de tierras bajas"),
        ("Swietenia macrophylla", "Caoba", "Especie amenazada de alto valor estructural"),
        ("Handroanthus chrysanthus", "Guayacán amarillo", "Conectividad y polinizadores"),
        ("Guazuma ulmifolia", "Guásimo", "Pionera resistente para potreros degradados"),
        ("Bursera simaruba", "Indio desnudo", "Cercas vivas y restauración rápida"),
    ],
    "bs-T": [
        ("Handroanthus chrysanthus", "Guayacán amarillo", "Tolerante a sequía estacional"),
        ("Guazuma ulmifolia", "Guásimo", "Forraje, sombra y recuperación de suelo"),
        ("Gliricidia sepium", "Matarratón", "Fijador de nitrógeno y cercas vivas"),
        ("Bursera simaruba", "Indio desnudo", "Alta supervivencia en déficit hídrico"),
        ("Cedrela odorata", "Cedro amargo", "Refugio en vegas y rondas hídricas"),
    ],
}


def limpiar_binomio(nombre: str) -> str:
    """Extrae 'genero especie' en minúsculas ignorando autor y año (ej. 'Sicalis flaveola (Linnaeus, 1766)')."""
    if not nombre or pd.isna(nombre):
        return ""
    limpio = re.sub(r"\(.*?\)", "", str(nombre)).strip()
    partes = limpio.split()
    if len(partes) >= 2:
        return f"{partes[0]} {partes[1]}".lower()
    return limpio.lower()


def buscar_nombre_comun(nombre_cientifico: str) -> str:
    return NOMBRES_COMUNES_ANTIOQUIA.get(limpiar_binomio(nombre_cientifico), "")


def enriquecer_nombres_comunes(df: pd.DataFrame, col_cientifico: str = "Especie", col_comun: str = "Nombre Común") -> pd.DataFrame:
    """Rellena nombres comunes vacíos o 'None' usando el diccionario curado de Antioquia."""
    if df is None or df.empty or col_cientifico not in df.columns:
        return df
    out = df.copy()
    if col_comun not in out.columns:
        out[col_comun] = ""

    def _resolver(row):
        actual = row.get(col_comun)
        if actual is not None and not pd.isna(actual) and str(actual).strip() not in ["", "None", "nan", "Sin Dato"]:
            return str(actual).strip()
        return buscar_nombre_comun(row.get(col_cientifico, "")) or "—"

    out[col_comun] = out.apply(_resolver, axis=1)
    return out


def obtener_paleta_por_zona_vida(zona_vida_txt: str):
    """Retorna (codigo_zv, lista_especies) a partir del nombre de Zona de Vida de Holdridge."""
    import unicodedata

    txt = unicodedata.normalize("NFKD", str(zona_vida_txt or "").lower())
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")

    # El orden importa: evaluar "muy humedo / pluvial" antes que "humedo"
    if any(k in txt for k in ["bmh-mb", "bmh-m", "bp-mb", "bp-m", "muy humedo montano", "pluvial montano"]):
        return "bmh-MB", PALETA_RESTAURACION_HOLDRIDGE["bmh-MB"]
    if any(k in txt for k in ["bh-mb", "bh-m", "humedo montano"]):
        return "bh-MB", PALETA_RESTAURACION_HOLDRIDGE["bh-MB"]
    if any(k in txt for k in ["bmh-pm", "bp-pm", "muy humedo premontano", "pluvial premontano"]):
        return "bmh-PM", PALETA_RESTAURACION_HOLDRIDGE["bmh-PM"]
    if any(k in txt for k in ["bh-pm", "humedo premontano"]):
        return "bh-PM", PALETA_RESTAURACION_HOLDRIDGE["bh-PM"]
    if any(k in txt for k in ["bs-t", "me-t", "seco tropical", "monte espinoso"]):
        return "bs-T", PALETA_RESTAURACION_HOLDRIDGE["bs-T"]
    if any(k in txt for k in ["bh-t", "bmh-t", "bp-t", "humedo tropical", "pluvial tropical"]):
        return "bh-T", PALETA_RESTAURACION_HOLDRIDGE["bh-T"]

    # Respaldo andino por defecto para Antioquia
    return "bh-MB", PALETA_RESTAURACION_HOLDRIDGE["bh-MB"]