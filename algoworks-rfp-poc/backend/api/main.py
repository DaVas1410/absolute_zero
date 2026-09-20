"""Punto de entrada de la API FastAPI (backend <-> frontend).

Contrato de endpoints: ver CLAUDE.md, sección 5.
"""

import logging
import threading
from functools import lru_cache
from http import HTTPStatus
from typing import Callable

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

load_dotenv()

from api.schemas import (
    Chunk,
    CorpusIngestResult,
    PipelineResult,
    ProposalDocument,
    RfpProgress,
    SectionType,
    TraceabilityReport,
    TraceEvent,
)
from graph.compose_graph import run_compose
from graph.graph import run_pipeline
from graph.llm import get_chat_llm
from rag import corpus
from rag.embed import SentenceTransformerEmbeddings
from rag.pdf_ingest import chunk_pdf_text, extract_pdf_text
from rag.store import add_chunks, build_vectorstore

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

# Feedback humano recibido via POST /rfp/{req_id}/feedback, por req_id.
# Antes este endpoint solo logueaba y no persistia nada; ahora alimenta
# verification_rate en GET /rfp/{rfp_id}/traceability-report.
_feedback: dict[str, bool] = {}

# Progreso en vivo de un POST /rfp/process/start por rfp_id (ver RfpProgress).
# El hilo de fondo escribe, GET /rfp/{rfp_id}/progress lee - protegido por
# _progress_lock porque ambos lados corren en threads distintos.
_pipeline_progress: dict[str, RfpProgress] = {}
_progress_lock = threading.Lock()


PipelineRunner = Callable[[str, str], PipelineResult]


@lru_cache(maxsize=1)
def _get_corpus_resources():
    chunks = corpus.load_dummy_chunks() + corpus.load_ingested_chunks(corpus.DEFAULT_INGESTED_PATH)
    embeddings = SentenceTransformerEmbeddings()
    vectorstore = build_vectorstore(chunks, embeddings)
    chunk_texts_by_id = {chunk.chunk_id: chunk.text for chunk in chunks}
    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    return vectorstore, embeddings, chunk_texts_by_id, chunk_by_id


CorpusResources = tuple[Chroma, Embeddings, dict[str, str], dict[str, Chunk]]


def get_corpus_resources() -> CorpusResources:
    return _get_corpus_resources()


@app.on_event("startup")
def _warm_up_corpus_resources() -> None:
    # Precalienta embeddings + vectorstore en el arranque (en vez de en el
    # primer POST /rfp/process) para no pagar el costo (descarga del modelo
    # de embeddings, indexado de Chroma) en la primera request de una demo.
    _get_corpus_resources()


def _default_pipeline_runner(rfp_id: str, rfp_text: str) -> PipelineResult:
    llm_small = get_chat_llm("small")
    llm_large = get_chat_llm("large")
    vectorstore, embeddings, chunk_texts_by_id, _chunk_by_id = _get_corpus_resources()
    return run_pipeline(rfp_id, rfp_text, llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id)


def get_pipeline_runner() -> PipelineRunner:
    return _default_pipeline_runner


def _run_pipeline_in_background(rfp_id: str, rfp_text: str) -> None:
    def on_progress(trace_log: list[TraceEvent]) -> None:
        with _progress_lock:
            _pipeline_progress[rfp_id].trace_log = trace_log

    try:
        llm_small = get_chat_llm("small")
        llm_large = get_chat_llm("large")
        vectorstore, embeddings, chunk_texts_by_id, _chunk_by_id = _get_corpus_resources()
        result = run_pipeline(
            rfp_id,
            rfp_text,
            llm_small,
            llm_large,
            vectorstore,
            embeddings,
            chunk_texts_by_id,
            on_progress=on_progress,
        )
        _pipeline_results[rfp_id] = result
        with _progress_lock:
            _pipeline_progress[rfp_id] = RfpProgress(
                rfp_id=rfp_id, status="done", trace_log=result.trace_log, result=result
            )
    except Exception as exc:
        logger.exception("Error corriendo el pipeline en background para rfp_id=%s", rfp_id)
        with _progress_lock:
            trace_log = _pipeline_progress[rfp_id].trace_log if rfp_id in _pipeline_progress else []
            _pipeline_progress[rfp_id] = RfpProgress(
                rfp_id=rfp_id, status="error", trace_log=trace_log, error=str(exc)
            )


ComposeRunner = Callable[[str], ProposalDocument]


def _default_compose_runner(rfp_id: str) -> ProposalDocument:
    result = _pipeline_results.get(rfp_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay resultados disponibles para rfp_id={rfp_id!r}. "
                "Ejecuta POST /rfp/process (o /rfp/process/pdf) primero."
            ),
        )
    llm_large = get_chat_llm("large")
    _vectorstore, _embeddings, _chunk_texts_by_id, chunk_by_id = _get_corpus_resources()
    return run_compose(
        rfp_id, result.requirements, result.drafts, result.verification, llm_large, chunk_by_id
    )


def get_compose_runner() -> ComposeRunner:
    return _default_compose_runner


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


@app.post("/corpus/ingest", response_model=CorpusIngestResult)
def ingest_corpus_pdf(
    file: UploadFile = File(...),
    section_type: SectionType = Form(...),
    source: str | None = Form(None),
    corpus_resources: CorpusResources = Depends(get_corpus_resources),
) -> CorpusIngestResult:
    # def sincrona (no async): la extraccion PDF, el embedding y (en el otro
    # endpoint) el pipeline completo son trabajo bloqueante de CPU/red. Con
    # async def y sin await, ese trabajo corre directo en el event loop y
    # congela todo el proceso (incluso /health) mientras dura. Starlette
    # corre las funciones def sincronas en un threadpool automaticamente,
    # igual que el process_rfp preexistente.
    vectorstore, _embeddings, chunk_texts_by_id, chunk_by_id = corpus_resources
    file_bytes = file.file.read()
    resolved_source = source or file.filename or "documento.pdf"

    try:
        text = extract_pdf_text(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    chunks = chunk_pdf_text(text, source=resolved_source, section_type=section_type)
    add_chunks(vectorstore, chunks)
    chunk_texts_by_id.update({chunk.chunk_id: chunk.text for chunk in chunks})
    chunk_by_id.update({chunk.chunk_id: chunk for chunk in chunks})
    corpus.append_ingested_chunks(chunks, path=corpus.DEFAULT_INGESTED_PATH)

    return CorpusIngestResult(
        source=resolved_source,
        section_type=section_type,
        chunks_added=chunks,
        chunk_count=len(chunks),
    )


@app.post("/rfp/process/pdf", response_model=PipelineResult)
def process_rfp_pdf(
    file: UploadFile = File(...),
    rfp_id: str = Form(...),
    pipeline_runner: PipelineRunner = Depends(get_pipeline_runner),
) -> PipelineResult:
    file_bytes = file.file.read()

    try:
        rfp_text = extract_pdf_text(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = pipeline_runner(rfp_id, rfp_text)
    _pipeline_results[rfp_id] = result
    return result


@app.post("/rfp/process/start")
def start_process_rfp(payload: RFPProcessRequest) -> dict[str, str]:
    """Version no bloqueante de POST /rfp/process: arranca el pipeline en un
    hilo de fondo y devuelve de inmediato. El progreso en vivo (trace_log
    creciendo nodo por nodo) se consulta con GET /rfp/{rfp_id}/progress."""
    with _progress_lock:
        _pipeline_progress[payload.rfp_id] = RfpProgress(rfp_id=payload.rfp_id, status="running", trace_log=[])
    threading.Thread(
        target=_run_pipeline_in_background,
        args=(payload.rfp_id, payload.rfp_text),
        daemon=True,
    ).start()
    return {"rfp_id": payload.rfp_id, "status": "started"}


@app.post("/rfp/process/pdf/start")
def start_process_rfp_pdf(file: UploadFile = File(...), rfp_id: str = Form(...)) -> dict[str, str]:
    file_bytes = file.file.read()
    try:
        rfp_text = extract_pdf_text(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with _progress_lock:
        _pipeline_progress[rfp_id] = RfpProgress(rfp_id=rfp_id, status="running", trace_log=[])
    threading.Thread(
        target=_run_pipeline_in_background,
        args=(rfp_id, rfp_text),
        daemon=True,
    ).start()
    return {"rfp_id": rfp_id, "status": "started"}


@app.get("/rfp/{rfp_id}/progress", response_model=RfpProgress)
def get_progress(rfp_id: str) -> RfpProgress:
    with _progress_lock:
        snapshot = _pipeline_progress.get(rfp_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay progreso para rfp_id={rfp_id!r}. Ejecuta POST /rfp/process/start primero.",
        )
    return snapshot


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


@app.post("/rfp/{rfp_id}/compose", response_model=ProposalDocument)
def compose_proposal_endpoint(
    rfp_id: str,
    compose_runner: ComposeRunner = Depends(get_compose_runner),
) -> ProposalDocument:
    return compose_runner(rfp_id)


@app.get("/rfp/{rfp_id}/traceability-report", response_model=TraceabilityReport)
def get_traceability_report(rfp_id: str) -> TraceabilityReport:
    result = _pipeline_results.get(rfp_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay resultados disponibles para rfp_id={rfp_id!r}. "
                "Ejecuta POST /rfp/process (o /rfp/process/pdf) primero."
            ),
        )
    metrics = result.metrics
    total_responses = len(result.requirements)
    verified_count = sum(1 for req in result.requirements if req.req_id in _feedback)
    return TraceabilityReport(
        rfp_id=rfp_id,
        total_responses=total_responses,
        fully_cited=metrics.fully_cited_count,
        partially_cited=metrics.partially_cited_count,
        uncited=metrics.uncited_count,
        traceability_rate=metrics.traceability_rate,
        partial_rate=metrics.partial_rate,
        uncited_rate=metrics.uncited_rate,
        verified_count=verified_count,
        verification_rate=verified_count / total_responses if total_responses else 0.0,
    )


@app.post("/rfp/{req_id}/feedback")
def submit_feedback(req_id: str, payload: FeedbackRequest) -> dict[str, str]:
    logger.info("Feedback recibido para req_id=%s: accepted=%s", req_id, payload.accepted)
    _feedback[req_id] = payload.accepted
    return {"status": "received"}
