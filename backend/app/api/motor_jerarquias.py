# backend/app/api/motor_jerarquias.py

import re
import unicodedata
import pandas as pd

# =================================================================
# 📚 DICCIONARIOS MAESTROS (Rescatados de V1)
# =================================================================
REGIONES_COL = {
    'Caribe': ['Atlántico', 'Bolívar', 'Cesar', 'Córdoba', 'La Guajira', 'Magdalena', 'Sucre', 'Archipiélago De San Andrés'],
    'Pacífica': ['Cauca', 'Chocó', 'Nariño', 'Valle Del Cauca'],
    'Andina': ['Antioquia', 'Boyacá', 'Caldas', 'Cundinamarca', 'Huila', 'Norte De Santander', 'Quindio', 'Risaralda', 'Santander', 'Tolima', 'Bogotá, D.C.'],
    'Orinoquía': ['Arauca', 'Casanare', 'Meta', 'Vichada'],
    'Amazonía': ['Amazonas', 'Caquetá', 'Guainía', 'Guaviare', 'Putumayo', 'Vaupés']
}

MPIOS_AMVA = ['MEDELLIN', 'BELLO', 'ITAGUI', 'ENVIGADO', 'SABANETA', 'COPACABANA', 'LAESTRELLA', 'GIRARDOTA', 'CALDAS', 'BARBOSA']

DICCIONARIO_REBELDES = {
    "BOGOTADC": "BOGOTA", "SANJOSEDECUCUTA": "CUCUTA", "LAGUAJIRA": "GUAJIRA", 
    "VALLE": "VALLEDELCAUCA", "VILLADESANDIEGODEUBATE": "UBATE", "SANTIAGODETOLU": "TOLU",
    "PUEBLORRICO": "PUEBLORICO", "BRICENO": "BRICEN0",
    "PIZARRO": "BAJOBAUDO", "DOCORDO": "ELLITORALDELSANJUAN", "LITORALDELSANJUAN": "ELLITORALDELSANJUAN",
    "BAHIASOLANO": "BAHIASOLANOMUTIS", "TUMACO": "SANANDRESDETUMACO", "PATIA": "PATIAELBORDO",
    "LOPEZDEMICAY": "LOPEZ", "MAGUI": "MAGUIPAYAN", "ROBERTOPAYAN": "ROBERTOPAYANSANJOSE",
    "MALLAMA": "MALLAMAPIEDRAANCHA", "CUASPUD": "CUASPUDCARLOSAMA", "ALTOBAUDO": "ALTOBAUDOPIEDEPATO",
    "OLAYAHERRERA": "OLAYAHERRERABOCASDESATINGA", "SANTACRUZ": "SANTACRUZGUACHAVEZ",
    "LOSANDES": "LOSANDESSOTOMAYOR", "FRANCISCOPIZARRO": "FRANCISCOPIZARROSALAHONDA",
    "MEDIOSANJUAN": "ELLITORALDELSANJUANDOCORDO", "ELCANTONDELSANPABLO": "ELCANTONDESANPABLOMANAGRU",
    "ATRATO": "ATRATOYUTO", "LEGUIZAMO": "PUERTOLEGUIZAMO", "BARRANCOMINAS": "BARRANCOMINA",
    "MAPIRIPANA": "PANAPANA", "MORICHAL": "MORICHALNUEVO", "SANANDRESSOTAVENTO": "SANANDRESDESOTAVENTO",
    "SANLUISDESINCE": "SINCE", "SANVICENTEDECHUCURI": "SANVICENTEDELCHUCURI", "ELCARMENDECHUCURI": "ELCARMEN",
    "ARIGUANI": "ARIGUANIELDIFICIL", "SANMIGUEL": "SANMIGUELLADORADA", "VILLADELEYVA": "VILLADELEIVA",
    "PURACE": "PURACECOCONUCO", "ELTABLONDEGOMEZ": "ELTABLON", "ARMERO": "ARMEROGUAYABAL",
    "COLON": "COLONGENOVA", "SANPEDRODECARTAGO": "SANPEDRODECARTAGOCARTAGO", "CERROSANANTONIO": "CERRODESANANTONIO",
    "ARBOLEDA": "ARBOLEDABERRUECOS", "ENCINO": "ELENCINO", "MACARAVITA": "MARACAVITA",
    "TUNUNGUA": "TUNUNGA", "LAMONTANITA": "MONTANITA", "ELPAUJIL": "PAUJIL", "VILLARICA": "VILLARRICA",
    "GUADALAJARADEBUGA": "BUGA", "CARTAGENA": "CARTAGENADEINDIAS", "PIENDAMO": "PIENDAMOTUNIA",
    "MARIQUITA": "SANSEBASTIANDEMARIQUITA", "TOLUVIEJO": "SANJOSEDETOLUVIEJO", "SOTARA": "SOTARAPAISPAMBA",
    "PURISIMA": "PURISIMADELACONCEPCION", "GUICAN": "GUICANDELASIERRA", "PAPUNAUACD": "PAPUNAHUA",
    "PAPUNAUA": "PAPUNAHUA", "CHIBOLO": "CHIVOLO", "MANAUREBALCONDELCESAR": "MANAURE",
    "SANTAFEDEANTIOQUIA": "SANTAFE", "LACEJADELTAMBO": "LACEJA",

    # --- 🛡️ NUEVOS BLINDAJES ANTIOQUIA ---
    "CAROLINADELPRINCIPE": "CAROLINA",
    "SANANDRESDECUERQUIA": "SANANDRES",
    "SANPEDRODELOSMILAGROS": "SANPEDRO",
    "SANPEDRODELOSMIL": "SANPEDRO",
    "ELCARMENDEVIBORAL": "CARMENDEVIBORAL",
    "ELRETIRO": "RETIRO",
    "RETIROEL": "RETIRO"
    # Nota: San Pedro de Urabá quedará como "SANPEDRODEURABA" y no chocará con el de los Milagros.
    # Itagüí quedará como "ITAGUI" porque nuestra función ya le quita la diéresis automáticamente.
}

def clasificar_area_dane(x):
    """Sella la fuga rural del 100% estandarizando las áreas."""
    val = str(x).lower().strip()
    if 'cabecera' in val or 'urban' in val: return 'Urbana'
    if 'rural' in val or 'centros' in val or 'resto' in val: return 'Rural'
    return 'Total'

# =================================================================
# 🏛️ LÓGICA DE JURISDICCIONES COMPLEJAS
# =================================================================
def procesar_jurisdiccion_car(df_base, nombre_car):
    """
    Resuelve el conflicto AMVA vs Corantioquia.
    Requiere un DataFrame que ya tenga la columna 'municipio_norm' y 'area_geografica'.
    """
    if nombre_car == 'AMVA':
        # AMVA rige únicamente sobre las cabeceras urbanas del Valle de Aburrá
        df_amva_urb = df_base[(df_base['municipio_norm'].isin(MPIOS_AMVA)) & (df_base['area_geografica'] == 'Urbana')].copy()
        df_amva_tot = df_amva_urb.copy()
        df_amva_tot['area_geografica'] = 'Total'
        return pd.concat([df_amva_urb, df_amva_tot]) if not df_amva_urb.empty else pd.DataFrame()
        
    elif nombre_car == 'CORANTIOQUIA':
        # Corantioquia rige sobre sus propios municipios, y las áreas RURALES del AMVA
        df_propios = df_base[~df_base['municipio_norm'].isin(MPIOS_AMVA)].copy()
        
        df_amva_rur = df_base[(df_base['municipio_norm'].isin(MPIOS_AMVA)) & (df_base['area_geografica'] == 'Rural')].copy()
        df_amva_rur_tot = df_amva_rur.copy()
        df_amva_rur_tot['area_geografica'] = 'Total'
        
        return pd.concat([df_propios, df_amva_rur, df_amva_rur_tot]) if not df_propios.empty else pd.DataFrame()
        
    else:
        # Cualquier otra CAR (ej. Cornare) se devuelve intacta
        return df_base