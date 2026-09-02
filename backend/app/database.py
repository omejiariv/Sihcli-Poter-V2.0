# backend/app/database.py
import os
from pathlib import Path
from sqlalchemy import create_engine
from dotenv import load_dotenv

# 1. Forzamos a Python a buscar el .env exactamente en la misma carpeta que este archivo
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_engine():
    if not DATABASE_URL:
        raise ValueError(f"CRÍTICO: No se encontró DATABASE_URL. Asegúrate de que el archivo .env existe en: {env_path}")
    
    # Conexión optimizada para FastAPI
    return create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)