# backend/app/database.py
import os
import toml
from pathlib import Path
from sqlalchemy import create_engine

def get_engine():
    # 1. Intentamos leer del entorno directo
    db_url = os.environ.get("DATABASE_URL")
    
    # 2. Si no hay URL, buscamos el archivo secrets.toml de Streamlit
    if not db_url:
        try:
            # Subimos desde backend/app/database.py hasta la raíz del proyecto
            root_dir = Path(__file__).resolve().parent.parent.parent
            secrets_path = root_dir / ".streamlit" / "secrets.toml"
            
            if secrets_path.exists():
                with open(secrets_path, "r", encoding="utf-8") as f:
                    secrets = toml.load(f)
                    db_url = secrets.get("DATABASE_URL") or secrets.get("connections", {}).get("supabase", {}).get("url")
        except Exception as e:
            print(f"Error leyendo secrets.toml: {e}")

    # 3. Escudo final de seguridad
    if not db_url:
        raise ValueError("CRÍTICO: No se encontró DATABASE_URL. El backend no puede conectar a Supabase.")

    # 4. Ajuste universal: SQLAlchemy requiere 'postgresql://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    return create_engine(db_url, pool_pre_ping=True, pool_size=5)