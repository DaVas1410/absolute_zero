"""Tests del cliente HTTP del backend: check_health y BackendError. Sin red
real — usa la librería responses para mockear las respuestas HTTP."""

import responses

from api_client import BackendError, check_health

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
