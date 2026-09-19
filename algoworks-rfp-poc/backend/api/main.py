"""Punto de entrada de la API FastAPI (backend <-> frontend).

Contrato de endpoints: ver CLAUDE.md, sección 5.
"""

import logging
from datetime import datetime, timezone
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.schemas import (
    DraftSection,
    PipelineResult,
    Requirement,
    RetrievedChunk,
    TraceEvent,
    VerificationResult,
)

logger = logging.getLogger("algoworks_rfp_api")

app = FastAPI(title="Algoworks RFP PoC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Formato de error estándar: {"error": str, "detail": str} (CLAUDE.md, sección 5) ---


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": HTTPStatus(exc.status_code).phrase, "detail": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "Unprocessable Entity", "detail": str(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no manejado procesando %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "Ha ocurrido un error inesperado."},
    )


# --- Modelos de request de la API (no forman parte del contrato de datos del pipeline) ---


class RFPProcessRequest(BaseModel):
    rfp_id: str
    rfp_text: str


class FeedbackRequest(BaseModel):
    accepted: bool


# Guarda en memoria el último PipelineResult mockeado por rfp_id, para que
# GET /rfp/{rfp_id}/trace pueda devolver su trace_log.
_pipeline_results: dict[str, PipelineResult] = {}


def _build_mock_pipeline_result(rfp_id: str) -> PipelineResult:
    # TODO: reemplazar por invocación real del grafo LangGraph
    # (extract_requirements -> retrieve_chunks -> generate_draft -> verify_citations).
    # Todo lo que sigue es un PipelineResult de EJEMPLO, hardcodeado, solo para
    # que frontend pueda construir el panel de explicabilidad desde ya.

    requirements = [
        Requirement(
            req_id="req_001",
            text=(
                "El proveedor debe demostrar experiencia previa en proyectos de "
                "integración de datos de tamaño y complejidad similares."
            ),
            section_target="experiencia_previa",
        ),
        Requirement(
            req_id="req_002",
            text=(
                "El proveedor debe describir las capacidades técnicas y la "
                "arquitectura propuesta para la integración de datos en tiempo real."
            ),
            section_target="capacidades_tecnicas",
        ),
    ]

    retrieved = {
        "req_001": [
            RetrievedChunk(
                chunk_id="chunk_001",
                score=0.89,
                justification=(
                    "El chunk describe un proyecto de integración de datos de "
                    "alcance comparable, incluyendo volumen de datos y timeline."
                ),
            ),
            RetrievedChunk(
                chunk_id="chunk_002",
                score=0.76,
                justification=(
                    "Menciona experiencia previa con el mismo tipo de cliente "
                    "(sector retail), relevante para el requisito de experiencia."
                ),
            ),
            RetrievedChunk(
                chunk_id="chunk_003",
                score=0.61,
                justification=(
                    "Relacionado tangencialmente: describe un proyecto de "
                    "migración de datos, no de integración, pero comparte stack."
                ),
            ),
        ],
        "req_002": [
            RetrievedChunk(
                chunk_id="chunk_004",
                score=0.83,
                justification=(
                    "Describe la arquitectura de referencia de Algoworks para "
                    "pipelines de datos en tiempo real (Kafka + Spark Streaming)."
                ),
            ),
            RetrievedChunk(
                chunk_id="chunk_005",
                score=0.70,
                justification=(
                    "Detalla las certificaciones técnicas del equipo en "
                    "plataformas de streaming de datos."
                ),
            ),
        ],
    }

    drafts = {
        "req_001": DraftSection(
            req_id="req_001",
            text=(
                "Algoworks cuenta con experiencia comprobada en proyectos de "
                "integración de datos de alcance similar [[chunk_001]], incluyendo "
                "trabajo previo con clientes del sector retail [[chunk_002]]."
            ),
            cited_chunks=["chunk_001", "chunk_002"],
        ),
        "req_002": DraftSection(
            req_id="req_002",
            text=(
                "Proponemos una arquitectura basada en Kafka y Spark Streaming "
                "para la integración de datos en tiempo real [[chunk_004]], con "
                "una latencia end-to-end de 50ms garantizada por el SLA del "
                "proveedor cloud [[chunk_004]]."
            ),
            cited_chunks=["chunk_004"],
        ),
    }

    verification = {
        "req_001": VerificationResult(
            req_id="req_001",
            supported=True,
            issues=[],
            confidence=0.91,
        ),
        "req_002": VerificationResult(
            req_id="req_002",
            supported=False,
            issues=[
                "chunk_004 describe la arquitectura de streaming pero no "
                "menciona ningún SLA de latencia de 50ms; esa afirmación "
                "parece inventada por el generador.",
            ],
            confidence=0.38,
        ),
    }

    now = datetime.now(timezone.utc)
    trace_log = [
        TraceEvent(
            node="extract_requirements",
            timestamp=now,
            input_summary=f"rfp_id={rfp_id}, texto de RFP recibido",
            output_summary=f"{len(requirements)} requisitos extraídos",
            reasoning=(
                "Se identificaron 2 secciones explícitas en el RFP (experiencia "
                "previa y capacidades técnicas) mediante structured output; no "
                "fue necesario el fallback de split por líneas numeradas."
            ),
        ),
        TraceEvent(
            node="retrieve_chunks",
            timestamp=now,
            input_summary="2 requisitos, corpus de 5 chunks disponibles",
            output_summary="3 chunks para req_001, 2 chunks para req_002",
            reasoning=(
                "Se recuperaron los chunks con mayor similitud coseno por "
                "requisito (umbral 0.6) y se generó una justificación en "
                "lenguaje natural para cada uno."
            ),
        ),
        TraceEvent(
            node="generate_draft",
            timestamp=now,
            input_summary="2 requisitos + chunks recuperados",
            output_summary="2 DraftSection generados, todos con citas [[chunk_id]] válidas",
            reasoning=(
                "El post-procesamiento verificó que todos los chunk_id citados "
                "existen entre los chunks recuperados; no se detectaron citas "
                "alucinadas en esta corrida."
            ),
        ),
        TraceEvent(
            node="verify_citations",
            timestamp=now,
            input_summary="2 DraftSection citados",
            output_summary="req_001 soportado, req_002 no soportado (1 reintento agotado)",
            reasoning=(
                "req_002 afirma un SLA de latencia de 50ms que chunk_004 no "
                "respalda; se disparó un reintento a generate_draft que no "
                "corrigió el problema, por lo que se marca para revisión humana."
            ),
        ),
    ]

    return PipelineResult(
        rfp_id=rfp_id,
        requirements=requirements,
        retrieved=retrieved,
        drafts=drafts,
        verification=verification,
        trace_log=trace_log,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/rfp/process", response_model=PipelineResult)
def process_rfp(payload: RFPProcessRequest) -> PipelineResult:
    result = _build_mock_pipeline_result(payload.rfp_id)
    _pipeline_results[payload.rfp_id] = result
    return result


@app.get("/rfp/{rfp_id}/trace", response_model=list[TraceEvent])
def get_trace(rfp_id: str) -> list[TraceEvent]:
    result = _pipeline_results.get(rfp_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay trace disponible para rfp_id={rfp_id!r}. "
                "Ejecuta POST /rfp/process primero."
            ),
        )
    return result.trace_log


@app.post("/rfp/{req_id}/feedback")
def submit_feedback(req_id: str, payload: FeedbackRequest) -> dict[str, str]:
    logger.info("Feedback recibido para req_id=%s: accepted=%s", req_id, payload.accepted)
    return {"status": "received"}
