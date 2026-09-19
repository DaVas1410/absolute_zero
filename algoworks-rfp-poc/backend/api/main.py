"""Punto de entrada de la API FastAPI (backend <-> frontend).

Contrato de endpoints: ver CLAUDE.md, sección 5.
"""

import logging
from functools import lru_cache
from http import HTTPStatus
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.schemas import PipelineResult, TraceEvent
from graph.graph import run_pipeline
from graph.llm import get_chat_llm
from rag.corpus import load_dummy_chunks
from rag.embed import SentenceTransformerEmbeddings
from rag.store import build_vectorstore

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


# Guarda en memoria el último PipelineResult real (no mockeado) por rfp_id,
# para que GET /rfp/{rfp_id}/trace pueda devolver su trace_log.
_pipeline_results: dict[str, PipelineResult] = {}


PipelineRunner = Callable[[str, str], PipelineResult]


@lru_cache(maxsize=1)
def _get_corpus_resources():
    chunks = load_dummy_chunks()
    embeddings = SentenceTransformerEmbeddings()
    vectorstore = build_vectorstore(chunks, embeddings)
    chunk_texts_by_id = {chunk.chunk_id: chunk.text for chunk in chunks}
    return vectorstore, embeddings, chunk_texts_by_id


@app.on_event("startup")
def _warm_up_corpus_resources() -> None:
    # Precalienta embeddings + vectorstore en el arranque (en vez de en el
    # primer POST /rfp/process) para no pagar el costo (descarga del modelo
    # de embeddings, indexado de Chroma) en la primera request de una demo.
    _get_corpus_resources()


def _default_pipeline_runner(rfp_id: str, rfp_text: str) -> PipelineResult:
    llm_small = get_chat_llm("small")
    llm_large = get_chat_llm("large")
    vectorstore, embeddings, chunk_texts_by_id = _get_corpus_resources()
    return run_pipeline(rfp_id, rfp_text, llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id)


def get_pipeline_runner() -> PipelineRunner:
    return _default_pipeline_runner


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/rfp/process", response_model=PipelineResult)
def process_rfp(
    payload: RFPProcessRequest,
    pipeline_runner: PipelineRunner = Depends(get_pipeline_runner),
) -> PipelineResult:
    result = pipeline_runner(payload.rfp_id, payload.rfp_text)
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
