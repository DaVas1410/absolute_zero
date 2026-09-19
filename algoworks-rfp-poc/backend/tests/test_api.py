"""Tests basicos de la API: llama a los 4 endpoints y valida que las
respuestas cumplan el schema Pydantic correspondiente. El pipeline real
(LangGraph + Groq/Ollama + Chroma) se reemplaza por un runner falso via
dependency override, para que la suite no dependa de red ni credenciales.
"""

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_corpus_resources, get_pipeline_runner
from api.schemas import (
    Chunk,
    CorpusIngestResult,
    DraftSection,
    PipelineMetrics,
    PipelineResult,
    ReasoningPathAudit,
    Requirement,
    RetrievedChunk,
    TokenUsage,
    TraceEvent,
    VerificationResult,
)
from rag.store import build_vectorstore
from tests.fakes import FakeEmbeddings, make_pdf_bytes

client = TestClient(app)

_NODES = ["extract_requirements", "retrieve_chunks", "generate_draft", "verify_citations", "compute_traceability_metrics"]


def _fake_pipeline_result(rfp_id: str) -> PipelineResult:
    now = datetime.now(timezone.utc)
    return PipelineResult(
        rfp_id=rfp_id,
        requirements=[
            Requirement(req_id="req_001", text="Requisito de prueba.", section_target="experiencia_previa")
        ],
        retrieved={
            "req_001": [RetrievedChunk(chunk_id="chunk_001", score=0.9, justification="Justificación de prueba.")]
        },
        drafts={
            "req_001": DraftSection(
                req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"], reasoning="..."
            )
        },
        verification={
            "req_001": VerificationResult(
                req_id="req_001", supported=True, issues=[], confidence=0.9, reasoning="...", retries_used=0
            )
        },
        trace_log=[
            TraceEvent(node=node, timestamp=now, input_summary="...", output_summary="...", reasoning="...")
            for node in _NODES
        ],
        metrics=PipelineMetrics(
            total_duration_ms=100.0,
            total_tokens=TokenUsage(),
            retries_used=0,
            requirements_supported=1,
            requirements_needing_review=0,
            hallucinated_citations_caught=0,
        ),
        reasoning_path_audit=ReasoningPathAudit(is_consistent=True, node_sequence=_NODES[:-1], issues=[]),
    )


def _fake_pipeline_runner(rfp_id: str, rfp_text: str) -> PipelineResult:
    return _fake_pipeline_result(rfp_id)


@pytest.fixture(autouse=True)
def override_pipeline_runner():
    app.dependency_overrides[get_pipeline_runner] = lambda: _fake_pipeline_runner
    yield
    app.dependency_overrides.clear()


_CORPUS_VOCABULARY = ["kafka", "manufactura", "retail"]


def _fake_corpus_resources():
    chunks = [
        Chunk(
            chunk_id="chunk_seed",
            text="Chunk semilla sobre kafka.",
            source="seed.md",
            section_type="capacidades_tecnicas",
        )
    ]
    embeddings = FakeEmbeddings(_CORPUS_VOCABULARY)
    vectorstore = build_vectorstore(chunks, embeddings)
    chunk_texts_by_id = {chunk.chunk_id: chunk.text for chunk in chunks}
    return vectorstore, embeddings, chunk_texts_by_id


@pytest.fixture(autouse=True)
def override_corpus_resources(tmp_path, monkeypatch):
    import rag.corpus as corpus_module

    monkeypatch.setattr(corpus_module, "DEFAULT_INGESTED_PATH", tmp_path / "ingested_chunks.json")
    app.dependency_overrides[get_corpus_resources] = _fake_corpus_resources
    yield
    app.dependency_overrides.clear()


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_process_rfp_returns_valid_pipeline_result():
    response = client.post(
        "/rfp/process",
        json={"rfp_id": "rfp_test_001", "rfp_text": "Texto de RFP de prueba."},
    )

    assert response.status_code == 200
    result = PipelineResult.model_validate(response.json())
    assert result.rfp_id == "rfp_test_001"
    nodes = [event.node for event in result.trace_log]
    assert nodes == _NODES
    assert result.metrics.requirements_supported == 1
    assert result.reasoning_path_audit.is_consistent is True


def test_get_trace_after_process():
    client.post(
        "/rfp/process",
        json={"rfp_id": "rfp_test_002", "rfp_text": "Otro texto de RFP."},
    )

    response = client.get("/rfp/rfp_test_002/trace")

    assert response.status_code == 200
    trace_log = [TraceEvent.model_validate(event) for event in response.json()]
    assert len(trace_log) == 5


def test_get_trace_unknown_rfp_returns_error_format():
    response = client.get("/rfp/unknown_rfp/trace")

    assert response.status_code == 404
    body = response.json()
    assert set(body.keys()) == {"error", "detail"}
    assert isinstance(body["error"], str)
    assert isinstance(body["detail"], str)


def test_feedback_endpoint():
    response = client.post("/rfp/req_001/feedback", json={"accepted": True})

    assert response.status_code == 200
    assert response.json() == {"status": "received"}


def test_ingest_corpus_pdf_returns_chunks_and_makes_them_retrievable():
    pdf_bytes = make_pdf_bytes("Algoworks tiene experiencia en proyectos de manufactura.")

    response = client.post(
        "/corpus/ingest",
        files={"file": ("propuesta_manufactura.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"section_type": "experiencia_previa"},
    )

    assert response.status_code == 200
    result = CorpusIngestResult.model_validate(response.json())
    assert result.source == "propuesta_manufactura.pdf"
    assert result.section_type == "experiencia_previa"
    assert result.chunk_count >= 1
    assert result.chunks_added[0].chunk_id == "propuesta_manufactura_001"


def test_ingest_corpus_pdf_rejects_invalid_section_type():
    pdf_bytes = make_pdf_bytes("Contenido de prueba.")

    response = client.post(
        "/corpus/ingest",
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"section_type": "no_es_un_tipo_valido"},
    )

    assert response.status_code == 422


def test_ingest_corpus_pdf_rejects_empty_pdf():
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    empty_pdf_bytes = bytes(pdf.output())

    response = client.post(
        "/corpus/ingest",
        files={"file": ("vacio.pdf", io.BytesIO(empty_pdf_bytes), "application/pdf")},
        data={"section_type": "experiencia_previa"},
    )

    assert response.status_code == 422
    body = response.json()
    assert set(body.keys()) == {"error", "detail"}
