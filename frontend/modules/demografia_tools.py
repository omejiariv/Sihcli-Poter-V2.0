# modules/demografia_tools.py

import streamlit as st
import pandas as pd
import numpy as np
import difflib
import re
import unicodedata
from sqlalchemy import text
from modules.db_manager import get_engine
from modules.utils import normalizar_texto_maestro, normalizar_texto

# ====================================================================
# 1. MOTOR SQL (PROYECCIONES MATEMÁTICAS A LARGO PLAZO)
# ====================================================================
def obtener_poblacion_matriz(nombre_zona, anio_objetivo, area_deseada="Total"):
    """Buscador de precisión quirúrgica basado en Llave Universal para proyecciones post-2042."""
    engine = get_engine()
    try:
        terr_norm = normalizar_texto(nombre_zona).upper()
        area_norm = area_deseada.upper()
        
        q = text("""
            SELECT * FROM matriz_maestra_demografica 
            WHERE "LLAVE_UNIVERSAL" LIKE :pattern 
            AND "Area" = :area
        """)
        
        df_res = pd.read_sql(q, engine, params={
            "pattern": f"%_{terr_norm}_%",
            "area": area_deseada
        })
        
        if not df_res.empty:
            nivel_activo = st.session_state.get('nivel_activo_global', 'Municipal')
            fila = df_res[df_res['Nivel'] == nivel_activo]
            if fila.empty: fila = df_res.head(1)
            
            row = fila.iloc[0]
            t_val = anio_objetivo - row['Año_Base']
            mod = row['Modelo_Recomendado']
            
            if mod == 'Logístico': return row['Log_K'] / (1 + row['Log_a'] * np.exp(-row['Log_r'] * t_val))
            elif mod == 'Exponencial': return row['Exp_a'] * np.exp(row['Exp_b'] * t_val)
            elif mod == 'Lineal': return row['Lin_m'] * t_val + row['Lin_b']
            else: return row['Poly_A']*(t_val**3) + row['Poly_B']*(t_val**2) + row['Poly_C']*t_val + row['Poly_D']
            
    except Exception: pass
    return 0

def render_motor_demografico(lugar_defecto="Antioquia"):
    """Mini-panel para inyectar población en el Aleph manualmente."""
    st.info(f"🧠 Conectado al Cerebro Demográfico: **{lugar_defecto}**")
    
    col_btn1, col_btn2 = st.columns([1, 2])
    with col_btn1:
        anio_proyeccion = st.slider("📅 Año:", 2024, 2050, st.session_state.get('aleph_anio', 2024), key=f"ds_{lugar_defecto}")
        
    with col_btn2:
        st.write("") 
        if st.button("👥 Sincronizar Población Real", use_container_width=True, key=f"db_{lugar_defecto}"):
            with st.spinner("Consultando Matriz SQL..."):
                pob_calculada = obtener_poblacion_matriz(lugar_defecto, anio_proyeccion)
                
                if pob_calculada > 0:
                    st.session_state['aleph_pob_total'] = pob_calculada
                    st.session_state['aleph_anio'] = anio_proyeccion
                    st.session_state['aleph_lugar'] = lugar_defecto
                    st.success(f"✅ Sincronizado: {int(pob_calculada):,} hab.")
                    st.rerun()
                else:
                    st.warning("⚠️ No se encontró el territorio en la Matriz.")

# ====================================================================
# 2. MOTOR PARQUET (DASIMETRÍA ESPACIAL Y DATOS EXACTOS HISTÓRICOS)
# ====================================================================
@st.cache_data(show_spinner="Cargando Parquet DANE en Memoria...")
def cargar_datos_dane_crudos():
    url_parquet = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/Poblacion_Colombia_1985_2042_Optimizado.parquet" 
    try:
        df = pd.read_parquet(url_parquet)
        
        columnas_base = {'DPNOM': 'depto_nom', 'DPMP': 'municipio', 'AÑO': 'año', 'AREA_GEOGRAFICA': 'area_geografica'}
        for col_orig in df.columns:
            col_upper = str(col_orig).strip().upper()
            if col_upper in columnas_base:
                df = df.rename(columns={col_orig: columnas_base[col_upper]})
                
        df.columns = df.columns.str.lower()
        
        if 'depto_nom' in df.columns: df['dpto_norm'] = df['depto_nom'].apply(normalizar_texto)
        if 'municipio' in df.columns: df['mun_norm'] = df['municipio'].apply(normalizar_texto)
            
        if 'area_geografica' in df.columns:
            def clasificar_dane(x):
                x = str(x).lower()
                if 'cabecera' in x or 'urban' in x: return 'urbana'
                if 'rural' in x or 'centros' in x or 'resto' in x: return 'rural'
                return 'total'
            df['area_geografica'] = df['area_geografica'].apply(clasificar_dane)
            
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(show_spinner="Agrupando datos poblacionales (Cerebro Híbrido)...")
def calcular_poblacion_al_vuelo(territorio, nivel, area, anio_especifico=None):
    df_dane = cargar_datos_dane_crudos()
    if df_dane.empty: return None

    area_filtro = area.lower()
    cols_hombres = [c for c in df_dane.columns if 'hombre' in c and any(char.isdigit() for char in c)]
    cols_mujeres = [c for c in df_dane.columns if 'mujer' in c and any(char.isdigit() for char in c)]
    cols_base = [c for c in ['año', 'dpto_norm', 'mun_norm', 'area_geografica'] if c in df_dane.columns]
    
    if anio_especifico is not None: df_f = df_dane[df_dane['año'] == anio_especifico][cols_base + cols_hombres + cols_mujeres].copy()
    else: df_f = df_dane[cols_base + cols_hombres + cols_mujeres].copy()
    
    if df_f.empty: return None

    if 'area_geografica' in df_f.columns and area_filtro != 'total':
        if area_filtro == 'urbana': mask_area = df_f['area_geografica'].astype(str).str.contains('cabecera|urb|1', case=False, regex=True)
        else: mask_area = df_f['area_geografica'].astype(str).str.contains('rural|centro|resto|2', case=False, regex=True)
        df_f = df_f[mask_area]
    elif 'area_geografica' in df_f.columns and area_filtro == 'total':
         df_f = df_f[df_f['area_geografica'] == 'total']

    def limpiar_fuerte(texto):
        if not texto: return ""
        t = str(texto).upper()
        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
        return re.sub(r'[^A-Z0-9]', '', t)
        
    terr_limpio = limpiar_fuerte(territorio)
    df_f['match_id'] = df_f['mun_norm'].apply(limpiar_fuerte)

    if nivel == "NACIONAL": df_agrupado = df_f
    elif nivel == "DEPARTAMENTAL":
        df_f['match_dpto'] = df_f['dpto_norm'].apply(limpiar_fuerte)
        df_agrupado = df_f[df_f['match_dpto'] == terr_limpio]
    elif nivel == "MUNICIPAL":
        if "CARMENDEVIBORAL" in terr_limpio: terr_limpio = "CARMENDEVIBORAL"
        if "SANVICENTE" in terr_limpio: terr_limpio = "SANVICENTE"
        if "SANANDRES" in terr_limpio and "CUERQUIA" in terr_limpio: terr_limpio = "SANANDRES"
        if "SANTAFE" in terr_limpio: terr_limpio = "SANTAFE"
        if "SANJOSE" in terr_limpio and "MONTANA" in terr_limpio: terr_limpio = "SANJOSE"
        if "CAROLINADELPRINCIPE" in terr_limpio: terr_limpio = "CAROLINA"
        if "PUEBLORICO" in terr_limpio: terr_limpio = "PUEBLORRICO"
        if "ELPENOL" in terr_limpio: terr_limpio = "PENOL"
        df_agrupado = df_f[df_f['match_id'] == terr_limpio]
    elif nivel in ["REGIONAL", "CAR"]:
        M_SUB = {
            "VALLEDEABURRA": ["MEDELLIN", "BELLO", "ITAGUI", "ENVIGADO", "SABANETA", "COPACABANA", "LAESTRELLA", "GIRARDOTA", "CALDAS", "BARBOSA"],
            "BAJOCAUCA": ["CAUCASIA", "CACERES", "ELBAGRE", "NECHI", "TARAZA", "ZARAGOZA"],
            "MAGDALENAMEDIO": ["CARACOLI", "MACEO", "PUERTOBERRIO", "PUERTONARE", "PUERTOTRIUNFO", "YONDO"],
            "NORDESTE": ["AMALFI", "ANORI", "CISNEROS", "REMEDIOS", "SANROQUE", "SANTODOMINGO", "SEGOVIA", "VEGACHI", "YALI", "YOLOMBO"],
            "NORTE": ["ANGOSTURA", "BELMIRA", "BRICENO", "CAMPAMENTO", "CAROLINA", "DONMATIAS", "ENTRERRIOS", "GOMEZPLATA", "GUADALUPE", "ITUANGO", "SANANDRESDECUERQUIA", "SANJOSEDELAMONTANA", "SANPEDRODELOSMILAGROS", "SANTAROSADEOSOS", "TOLEDO", "VALDIVIA", "YARUMAL"],
            "OCCIDENTE": ["ABRIAQUI", "ANZA", "ARMENIA", "BURITICA", "CANASGORDAS", "DABEIBA", "EBEJICO", "FRONTINO", "GIRALDO", "HELICONIA", "LIBORINA", "OLAYA", "PEQUE", "SABANALARGA", "SANJERONIMO", "SANTAFEDEANTIOQUIA", "SOPETRAN", "URAMITA"],
            "ORIENTE": ["ABEJORRAL", "ALEJANDRIA", "ARGELIA", "ELCARMENDEVIBORAL", "COCORNA", "CONCEPCION", "PENOL", "ELRETIRO", "ELSANTUARIO", "GUARNE", "GUATAPE", "LACEJA", "LAUNION", "MARINILLA", "NARINO", "RIONEGRO", "SANCARLOS", "SANFRANCISCO", "SANLUIS", "SANRAFAEL", "SANVICENTEFERRER", "SONSON", "GRANADA"],
            "SUROESTE": ["AMAGA", "ANDES", "ANGELOPOLIS", "BETANIA", "BETULIA", "CARAMANTA", "CIUDADBOLIVAR", "CONCORDIA", "FREDONIA", "HISPANIA", "JARDIN", "JERICO", "LAPINTADA", "MONTEBELLO", "PUEBLORRICO", "SALGAR", "SANTABARBARA", "TAMESIS", "TARSO", "TITIRIBI", "URRAO", "VALPARAISO", "VENECIA"],
            "URABA": ["APARTADO", "ARBOLETES", "CAREPA", "CHIGORODO", "MURINDO", "MUTATA", "NECOCLI", "SANJUANDEURABA", "SANPEDRODEURABA", "TURBO", "VIGIADELFUERTE"]
        }
        M_CAR = {
            "AMVA": M_SUB["VALLEDEABURRA"],
            "CORPOURABA": M_SUB["URABA"] + ["DABEIBA", "MURINDO", "VIGIADELFUERTE", "URRAO", "FRONTINO", "ABRIAQUI", "GIRALDO", "CANASGORDAS", "URAMITA", "PEQUE"],
            "CORNARE": M_SUB["ORIENTE"] + ["PUERTONARE", "PUERTOTRIUNFO"]
        }
        if nivel == "REGIONAL": mpios_validos = M_SUB.get(terr_limpio, [])
        else:
            if terr_limpio == "CORANTIOQUIA":
                excluir = set(M_CAR["AMVA"] + M_CAR["CORPOURABA"] + M_CAR["CORNARE"])
                todos = [m for sublist in M_SUB.values() for m in sublist]
                mpios_validos = list(set(todos) - excluir)
            else: mpios_validos = M_CAR.get(terr_limpio, [])
            
        df_agrupado = df_f[df_f['match_id'].isin(mpios_validos)]

    elif nivel == "CUENCA":
        import os
        ruta_pesos = "backend/app/data/matriz_pesos_veredales.parquet"
        ruta_inter = "backend/app/data/matriz_cuencas_veredas.parquet"
        if not os.path.exists(ruta_pesos) or not os.path.exists(ruta_inter): return None
            
        df_pesos = pd.read_parquet(ruta_pesos)
        df_inter = pd.read_parquet(ruta_inter)

        if 'territorio_norm' in df_pesos.columns and 'vereda_norm' not in df_pesos.columns:
            df_pesos.rename(columns={'territorio_norm': 'vereda_norm'}, inplace=True)
        if 'territorio_norm' in df_inter.columns and 'vereda_norm' not in df_inter.columns:
            df_inter.rename(columns={'territorio_norm': 'vereda_norm'}, inplace=True)

        terr_aplanado = limpiar_fuerte(territorio)
        mask_cuenca = (
            (df_inter['NOMAH'].astype(str).apply(limpiar_fuerte) == terr_aplanado) | 
            (df_inter['NOMZH'].astype(str).apply(limpiar_fuerte) == terr_aplanado) | 
            (df_inter['NOM_SZH'].astype(str).apply(limpiar_fuerte) == terr_aplanado) | 
            (df_inter['NOM_NSS1'].astype(str).apply(limpiar_fuerte) == terr_aplanado) | 
            (df_inter['NOM_NSS2'].astype(str).apply(limpiar_fuerte) == terr_aplanado) | 
            (df_inter['NOM_NSS3'].astype(str).apply(limpiar_fuerte) == terr_aplanado) |
            (df_inter['AH'].astype(str).apply(limpiar_fuerte) == terr_aplanado) |
            (df_inter['ZH'].astype(str).apply(limpiar_fuerte) == terr_aplanado) |
            (df_inter['SZH'].astype(str).apply(limpiar_fuerte) == terr_aplanado) |
            (df_inter['NSS1'].astype(str).apply(limpiar_fuerte) == terr_aplanado) |
            (df_inter['NSS2'].astype(str).apply(limpiar_fuerte) == terr_aplanado) |
            (df_inter['NSS3'].astype(str).apply(limpiar_fuerte) == terr_aplanado)
        )
        
        df_cuenca_veredas = df_inter[mask_cuenca]
        if df_cuenca_veredas.empty: return None
            
        df_cruce = df_cuenca_veredas.merge(df_pesos, on=['mpio_norm', 'vereda_norm'], how='inner')
        df_cruce['factor_urb'] = df_cruce['Pct_Vereda_en_Cuenca'] * df_cruce['peso_urbano']
        df_cruce['factor_rur'] = df_cruce['Pct_Vereda_en_Cuenca'] * df_cruce['peso_rural']
        df_factor_mpio = df_cruce.groupby('mpio_norm')[['factor_urb', 'factor_rur']].sum().reset_index()
        
        mask_urb = df_f['area_geografica'].astype(str).str.contains('cabecera|urb|1', case=False, regex=True)
        mask_rur = df_f['area_geografica'].astype(str).str.contains('rural|centro|resto|2', case=False, regex=True)
        
        df_dane_urb = df_f[mask_urb].copy()
        df_dane_rur = df_f[mask_rur].copy()
        
        data_frames_calculados = []
        for _, row in df_factor_mpio.iterrows():
            mpio = row['mpio_norm']
            f_urb, f_rur = float(row['factor_urb']), float(row['factor_rur'])
            
            if f_urb > 0:
                df_urb = df_dane_urb[df_dane_urb['match_id'] == mpio].copy()
                if not df_urb.empty:
                    for col in cols_hombres + cols_mujeres: df_urb[col] = df_urb[col] * f_urb
                    data_frames_calculados.append(df_urb)
                    
            if f_rur > 0:
                df_rur = df_dane_rur[df_dane_rur['match_id'] == mpio].copy()
                if not df_rur.empty:
                    for col in cols_hombres + cols_mujeres: df_rur[col] = df_rur[col] * f_rur
                    data_frames_calculados.append(df_rur)
                    
        if data_frames_calculados: df_agrupado = pd.concat(data_frames_calculados)
        else: return None
        
    if 'df_agrupado' not in locals() or df_agrupado.empty: return None

    df_res = df_agrupado.groupby('año')[cols_hombres + cols_mujeres].sum().reset_index()
    df_res['Total'] = df_res[cols_hombres + cols_mujeres].sum(axis=1)
    
    if anio_especifico is not None: return df_res
         
    return {
        'hist_anios': df_res['año'].tolist(),
        'hist_pob': df_res['Total'].tolist(),
        'df_edades': df_res,
        'cols_hombres': cols_hombres,
        'cols_mujeres': cols_mujeres
    }