"""Punto de entrada de la API FastAPI (backend <-> frontend).

Contrato de endpoints: ver CLAUDE.md, sección 5. Todavía sin lógica de
negocio — solo el andamiaje necesario para validar que el entorno funciona
(GET /health).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Algoworks RFP PoC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
