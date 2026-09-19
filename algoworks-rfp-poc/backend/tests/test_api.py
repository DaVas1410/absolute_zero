"""Tests basicos de la API: llama a los 4 endpoints y valida que las
respuestas cumplan el schema Pydantic correspondiente.
"""

from fastapi.testclient import TestClient

from api.main import app
from api.schemas import PipelineResult, TraceEvent

client = TestClient(app)


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
    assert len(result.requirements) == 2
    assert all(2 <= len(chunks) <= 3 for chunks in result.retrieved.values())
    assert any(v.supported for v in result.verification.values())
    assert any(not v.supported for v in result.verification.values())
    nodes = [event.node for event in result.trace_log]
    assert nodes == [
        "extract_requirements",
        "retrieve_chunks",
        "generate_draft",
        "verify_citations",
    ]


def test_get_trace_after_process():
    client.post(
        "/rfp/process",
        json={"rfp_id": "rfp_test_002", "rfp_text": "Otro texto de RFP."},
    )

    response = client.get("/rfp/rfp_test_002/trace")

    assert response.status_code == 200
    trace_log = [TraceEvent.model_validate(event) for event in response.json()]
    assert len(trace_log) == 4


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
