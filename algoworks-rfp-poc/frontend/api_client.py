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
