from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import pandas as pd
import numpy as np
from sqlalchemy import text
import traceback
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from frontend.modules.db_manager import get_engine

router = APIRouter(prefix="/api/hidrologia", tags=["Hidrologia"])

class ConsultaEstaciones(BaseModel):
    territorio: str
    ids_estaciones: List[str]

@router.post("/perfil_base")
def obtener_perfil_base(consulta: ConsultaEstaciones):
    if not consulta.ids_estaciones:
        raise HTTPException(status_code=400, detail="No se proporcionaron estaciones")

    try:
        ids_fmt = ",".join([f"'{str(x).strip()}'" for x in consulta.ids_estaciones])
        engine = get_engine()
        query = text(f"SELECT id_estacion, fecha, valor FROM precipitacion WHERE id_estacion IN ({ids_fmt})")
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)

        if df.empty:
            return {"meses": [], "precipitacion": [], "error": "No hay registros históricos."}

        # 1. Limpieza base
        df = df.drop_duplicates(subset=['id_estacion', 'fecha'])
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce')
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        df = df.dropna(subset=['fecha', 'valor'])
        
        # Filtro de anomalías físicas (Si está en décimas de mm, 8000 = 800mm, es válido)
        # Cortamos en 15000 (1500 mm mensuales) para ser seguros.
        df = df[(df['valor'] >= 0) & (df['valor'] < 15000)]

        df['mes'] = df['fecha'].dt.month
        df['dia'] = df['fecha'].dt.day
        df['año'] = df['fecha'].dt.year

        # ====================================================================
        # 🕵️‍♂️ EL EXORCISMO DE ENERO (La Cura del Formato Invertido)
        # ====================================================================
        # Si el motor detecta que el mes es 1 (Enero) y el día está entre 2 y 12, 
        # sabe que fue víctima del error MM/DD/YYYY y devuelve el mes a la normalidad.
        mask_invertidas = (df['mes'] == 1) & (df['dia'] >= 2) & (df['dia'] <= 12)
        df.loc[mask_invertidas, 'mes'] = df.loc[mask_invertidas, 'dia']
        # ====================================================================

        # 2. Agrupamiento Mensual y Multianual
        df_mensual = df.groupby(['id_estacion', 'año', 'mes'])['valor'].sum().reset_index()
        df_perfil = df_mensual.groupby('mes')['valor'].mean().reset_index()
        
        perfil_final = []
        for i in range(1, 13):
            val = df_perfil[df_perfil['mes'] == i]['valor'].mean()
            perfil_final.append(round(val, 1) if not pd.isna(val) else 0.0)

        # 3. ETP DINÁMICA SIMULADA
        etp = []
        for lluvia_mes in perfil_final:
            etp_mes = 150 - (lluvia_mes * 0.25)
            etp.append(round(max(70.0, min(150.0, etp_mes)), 1))

        return {
            "territorio": consulta.territorio,
            "meses": ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
            "precipitacion": perfil_final,
            "evapotranspiracion": etp
        }
        
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error en BD/Cálculo: {str(e)}")