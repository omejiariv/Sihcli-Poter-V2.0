# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api import router_demografia
from backend.app.api import router_hidrologia  # 🚀 NUEVA IMPORTACIÓN DEL MOTOR HÍDRICO

app = FastAPI(
    title="Sihcli-Poter API Core",
    description="Motor de cálculo hidrosocial, climático y geomorfológico",
    version="2.0.0"
)

# Configuración CORS para permitir comunicación fluida
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conectamos los enrutadores a la aplicación principal
app.include_router(router_demografia.router)
app.include_router(router_hidrologia.router)  # 🚀 NUEVA CONEXIÓN AL CEREBRO

@app.get("/")
def read_root():
    return {"status": "El Aleph está en línea y operando. Backend V2.0 inicializado en la nube."}