"""Tests basicos de la API: llama a los 4 endpoints y valida que las
respuestas cumplan el schema Pydantic correspondiente. El pipeline real
(LangGraph + Groq/Ollama + Chroma) se reemplaza por un runner falso via
dependency override, para que la suite no dependa de red ni credenciales.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_pipeline_runner
from api.schemas import (
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
