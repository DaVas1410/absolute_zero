"""Tests del cliente HTTP del backend: check_health y BackendError. Sin red
real — usa la librería responses para mockear las respuestas HTTP."""

import pytest
import responses
from requests.exceptions import ConnectionError

from api_client import BackendError, check_health, process_rfp

BASE_URL = "http://localhost:8000"


@responses.activate
def test_check_health_returns_true_on_200():
    responses.add(responses.GET, f"{BASE_URL}/health", json={"status": "ok"}, status=200)

    assert check_health(BASE_URL) is True


@responses.activate
def test_check_health_returns_false_on_error_status():
    responses.add(responses.GET, f"{BASE_URL}/health", json={"error": "x", "detail": "y"}, status=500)

    assert check_health(BASE_URL) is False


def test_check_health_returns_false_on_connection_failure():
    assert check_health("http://localhost:9") is False  # puerto que nadie escucha: falla la conexión


def test_backend_error_carries_error_and_detail():
    exc = BackendError(error="Not Found", detail="no existe")

    assert exc.error == "Not Found"
    assert exc.detail == "no existe"
    assert "Not Found" in str(exc)


@responses.activate
def test_process_rfp_returns_parsed_json_on_success():
    fake_result = {"rfp_id": "rfp_001", "requirements": []}
    responses.add(responses.POST, f"{BASE_URL}/rfp/process", json=fake_result, status=200)

    result = process_rfp(BASE_URL, "rfp_001", "texto de prueba")

    assert result == fake_result


@responses.activate
def test_process_rfp_raises_backend_error_on_4xx():
    responses.add(
        responses.POST,
        f"{BASE_URL}/rfp/process",
        json={"error": "Unprocessable Entity", "detail": "rfp_text vacío"},
        status=422,
    )

    with pytest.raises(BackendError) as exc_info:
        process_rfp(BASE_URL, "rfp_001", "")

    assert exc_info.value.error == "Unprocessable Entity"
    assert exc_info.value.detail == "rfp_text vacío"


@responses.activate
def test_process_rfp_raises_backend_error_on_connection_failure():
    responses.add(responses.POST, f"{BASE_URL}/rfp/process", body=ConnectionError("sin conexión"))

    with pytest.raises(BackendError) as exc_info:
        process_rfp(BASE_URL, "rfp_001", "texto")

    assert exc_info.value.error == "Connection Error"
