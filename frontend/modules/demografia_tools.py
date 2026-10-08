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
            elif mod == 'Lineal': return row.get('Lin_m', 0) * t_val + row.get('Lin_b', 0)
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

# 🚀 NUEVO: CEREBRO DE PROPORCIONES (CACHÉ)
@st.cache_data(show_spinner=False)
def cargar_proporciones_cuencas():
    url_prop = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/cuencas_mpios_proporcion.csv"
    try:
        df_prop = pd.read_csv(url_prop, sep=';', encoding='utf-8')
        df_prop.columns = [c.strip() for c in df_prop.columns]
        
        def limpiar_cuenca(texto):
            if pd.isna(texto): return ""
            t = str(texto).upper()
            t = re.sub(r'\(.*?\)', '', t)
            t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
            return re.sub(r'[^A-Z0-9]', '', t).strip()
            
        df_prop['cuenca_norm'] = df_prop['Subcuenca'].astype(str).apply(limpiar_cuenca)
        df_prop['mun_norm'] = df_prop['Municipio'].astype(str).apply(normalizar_texto)
        return df_prop
    except:
        return pd.DataFrame()

@st.cache_data(show_spinner="Agrupando datos poblacionales (Cerebro Híbrido)...")
def calcular_poblacion_al_vuelo(territorio, nivel, area, anio_especifico=None):
    nivel_upper = str(nivel).strip().upper()
    area_filtro = str(area).lower()
    
    def limpiar_fuerte(texto):
        if not texto: return ""
        t = str(texto).upper()
        t = re.sub(r'\(.*?\)', '', t)
        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
        return re.sub(r'[^A-Z0-9]', '', t).strip()
        
    terr_limpio = limpiar_fuerte(territorio)

    df_dane = cargar_datos_dane_crudos()
    if df_dane.empty: return None

    cols_hombres = [c for c in df_dane.columns if 'hombre' in str(c).lower() and any(char.isdigit() for char in str(c))]
    cols_mujeres = [c for c in df_dane.columns if 'mujer' in str(c).lower() and any(char.isdigit() for char in str(c))]

    # ====================================================================
    # 🌊 MOTOR PARA CUENCAS (ESTRUCTURA HÍBRIDA: SQL -> FALLBACK)
    # ====================================================================
    if nivel_upper == "CUENCA":
        # 🟢 INTENTO 1: Buscar en la Matriz Maestra (PostgreSQL)
        try:
            engine = get_engine()
            cat_llave = "TOTAL" if area_filtro == 'total' else ("URBANA" if area_filtro == 'urbana' else "RURAL")
            llave_busqueda = f"CUENCA_{terr_limpio}_{cat_llave}"
            
            q = text('SELECT * FROM matriz_maestra_demografica WHERE "LLAVE_UNIVERSAL" = :llave')
            df_matriz = pd.read_sql(q, engine, params={"llave": llave_busqueda})
            
            if not df_matriz.empty:
                row = df_matriz.iloc[0]
                anios = np.arange(1985, 2043)
                t_val = anios - int(row.get('Año_Base', 2018))
                mod = str(row.get('Modelo_Recomendado', 'Desconocido'))
                
                if 'Logístico' in mod or 'Logistico' in mod: pob_calc = row['Log_K'] / (1 + row['Log_a'] * np.exp(-row['Log_r'] * t_val))
                elif 'Exponencial' in mod: pob_calc = row['Exp_a'] * np.exp(row['Exp_b'] * t_val)
                elif 'Polinomial' in mod: pob_calc = row['Poly_A']*(t_val**3) + row['Poly_B']*(t_val**2) + row['Poly_C']*t_val + row['Poly_D']
                elif 'Lineal' in mod: pob_calc = row.get('Lin_m', 0) * t_val + row.get('Lin_b', 0)
                else: pob_calc = np.full_like(anios, row.get('Pob_Base', 0))
                    
                pob_calc = np.clip(pob_calc, 0, None)
                df_res = pd.DataFrame({'año': anios, 'Total': pob_calc})
                
                # Constructor sintético de pirámide
                col_depto = next((c for c in df_dane.columns if 'depto' in str(c).lower() or 'dpto' in str(c).lower()), df_dane.columns[1])
                df_dane_proxy = df_dane.copy()
                df_dane_proxy['año'] = pd.to_numeric(df_dane_proxy['año'], errors='coerce').fillna(2018).astype(int)
                
                df_ant = df_dane_proxy[df_dane_proxy[col_depto].astype(str).str.contains('ANTIOQUIA', case=False, na=False)].groupby('año')[cols_hombres + cols_mujeres].sum().reset_index()
                df_ant['Total_Ant'] = df_ant[cols_hombres + cols_mujeres].sum(axis=1).replace(0, 1) 
                
                df_res = pd.merge(df_res, df_ant, on='año', how='left')
                for c in cols_hombres + cols_mujeres:
                    if c in df_res.columns: df_res[c] = (df_res[c] / df_res['Total_Ant']).ffill().bfill() * df_res['Total']
                    else: df_res[c] = 0
                    
                if anio_especifico is not None: return df_res[df_res['año'] == anio_especifico]
                return {'hist_anios': df_res['año'].tolist(), 'hist_pob': df_res['Total'].tolist(), 'df_edades': df_res, 'cols_hombres': cols_hombres, 'cols_mujeres': cols_mujeres}
        except Exception:
            pass # Falla silenciosa para pasar al Plan B

        # 🟠 INTENTO 2 (EL SALVAVIDAS): Construcción Dasimétrica al Vuelo
        try:
            df_prop = cargar_proporciones_cuencas()
            if not df_prop.empty:
                # Buscamos qué municipios componen la cuenca
                fragmentos = df_prop[df_prop['cuenca_norm'] == terr_limpio]
                
                if not fragmentos.empty:
                    anios_base = sorted(df_dane['año'].dropna().unique())
                    df_res = pd.DataFrame({'año': anios_base})
                    df_res['Total'] = 0.0
                    for c in cols_hombres + cols_mujeres: df_res[c] = 0.0
                        
                    for _, frag in fragmentos.iterrows():
                        mun_frag = frag['mun_norm']
                        
                        # Extraer porcentaje matemáticamente
                        pct_str = str(frag.get('Porcentaje', '100')).replace('.', '')
                        try:
                            pct_float = float(pct_str[:-2] + '.' + pct_str[-2:]) if len(pct_str) > 2 else float(pct_str)
                            pct_real = pct_float / 100.0 if pct_float > 1 else pct_float
                        except: pct_real = 0.0
                        
                        # Rescatar la población de ese municipio del DANE
                        mask_m = (df_dane['mun_norm'] == mun_frag)
                        if area_filtro == 'urbana': mask_m &= df_dane['area_geografica'].astype(str).str.contains('cabecera|urb|1', case=False, regex=True)
                        elif area_filtro == 'rural': mask_m &= df_dane['area_geografica'].astype(str).str.contains('rural|centro|resto|2', case=False, regex=True)
                        else: mask_m &= df_dane['area_geografica'].astype(str).str.contains('total', case=False, regex=True)
                        
                        df_m = df_dane[mask_m].groupby('año')[cols_hombres + cols_mujeres].sum().reset_index()
                        
                        # Multiplicar el municipio por el porcentaje que aporta a la cuenca
                        if not df_m.empty:
                            df_m['Total_frag'] = df_m[cols_hombres + cols_mujeres].sum(axis=1) * pct_real
                            for c in cols_hombres + cols_mujeres: df_m[c] = df_m[c] * pct_real
                                
                            df_res = pd.merge(df_res, df_m, on='año', how='left', suffixes=('', '_frag'))
                            df_res['Total'] = df_res['Total'] + df_res['Total_frag'].fillna(0)
                            for c in cols_hombres + cols_mujeres: df_res[c] = df_res[c] + df_res[f"{c}_frag"].fillna(0)
                            df_res.drop(columns=[c for c in df_res.columns if '_frag' in c], inplace=True)
                    
                    if df_res['Total'].sum() > 0:
                        if anio_especifico is not None: return df_res[df_res['año'] == anio_especifico]
                        return {'hist_anios': df_res['año'].tolist(), 'hist_pob': df_res['Total'].tolist(), 'df_edades': df_res, 'cols_hombres': cols_hombres, 'cols_mujeres': cols_mujeres}
        except Exception as e:
            print(f"Error en constructor dasimétrico: {e}")
            
        # 🔴 INTENTO 3: Retorno Nulo
        return None

    # ====================================================================
    # 🏢 MOTOR PARA MUNICIPIOS, DEPTOS Y REGIONES (DATOS DANE CRUDOS)
    # ====================================================================
    cols_base = [c for c in ['año', 'dpto_norm', 'depto_nom', 'mun_norm', 'municipio', 'area_geografica'] if c in df_dane.columns]
    
    if anio_especifico is not None: df_f = df_dane[df_dane['año'] == anio_especifico][cols_base + cols_hombres + cols_mujeres].copy()
    else: df_f = df_dane[cols_base + cols_hombres + cols_mujeres].copy()
    
    if df_f.empty: return None

    if 'area_geografica' in df_f.columns and area_filtro != 'total':
        if area_filtro == 'urbana': mask_area = df_f['area_geografica'].astype(str).str.contains('cabecera|urb|1', case=False, regex=True)
        else: mask_area = df_f['area_geografica'].astype(str).str.contains('rural|centro|resto|2', case=False, regex=True)
        df_f = df_f[mask_area]
    elif 'area_geografica' in df_f.columns and area_filtro == 'total':
         df_f = df_f[df_f['area_geografica'].astype(str).str.contains('total', case=False, regex=True)]

    col_mun = next((c for c in ['mun_norm', 'municipio'] if c in df_f.columns), None)
    if col_mun: df_f['match_id'] = df_f[col_mun].apply(limpiar_fuerte)

    if nivel_upper == "NACIONAL": df_agrupado = df_f
    elif nivel_upper == "DEPARTAMENTAL":
        col_dpto = next((c for c in ['dpto_norm', 'depto_nom'] if c in df_f.columns), None)
        if col_dpto:
            df_f['match_dpto'] = df_f[col_dpto].apply(limpiar_fuerte)
            df_agrupado = df_f[df_f['match_dpto'] == terr_limpio]
        else: return None
    elif nivel_upper == "MUNICIPAL":
        if "CARMENDEVIBORAL" in terr_limpio: terr_limpio = "CARMENDEVIBORAL"
        if "SANVICENTE" in terr_limpio: terr_limpio = "SANVICENTE"
        if "SANANDRES" in terr_limpio and "CUERQUIA" in terr_limpio: terr_limpio = "SANANDRES"
        if "SANTAFE" in terr_limpio: terr_limpio = "SANTAFE"
        if "SANJOSE" in terr_limpio and "MONTANA" in terr_limpio: terr_limpio = "SANJOSE"
        if "CAROLINADELPRINCIPE" in terr_limpio: terr_limpio = "CAROLINA"
        if "PUEBLORICO" in terr_limpio: terr_limpio = "PUEBLORRICO"
        if "ELPENOL" in terr_limpio: terr_limpio = "PENOL"
        df_agrupado = df_f[df_f['match_id'] == terr_limpio]
    elif nivel_upper in ["REGIONAL", "CAR"]:
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
        if nivel_upper == "REGIONAL": mpios_validos = M_SUB.get(terr_limpio, [])
        else:
            if terr_limpio == "CORANTIOQUIA":
                excluir = set(M_CAR["AMVA"] + M_CAR["CORPOURABA"] + M_CAR["CORNARE"])
                todos = [m for sublist in M_SUB.values() for m in sublist]
                mpios_validos = list(set(todos) - excluir)
            else: mpios_validos = M_CAR.get(terr_limpio, [])
            
        df_agrupado = df_f[df_f['match_id'].isin(mpios_validos)]
        
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