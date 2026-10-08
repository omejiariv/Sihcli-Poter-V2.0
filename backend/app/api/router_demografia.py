# backend/app/api/router_demografia.py
import numpy as np
import pandas as pd
import geopandas as gpd
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from functools import lru_cache
from backend.app.database import get_engine

import re
import unicodedata

# --- FUNCION MÁGICA 1: EL ASPIRADOR DE TEXTOS (Match infalible) ---
def normalizar_texto(texto):
    import pandas as pd
    import re
    import unicodedata
    
    if pd.isna(texto) or not texto: return ""
    t = str(texto).strip().upper()
    t = re.sub(r'\(.*?\)', '', t)
    
    # Quitar prefijos molestos
    t = t.replace("VDA.", "").replace("VDA ", "").replace("VEREDA ", "").replace("SECTOR ", "")
    
    # 🚀 FIX CRÍTICO: Reemplazar la Ñ antes de quitar acentos
    t = t.replace("Ñ", "N")
    
    # Quitar tildes
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    
    # 🚀 FIX DE ESPACIOS: Conservar letras, números Y ESPACIOS.
    t = re.sub(r'[^A-Z0-9 ]', '', t).strip()
    
    # Diccionario de rescate para el DANE
    diccionario_rebeldes = {
        "BRICEN0": "BRICENO", "BOGOTADC": "BOGOTA", "VALLE": "VALLE DEL CAUCA",
        "SANVICENTEDECHUCURI": "SAN VICENTE", "SAN VICENTE FERRER": "SAN VICENTE",
        "EL CARMEN DE VIBORAL": "CARMEN DE VIBORAL", "SAN PEDRO DE LOS MILAGROS": "SAN PEDRO",
        "SANTAFE DE ANTIOQUIA": "SANTAFE", "SANTA FE DE ANTIOQUIA": "SANTAFE",
        "AREA METROPOLITANA": "VALLE DE ABURRA"
    }
    
    # Si la versión pegada (sin espacios) está en el diccionario, la traducimos
    t_sin_espacios = t.replace(" ", "")
    if t_sin_espacios in diccionario_rebeldes: 
        return diccionario_rebeldes[t_sin_espacios]
        
    return t

# 🌟 INYECCIÓN DEL MOTOR DE JERARQUÍAS

router = APIRouter(prefix="/api/demografia", tags=["Motor Demográfico"])

class ConsultaDemografica(BaseModel):
    territorio: str
    nivel: str
    anio_destino: int

# =================================================================
# 🧠 MEMORIA PROFUNDA: Cachés del Backend con Escudo Lingüístico
# =================================================================
@lru_cache(maxsize=1)
def obtener_datos_dane_parquet():
    print("\n📥 [MEMORIA] Iniciando descarga del Parquet de Edades desde Supabase...")
    url_parquet = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/sihcli_maestros/Poblacion_Colombia_1985_2042_Optimizado.parquet"
    try:
        df = pd.read_parquet(url_parquet)
        renames = {'DPNOM': 'depto_nom', 'DPMP': 'municipio', 'AÑO': 'anio', 'AREA_GEOGRAFICA': 'area'}
        df = df.rename(columns=lambda x: renames.get(str(x).strip().upper(), str(x).strip()))
        
        if 'anio' in df.columns:
            df['anio'] = pd.to_numeric(df['anio'], errors='coerce').fillna(1985).astype(int)
            
        # 🌟 INYECCIÓN: Normalizamos la base DANE una sola vez en memoria
        df['mun_norm'] = df['municipio'].astype(str).apply(normalizar_texto)
        df['dpto_norm'] = df['depto_nom'].astype(str).apply(normalizar_texto)
        
        # 🚀 FIX APLICADO: Limpieza nativa de Pandas (Adiós a la función fantasma)
        df['area_norm'] = df['area'].astype(str).str.strip().str.title()
        
        print(f"✅ [MEMORIA] ¡Parquet cargado y normalizado! Filas: {len(df)}")
        return df
    except Exception as e:
        print(f"🚨 [ERROR] Falló Parquet: {e}")
        return pd.DataFrame()

@lru_cache(maxsize=1)
def obtener_geojson_maestro():
    print("\n🗺️ [MEMORIA ESPACIAL] Descargando Territorio Maestro (GeoJSON 131MB)...")
    url_geojson = "https://ldunpssoxvifemoyeuac.supabase.co/storage/v1/object/public/geojson/TerritorioMaestro.geojson"
    try:
        gdf = gpd.read_file(url_geojson)
        
        # 🌟 INYECCIÓN: Normalizamos la topología una sola vez en memoria
        gdf['mpio_norm'] = gdf['mpio_cnmbr'].astype(str).apply(normalizar_texto)
        gdf['dpto_norm'] = gdf['dpto_cnmbr'].astype(str).apply(normalizar_texto)
        
        print(f"✅ [MEMORIA ESPACIAL] GeoJSON Maestro cargado y normalizado. Polígonos: {len(gdf)}")
        return gdf
    except Exception as e:
        print(f"🚨 [ERROR ESPACIAL] Falló carga de GeoJSON: {e}")
        return None

# =================================================================
# 🚀 RUTAS DEL API
# =================================================================
@router.post("/proyectar")
def calcular_proyeccion(consulta: ConsultaDemografica):
    engine = get_engine()
    
    # 🌟 INYECCIÓN: Limpiamos lo que el usuario escribió en el frontend
    terr_limpio = normalizar_texto(consulta.territorio)

    query = text("""
        SELECT * FROM matriz_maestra_demografica
        WHERE UPPER(TRIM("Territorio")) = :terr
        AND UPPER(TRIM("Nivel")) = :nivel
    """)

    with engine.connect() as conn:
        # Buscamos en la BD usando el nombre purificado
        df = pd.read_sql(query, conn, params={"terr": terr_limpio, "nivel": consulta.nivel.upper()})

    if df.empty:
        raise HTTPException(status_code=404, detail=f"Territorio '{terr_limpio}' no encontrado en la Matriz Maestra.")

    resultados = {}
    anios_array = list(range(1985, consulta.anio_destino + 1))
    serie_historica = {"anios": anios_array}
    
    for _, fila in df.iterrows():
        area = fila.get('Area', 'Desconocida').title()
        anio_base = fila.get('Año_Base', 2018)
        modelo = str(fila.get('Modelo_Recomendado', 'Logístico'))

        valores_serie = []
        for anio in anios_array:
            x_norm = anio - anio_base
            try:
                if 'Logistico' in modelo or 'Logístico' in modelo:
                    val = fila['Log_K'] / (1 + fila['Log_a'] * np.exp(-fila['Log_r'] * x_norm))
                elif 'Exponencial' in modelo:
                    val = fila['Exp_a'] * np.exp(fila['Exp_b'] * x_norm)
                elif 'Lineal' in modelo:
                    val = fila['Lin_m'] * x_norm + fila['Lin_b']
                else:
                    val = fila['Poly_A']*(x_norm**3) + fila['Poly_B']*(x_norm**2) + fila['Poly_C']*x_norm + fila['Poly_D']
            except Exception:
                val = 0.0
            valores_serie.append(max(0, int(round(val, 0))))

        serie_historica[area] = valores_serie
        resultados[area] = valores_serie[-1]

    return {"territorio": consulta.territorio, "anio_proyeccion": consulta.anio_destino, "resultados": resultados, "serie_historica": serie_historica}


@router.post("/piramide")
def calcular_piramide(consulta: ConsultaDemografica):
    df = obtener_datos_dane_parquet()
    if df.empty: raise HTTPException(status_code=500, detail="Error cargando Parquet.")

    # 🌟 INYECCIÓN: Usamos el escudo lingüístico
    terr_limpio = normalizar_texto(consulta.territorio)
    
    if consulta.nivel == "NACIONAL":
        df_filtro = df[df['area_norm'] == 'Total']
    elif consulta.nivel == "DEPARTAMENTAL":
        df_filtro = df[(df['dpto_norm'] == terr_limpio) & (df['area_norm'] == 'Total')]
    elif consulta.nivel == "MUNICIPAL":
        df_filtro = df[(df['mun_norm'] == terr_limpio) & (df['area_norm'] == 'Total')]
    else:
        df_filtro = pd.DataFrame()
        
    if df_filtro.empty: raise HTTPException(status_code=404, detail=f"Sin datos DANE para {terr_limpio}.")

    anio_max = df_filtro['anio'].max()
    anio_buscar = min(consulta.anio_destino, int(anio_max))
    df_anio = df_filtro[df_filtro['anio'] == anio_buscar]
    
    cols_hombres = [c for c in df_anio.columns if 'Hombre' in str(c) and any(char.isdigit() for char in str(c))]
    cols_mujeres = [c for c in df_anio.columns if 'Mujer' in str(c) and any(char.isdigit() for char in str(c))]
    
    datos_hombres = df_anio[cols_hombres].sum().to_dict()
    datos_mujeres = df_anio[cols_mujeres].sum().to_dict()
    edades = [c.split('_', 1)[1].replace('_', '-') for c in cols_hombres]

    return {
        "anio_base_dane": int(anio_buscar),
        "edades": edades,
        "hombres": list(datos_hombres.values()),
        "mujeres": list(datos_mujeres.values())
    }

# =================================================================
# 🗺️ RUTA: Geovisor Inteligente Multiescala (Optimizado RAM & Topología)
# =================================================================
@router.post("/mapa")
def obtener_mapa_territorio(consulta: ConsultaDemografica):
    import re
    import unicodedata
    import json
    
    def limpiar_fuerte(texto):
        if not texto: return ""
        t = str(texto).upper()
        # 🚀 FIX QUIRÚRGICO: Borramos cualquier código entre paréntesis que envíe el Aleph
        t = re.sub(r'\(.*?\)', '', t)
        t = t.replace("Ñ", "N")
        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
        # Borramos guiones, puntos y espacios para hacer un match perfecto
        return re.sub(r'[^A-Z0-9]', '', t) 

    terr_crudo = str(consulta.territorio).upper()
    terr_limpio = limpiar_fuerte(terr_crudo)
    nivel = str(consulta.nivel).upper().strip()

    if nivel == "NACIONAL":
        raise HTTPException(status_code=404, detail="El mapa Nacional es demasiado pesado. Usa visualización local.")

    # -------------------------------------------------------------
    # RUTA A: Escalas Administrativas
    # -------------------------------------------------------------
    if nivel in ["MUNICIPAL", "DEPARTAMENTAL", "REGIONAL", "CAR"]:
        gdf_mpios = obtener_geojson_maestro()
        if gdf_mpios is None: raise HTTPException(status_code=500, detail="GeoJSON no cargado.")
        
        col_nom = 'MPIO_CNMBR' if 'MPIO_CNMBR' in gdf_mpios.columns else 'mpio_norm'
        gdf_mpios['match_id'] = gdf_mpios[col_nom].apply(limpiar_fuerte)
        
        if nivel == "MUNICIPAL":
            if "CARMENDEVIBORAL" in terr_limpio: terr_limpio = "ELCARMENDEVIBORAL"
            if "SANVICENTE" in terr_limpio: terr_limpio = "SANVICENTEFERRER"
            if "SANANDRES" in terr_limpio and "CUERQUIA" in terr_limpio: terr_limpio = "SANANDRESDECUERQUIA"
            if "SANTAFE" in terr_limpio: terr_limpio = "SANTAFEDEANTIOQUIA"
            if "SANJOSE" in terr_limpio and "MONTANA" in terr_limpio: terr_limpio = "SANJOSEDELAMONTANA"
            
            if "CAROLINADELPRINCIPE" in terr_limpio: terr_limpio = "CAROLINA"
            if "PUEBLORICO" in terr_limpio: terr_limpio = "PUEBLORRICO"
            if "ELPENOL" in terr_limpio: terr_limpio = "PENOL"

            gdf_filtro = gdf_mpios[gdf_mpios['match_id'] == terr_limpio]
            
            if gdf_filtro.empty:
                gdf_filtro = gdf_mpios[gdf_mpios['MPIO_CNMBR'].str.upper().str.contains(terr_crudo[:5], na=False)]
                        
        elif nivel == "DEPARTAMENTAL":
            col_dpto = 'DPTO_CNMBR' if 'DPTO_CNMBR' in gdf_mpios.columns else 'dpto_norm'
            gdf_mpios['match_dpto'] = gdf_mpios[col_dpto].apply(limpiar_fuerte)
            gdf_filtro = gdf_mpios[gdf_mpios['match_dpto'] == terr_limpio]
            
        elif nivel in ["REGIONAL", "CAR"]:
            M_SUB = {
                "VALLEDEABURRA": ["MEDELLIN", "BELLO", "ITAGUI", "ENVIGADO", "SABANETA", "COPACABANA", "LAESTRELLA", "GIRARDOTA", "CALDAS", "BARBOSA"],
                "BAJOCAUCA": ["CAUCASIA", "CACERES", "ELBAGRE", "NECHI", "TARAZA", "ZARAGOZA"],
                "MAGDALENAMEDIO": ["CARACOLI", "MACEO", "PUERTOBERRIO", "PUERTONARE", "PUERTOTRIUNFO", "YONDO"],
                "NORDESTE": ["AMALFI", "ANORI", "CISNEROS", "REMEDIOS", "SANROQUE", "SANTODOMINGO", "SEGOVIA", "VEGACHI", "YALI", "YOLOMBO"],
                "NORTE": ["ANGOSTURA", "BELMIRA", "BRICENO", "CAMPAMENTO", "CAROLINA", "CAROLINADELPRINCIPE", "DONMATIAS", "ENTRERRIOS", "GOMEZPLATA", "GUADALUPE", "ITUANGO", "SANANDRESDECUERQUIA", "SANANDRES", "SANJOSEDELAMONTANA", "SANJOSE", "SANPEDRODELOSMILAGROS", "SANPEDRO", "SANTAROSADEOSOS", "TOLEDO", "VALDIVIA", "YARUMAL"],
                "OCCIDENTE": ["ABRIAQUI", "ANZA", "ARMENIA", "BURITICA", "CANASGORDAS", "DABEIBA", "EBEJICO", "FRONTINO", "GIRALDO", "HELICONIA", "LIBORINA", "OLAYA", "PEQUE", "SABANALARGA", "SANJERONIMO", "SANTAFEDEANTIOQUIA", "SANTAFE", "SOPETRAN", "URAMITA"],
                "ORIENTE": ["ABEJORRAL", "ALEJANDRIA", "ARGELIA", "ELCARMENDEVIBORAL", "CARMENDEVIBORAL", "COCORNA", "CONCEPCION", "ELPENOL", "PENOL", "ELRETIRO", "RETIRO", "ELSANTUARIO", "SANTUARIO", "GUARNE", "GUATAPE", "LACEJA", "LAUNION", "MARINILLA", "NARINO", "RIONEGRO", "SANCARLOS", "SANFRANCISCO", "SANLUIS", "SANRAFAEL", "SANVICENTEFERRER", "SANVICENTE", "SONSON", "GRANADA"],
                "SUROESTE": ["AMAGA", "ANDES", "ANGELOPOLIS", "BETANIA", "BETULIA", "CARAMANTA", "CIUDADBOLIVAR", "CONCORDIA", "FREDONIA", "HISPANIA", "JARDIN", "JERICO", "LAPINTADA", "MONTEBELLO", "PUEBLORICO", "PUEBLORRICO", "SALGAR", "SANTABARBARA", "TAMESIS", "TARSO", "TITIRIBI", "URRAO", "VALPARAISO", "VENECIA"],
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
                
            gdf_filtro = gdf_mpios[gdf_mpios['match_id'].isin(mpios_validos)]
        
        if gdf_filtro.empty: raise HTTPException(status_code=404, detail=f"No se encontraron polígonos.")

        try:
            gdf_filtro['Area_Calc'] = gdf_filtro.geometry.area
            gdf_filtro['geometry'] = gdf_filtro['geometry'].simplify(0.005, preserve_topology=True)
            geojson_dict = json.loads(gdf_filtro.to_json())
            
            for feature in geojson_dict.get('features', []):
                props = feature.get('properties', {})
                
                dpto = str(props.get('dpto_cnmbr') or props.get('DPTO_CNMBR') or 'Antioquia')
                mpio = str(props.get('mpio_cnmbr') or props.get('MPIO_CNMBR') or props.get('MPIO_CNAM') or 'Sin Municipio')
                clase_suelo = str(props.get('clase_suel') or props.get('CLASE_SUEL') or '').strip().title()
                tipo_pol = str(props.get('tipo') or props.get('TIPO') or '').strip().title()
                nombre_bar_ver = str(props.get('bar_ccnmbr') or props.get('BAR_CCNMBR') or '').strip().title()
                comuna = str(props.get('comu_nmbre') or props.get('COMU_NMBRE') or '').strip().title()
                region = str(props.get('region') or props.get('REGION') or 'N/A').title()
                subregion = str(props.get('subreg_nm') or props.get('subregion') or props.get('SUBREGION') or 'N/A').title()
                car = str(props.get('car') or props.get('CAR') or 'N/A').upper()
                territorial = str(props.get('territoria') or props.get('TERRITORIA') or 'N/A').title()

                if not nombre_bar_ver or nombre_bar_ver.lower() in ['null', 'nan', 'none']:
                    nombre_final = f"Sector de {mpio.title()}"
                else:
                    if clase_suelo == 'Cabecera' or tipo_pol == 'Barrio':
                        if comuna and comuna.lower() not in ['null', 'nan', 'none', '']:
                            nombre_final = f"Barrio {nombre_bar_ver} ({comuna})"
                        else:
                            nombre_final = f"Barrio / Sector {nombre_bar_ver}"
                    else:
                        nombre_final = f"Vereda {nombre_bar_ver}"
                
                area_real = float(props.get('Area_Calc', 1.0))
                
                feature['properties'] = {
                    'Región': region, 'Subregión': subregion, 'Autoridad Ambiental (CAR)': car, 'Dir. Territorial': territorial,
                    'Tipo de Asentamiento': tipo_pol if tipo_pol and tipo_pol.lower() not in ['null', 'nan'] else 'No Aplica',
                    'Comuna': comuna if comuna and comuna.lower() not in ['null', 'nan', 'none', ''] else 'No Aplica',
                    'Departamento': dpto.title(), 'Municipio': mpio.title(), 'Sector / Vereda': nombre_final,
                    'Habitantes': 0, 'Area_Calc': area_real 
                }
        except Exception: raise HTTPException(status_code=500, detail="Error procesando polígono.")

        return {
            "centro": {"lat": float(gdf_filtro.geometry.centroid.y.mean()), "lon": float(gdf_filtro.geometry.centroid.x.mean())},
            "geojson": geojson_dict
        }

    # -------------------------------------------------------------
    # RUTA B: Cuencas (PostGIS) - BÚSQUEDA TOPOLÓGICA FLEXIBLE
    # -------------------------------------------------------------
    elif nivel == "CUENCA":
        from backend.app.database import get_engine
        import geopandas as gpd
        engine = get_engine()
        
        try:
            # 🚀 CIRUGÍA: Extracción de palabras clave robusta
            # Si el usuario busca "Alto Río Negro - (1234)", sacamos ["ALTO", "RIO", "NEGRO"]
            import unicodedata
            import re
            
            # Limpiamos el texto original (quitando códigos entre paréntesis)
            texto_base = str(consulta.territorio).upper()
            texto_base = re.sub(r'\(.*?\)', '', texto_base)
            
            # Quitamos tildes
            texto_limpio = ''.join(c for c in unicodedata.normalize('NFD', texto_base) if unicodedata.category(c) != 'Mn')
            
            # Extraemos solo las palabras clave largas (ignorando conectores como "DE", "LA", "EL")
            palabras_clave = [p for p in re.findall(r'[A-Z0-9Ñ]+', texto_limpio) if len(p) > 2]
            
            if not palabras_clave:
                raise HTTPException(status_code=400, detail="Nombre de cuenca inválido para búsqueda.")

            # Construimos cláusulas ILIKE dinámicas para cada palabra clave
            # Buscamos que TODAS las palabras clave estén presentes en alguno de los campos de nombre
            condiciones_sql = []
            params_sql = {}
            
            for i, palabra in enumerate(palabras_clave):
                cond_palabra = f"""(
                    UNACCENT(nomah) ILIKE :p{i} OR 
                    UNACCENT(nomzh) ILIKE :p{i} OR 
                    UNACCENT(nom_szh) ILIKE :p{i} OR 
                    UNACCENT(nom_nss1) ILIKE :p{i} OR 
                    UNACCENT(nom_nss2) ILIKE :p{i} OR 
                    UNACCENT(nom_nss3) ILIKE :p{i}
                )"""
                condiciones_sql.append(cond_palabra)
                params_sql[f"p{i}"] = f"%{palabra}%"
            
            # Unimos todas las condiciones con AND (debe contener todas las palabras clave)
            where_clause = " AND ".join(condiciones_sql)

            q_geom = text(f"""
                SELECT geometry, nomah, nomzh, nom_szh, nom_nss1, nom_nss2, nom_nss3 
                FROM cuencas 
                WHERE {where_clause}
            """)
            
            try:
                # 🚀 INTENTO 1: Con extensión UNACCENT activada
                with engine.connect() as conn:
                    gdf_filtro = gpd.read_postgis(q_geom, conn, params=params_sql, geom_col="geometry")
            except Exception as db_err:
                error_str = str(db_err).lower()
                # Si falla (transacción abortada, sin extensión, error de sintaxis...)
                if "unaccent" in error_str or "syntax" in error_str or "aborted" in error_str or "transaction" in error_str:
                    # 🚀 FIX MAGISTRAL: Abrimos una CONEXIÓN NUEVA Y LIMPIA para evitar el bloqueo de PostgreSQL
                    with engine.connect() as conn_fallback:
                        where_clause_fallback = " AND ".join([c.replace("UNACCENT(", "").replace(") ILIKE", " ILIKE") for c in condiciones_sql])
                        q_geom_fallback = text(f"SELECT geometry, nomah, nomzh, nom_szh, nom_nss1, nom_nss2, nom_nss3 FROM cuencas WHERE {where_clause_fallback}")
                        gdf_filtro = gpd.read_postgis(q_geom_fallback, conn_fallback, params=params_sql, geom_col="geometry")
                else:
                    raise db_err
            
            if gdf_filtro.empty: 
                raise HTTPException(status_code=404, detail=f"El polígono de la cuenca '{texto_base.strip()}' no se encuentra en la base de datos espacial.")
            
            # Si encuentra varios fragmentos, los une
            if len(gdf_filtro) > 1:
                # Usamos el primer campo no nulo como índice de disolución
                col_dissolve = 'nom_nss1' if 'nom_nss1' in gdf_filtro.columns else gdf_filtro.columns[1]
                gdf_filtro = gdf_filtro.dissolve(by=col_dissolve, as_index=False)

            gdf_filtro['geometry'] = gdf_filtro['geometry'].simplify(0.005, preserve_topology=True)
            geojson_dict = json.loads(gdf_filtro.to_json())
            
            for feature in geojson_dict.get('features', []):
                props = feature.get('properties', {})
                feature['properties'] = {
                    'Macrocuenca (AH)': str(props.get('nomah') or 'N/A').title(),
                    'Zona Hidrográfica': str(props.get('nomzh') or 'N/A').title(),
                    'Subzona': str(props.get('nom_szh') or 'N/A').title(),
                    'Río Tributario': str(props.get('nom_nss1') or 'N/A').title(),
                    'Microcuenca': str(props.get('nom_nss2') or 'N/A').title(),
                    'Area_Calc': 1.0,
                    'Municipio': 'N/A'
                }
                
            return {
                "centro": {"lat": float(gdf_filtro.geometry.centroid.y.mean()), "lon": float(gdf_filtro.geometry.centroid.x.mean())},
                "geojson": geojson_dict
            }
            
        except HTTPException:
            raise
        except Exception as e: 
            raise HTTPException(status_code=500, detail=f"Fallo PostGIS interno: {str(e)}")
            
    else: 
        raise HTTPException(status_code=400, detail="Escala no soportada.")
    
# =================================================================
# 🗂️ RUTA: Catálogo Universal de Territorios (V2.1 - Con Cuencas)
# =================================================================
@router.get("/catalogo")
def obtener_catalogo_territorios():
    print("\n--- LOG: Solicitud de Catálogo Universal recibida ---")
    df = obtener_datos_dane_parquet()
    
    if df.empty:
        raise HTTPException(status_code=500, detail="No se pudo cargar la base DANE para el catálogo.")
    
    # 1. Catálogo Político (Departamentos y Municipios)
    deptos = sorted(df['dpto_norm'].dropna().unique().tolist())
    mpios_por_depto = {}
    for d in deptos:
        mpios_por_depto[d] = sorted(df[df['dpto_norm'] == d]['mun_norm'].dropna().unique().tolist())
        
    # 🚀 FIX QUIRÚRGICO: Blindaje para que Medellín jamás desaparezca de Antioquia
    if "ANTIOQUIA" in mpios_por_depto and "MEDELLIN" not in mpios_por_depto["ANTIOQUIA"]:
        mpios_por_depto["ANTIOQUIA"].append("MEDELLIN")
        mpios_por_depto["ANTIOQUIA"].sort()
        
    # 2. Catálogo Hidrológico (Nombres de Cuencas desde la Matriz)
    cuencas_lista = []
    try:
        from backend.app.database import get_engine
        engine = get_engine()
        q_cuencas = text("SELECT DISTINCT \"Territorio\" FROM matriz_maestra_demografica WHERE UPPER(\"Nivel\") = 'CUENCA' ORDER BY \"Territorio\"")
        with engine.connect() as conn:
            cuencas_bd = pd.read_sql(q_cuencas, conn)["Territorio"].tolist()
            cuencas_lista = [str(c).title() for c in cuencas_bd]
    except Exception as e:
        print(f"Error cargando catálogo de cuencas: {e}")
        cuencas_lista = ["Río Porce", "Río Nechí", "Río Cauca", "Río Magdalena"] # Fallback

    print(f"--- LOG: Catálogo enviado. {len(deptos)} deptos, {len(cuencas_lista)} cuencas. ---\n")
    
    return {
        "nacional": ["COLOMBIA"],
        "departamentos": deptos,
        "municipios": mpios_por_depto,
        "cuencas": cuencas_lista
    }