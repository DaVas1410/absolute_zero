"""Cliente HTTP delgado para el backend FastAPI (docs/CONTRATO_DATOS.md).
No importa los schemas Pydantic del backend: el frontend es un proyecto
Python separado y consume las respuestas como dicts planos."""

import requests

DEFAULT_TIMEOUT = 10.0


class BackendError(Exception):
    def __init__(self, error: str, detail: str):
        self.error = error
        self.detail = detail
        super().__init__(f"{error}: {detail}")


def check_health(base_url: str) -> bool:
    try:
        response = requests.get(f"{base_url}/health", timeout=DEFAULT_TIMEOUT)
        return response.ok
    except requests.exceptions.RequestException:
        return False


def _raise_for_error_response(response: requests.Response) -> None:
    if response.ok:
        return
    try:
        body = response.json()
        error = body.get("error", "Error")
        detail = body.get("detail", response.text)
    except ValueError:
        error, detail = "Error", response.text
    raise BackendError(error=error, detail=detail)


def process_rfp(base_url: str, rfp_id: str, rfp_text: str, timeout: float = 120.0) -> dict:
    try:
        response = requests.post(
            f"{base_url}/rfp/process",
            json={"rfp_id": rfp_id, "rfp_text": rfp_text},
            timeout=timeout,
        )
    except requests.exceptions.RequestException as exc:
        raise BackendError(error="Connection Error", detail=str(exc)) from exc
    _raise_for_error_response(response)
    return response.json()


def get_trace(base_url: str, rfp_id: str, timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
    try:
        response = requests.get(f"{base_url}/rfp/{rfp_id}/trace", timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise BackendError(error="Connection Error", detail=str(exc)) from exc
    _raise_for_error_response(response)
    return response.json()


def submit_feedback(base_url: str, req_id: str, accepted: bool, timeout: float = DEFAULT_TIMEOUT) -> dict:
    try:
        response = requests.post(
            f"{base_url}/rfp/{req_id}/feedback",
            json={"accepted": accepted},
            timeout=timeout,
        )
    except requests.exceptions.RequestException as exc:
        raise BackendError(error="Connection Error", detail=str(exc)) from exc
    _raise_for_error_response(response)
    return response.json()
