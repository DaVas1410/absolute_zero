"""Punto de entrada de la API FastAPI (backend <-> frontend).

Contrato de endpoints: ver CLAUDE.md, sección 5.
"""

import logging
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

from api.schemas import CorpusIngestResult, PipelineResult, ProposalDocument, SectionType, TraceEvent
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


PipelineRunner = Callable[[str, str], PipelineResult]


@lru_cache(maxsize=1)
def _get_corpus_resources():
    chunks = corpus.load_dummy_chunks() + corpus.load_ingested_chunks(corpus.DEFAULT_INGESTED_PATH)
    embeddings = SentenceTransformerEmbeddings()
    vectorstore = build_vectorstore(chunks, embeddings)
    chunk_texts_by_id = {chunk.chunk_id: chunk.text for chunk in chunks}
    return vectorstore, embeddings, chunk_texts_by_id


CorpusResources = tuple[Chroma, Embeddings, dict[str, str]]


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
    vectorstore, embeddings, chunk_texts_by_id = _get_corpus_resources()
    return run_pipeline(rfp_id, rfp_text, llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id)


def get_pipeline_runner() -> PipelineRunner:
    return _default_pipeline_runner


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
    _vectorstore, _embeddings, chunk_texts_by_id = _get_corpus_resources()
    return run_compose(
        rfp_id, result.requirements, result.drafts, result.verification, llm_large, chunk_texts_by_id
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
    vectorstore, _embeddings, chunk_texts_by_id = corpus_resources
    file_bytes = file.file.read()
    resolved_source = source or file.filename or "documento.pdf"

    try:
        text = extract_pdf_text(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    chunks = chunk_pdf_text(text, source=resolved_source, section_type=section_type)
    add_chunks(vectorstore, chunks)
    chunk_texts_by_id.update({chunk.chunk_id: chunk.text for chunk in chunks})
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


@app.post("/rfp/{req_id}/feedback")
def submit_feedback(req_id: str, payload: FeedbackRequest) -> dict[str, str]:
    logger.info("Feedback recibido para req_id=%s: accepted=%s", req_id, payload.accepted)
    return {"status": "received"}
