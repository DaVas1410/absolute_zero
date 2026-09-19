# Frontend Explainability UI (Streamlit) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Streamlit frontend that drives `POST /rfp/process` and renders the full `PipelineResult` — chunks/score/justification, the draft with inline citation highlighting, the verifier's verdict, sub-project A's reasoning/grounding-similarity/path-audit/metrics fields, and a human-in-the-loop accept/reject per requirement.

**Architecture:** A thin `api_client.py` wraps the 4 backend endpoints and raises a single `BackendError` on any failure. A pure `rendering.py` holds display-transform helpers with no Streamlit dependency (testable without a UI harness). `sample_rfps.py` loads canned demo RFPs from `data/sample_rfps/`. `app.py` is orchestration-only: it wires widgets to `st.session_state` and calls the three modules above — it holds no business logic of its own.

**Tech Stack:** Streamlit, `requests`, `uv` for dependency management (mirroring `backend/`'s existing convention), `pytest` + `responses` (HTTP mocking, no real network) for the two testable modules.

**Spec:** `docs/superpowers/specs/2026-09-18-frontend-design.md`. The backend contract it consumes is documented in `docs/CONTRATO_DATOS.md` and defined by `backend/api/schemas.py`, as extended by `docs/superpowers/plans/2026-09-18-backend-rfp-pipeline.md` (sub-project A fields: `metrics`, `reasoning_path_audit`, `DraftSection.reasoning`/`citation_similarities`/`overall_similarity`, `VerificationResult.reasoning`/`retries_used`).

## Global Constraints

- The frontend does **not** import `backend/api/schemas.py` — it's a separate Python project/venv, consuming API responses as plain `dict`s (spec §3).
- `api_client.py` is the only module that imports `requests`; `rendering.py` has zero Streamlit or `requests` dependencies so it stays unit-testable (spec §4).
- Single-page app, no tabs — everything in one continuous scroll (spec §5).
- `BackendError` carries `.error`/`.detail` matching the backend's standard `{"error", "detail"}` shape; network/timeout failures synthesize `{"error": "Connection Error", "detail": str(exc)}` (spec §6).
- No client-side retries — a failed call surfaces immediately (spec §6).
- Testing is deliberately reduced (spec §9): `api_client.py` and `rendering.py` get TDD unit tests (HTTP mocked, no network); `app.py`, `sample_rfps.py`, and the sample RFP text files are wiring/data tasks verified by import/smoke-check plus one manual click-through pass at the end — no Streamlit widget tests.
- `BACKEND_URL` is read from an environment variable, defaulting to `http://localhost:8000` (spec §3).

---

## File Structure

```
algoworks-rfp-poc/
├── frontend/
│   ├── pyproject.toml         # NEW — streamlit, requests, pytest, responses
│   ├── .python-version        # NEW — "3.12", matching backend/
│   ├── api_client.py          # NEW — BackendError + check_health/process_rfp/get_trace/submit_feedback
│   ├── rendering.py           # NEW — highlight_citations (pure)
│   ├── sample_rfps.py         # NEW — list_samples()
│   ├── app.py                 # NEW — page orchestration
│   └── tests/
│       ├── test_api_client.py # NEW
│       └── test_rendering.py  # NEW
└── data/
    └── sample_rfps/
        ├── rfp_experiencia_arquitectura.txt  # NEW
        └── rfp_sla_no_respaldado.txt          # NEW
```

`frontend/tests/` mirrors `backend/tests/`'s flat layout; `pythonpath = ["."]` in `frontend/pyproject.toml` makes `from api_client import ...` etc. work from any test file without extra path setup.

---

## Task 1: Frontend project scaffold

**Files:**
- Create: `algoworks-rfp-poc/frontend/pyproject.toml`
- Create: `algoworks-rfp-poc/frontend/.python-version`

**Interfaces:**
- Produces: a `uv`-managed project at `algoworks-rfp-poc/frontend/` with `streamlit`, `requests` as runtime deps and `pytest`, `responses` as dev deps, and `pythonpath = ["."]` configured for pytest. Every later task's `uv run` commands depend on this existing first.

- [ ] **Step 1: Create the project files**

Create `algoworks-rfp-poc/frontend/.python-version`:

```
3.12
```

Create `algoworks-rfp-poc/frontend/pyproject.toml`:

```toml
[project]
name = "algoworks-rfp-frontend"
version = "0.1.0"
description = "Frontend (Streamlit) del PoC de RFP para Algoworks"
authors = [
    { name = "Juan Daniel Vasconez Vela", email = "juan.vasconezvela@gmail.com" }
]
requires-python = ">=3.12"
dependencies = [
    "streamlit",
    "requests",
]

[dependency-groups]
dev = [
    "pytest",
    "responses",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 2: Verify the environment resolves**

Run (from `algoworks-rfp-poc/frontend/`): `uv sync`
Expected: creates `.venv` and `uv.lock` with no errors; `streamlit`, `requests`, `pytest`, `responses` all installed.

- [ ] **Step 3: Commit**

```bash
git add algoworks-rfp-poc/frontend/pyproject.toml algoworks-rfp-poc/frontend/.python-version algoworks-rfp-poc/frontend/uv.lock
git commit -m "feat: scaffold frontend project (uv, streamlit, requests)"
```

---

## Task 2: `api_client.py` — `BackendError` + `check_health`

**Files:**
- Create: `algoworks-rfp-poc/frontend/api_client.py`
- Test: `algoworks-rfp-poc/frontend/tests/test_api_client.py`

**Interfaces:**
- Produces: `BackendError(error: str, detail: str)` (exception, `.error`/`.detail` attributes) and `check_health(base_url: str) -> bool`, both from `api_client`. `BackendError` is reused by Tasks 3-4; `check_health` is consumed by Task 7 (`app.py`).

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/frontend/tests/test_api_client.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `algoworks-rfp-poc/frontend/`): `uv run pytest tests/test_api_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api_client'`.

- [ ] **Step 3: Write minimal implementation**

Create `algoworks-rfp-poc/frontend/api_client.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/frontend/api_client.py algoworks-rfp-poc/frontend/tests/test_api_client.py
git commit -m "feat: add BackendError and check_health to the API client"
```

---

## Task 3: `api_client.py` — `process_rfp`

**Files:**
- Modify: `algoworks-rfp-poc/frontend/api_client.py`
- Modify: `algoworks-rfp-poc/frontend/tests/test_api_client.py`

**Interfaces:**
- Consumes: `BackendError` (Task 2).
- Produces: `_raise_for_error_response(response: requests.Response) -> None` (internal helper, reused by Task 4) and `process_rfp(base_url: str, rfp_id: str, rfp_text: str, timeout: float = 120.0) -> dict`, both from `api_client`. Consumed by Task 7.

- [ ] **Step 1: Write the failing test**

Append to `algoworks-rfp-poc/frontend/tests/test_api_client.py`:

```python
import pytest
from requests.exceptions import ConnectionError

from api_client import process_rfp


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
```

(The `import pytest` and `from requests.exceptions import ConnectionError` lines go at the top of the file alongside the existing `import responses` / `from api_client import ...` line — extend that existing import to `from api_client import BackendError, check_health, process_rfp`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'process_rfp' from 'api_client'`.

- [ ] **Step 3: Write minimal implementation**

Append to `algoworks-rfp-poc/frontend/api_client.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_client.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/frontend/api_client.py algoworks-rfp-poc/frontend/tests/test_api_client.py
git commit -m "feat: add process_rfp to the API client"
```

---

## Task 4: `api_client.py` — `get_trace` + `submit_feedback`

**Files:**
- Modify: `algoworks-rfp-poc/frontend/api_client.py`
- Modify: `algoworks-rfp-poc/frontend/tests/test_api_client.py`

**Interfaces:**
- Consumes: `BackendError`, `_raise_for_error_response` (Task 3).
- Produces: `get_trace(base_url: str, rfp_id: str, timeout: float = DEFAULT_TIMEOUT) -> list[dict]` and `submit_feedback(base_url: str, req_id: str, accepted: bool, timeout: float = DEFAULT_TIMEOUT) -> dict`, both from `api_client`. Consumed by Task 7. This completes `api_client.py`'s public surface — no further tasks modify it.

- [ ] **Step 1: Write the failing test**

Append to `algoworks-rfp-poc/frontend/tests/test_api_client.py` (extend the `from api_client import ...` line to include `get_trace, submit_feedback`):

```python
@responses.activate
def test_get_trace_returns_parsed_json_on_success():
    fake_trace = [{"node": "extract_requirements", "reasoning": "..."}]
    responses.add(responses.GET, f"{BASE_URL}/rfp/rfp_001/trace", json=fake_trace, status=200)

    assert get_trace(BASE_URL, "rfp_001") == fake_trace


@responses.activate
def test_get_trace_raises_backend_error_on_404():
    responses.add(
        responses.GET,
        f"{BASE_URL}/rfp/unknown/trace",
        json={"error": "Not Found", "detail": "no hay trace"},
        status=404,
    )

    with pytest.raises(BackendError) as exc_info:
        get_trace(BASE_URL, "unknown")

    assert exc_info.value.detail == "no hay trace"


@responses.activate
def test_submit_feedback_returns_parsed_json_on_success():
    responses.add(responses.POST, f"{BASE_URL}/rfp/req_001/feedback", json={"status": "received"}, status=200)

    assert submit_feedback(BASE_URL, "req_001", True) == {"status": "received"}


@responses.activate
def test_submit_feedback_raises_backend_error_on_5xx():
    responses.add(
        responses.POST,
        f"{BASE_URL}/rfp/req_001/feedback",
        json={"error": "Internal Server Error", "detail": "boom"},
        status=500,
    )

    with pytest.raises(BackendError):
        submit_feedback(BASE_URL, "req_001", False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_trace' from 'api_client'`.

- [ ] **Step 3: Write minimal implementation**

Append to `algoworks-rfp-poc/frontend/api_client.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api_client.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/frontend/api_client.py algoworks-rfp-poc/frontend/tests/test_api_client.py
git commit -m "feat: add get_trace and submit_feedback to the API client"
```

---

## Task 5: `rendering.py` — `highlight_citations`

**Files:**
- Create: `algoworks-rfp-poc/frontend/rendering.py`
- Test: `algoworks-rfp-poc/frontend/tests/test_rendering.py`

**Interfaces:**
- Produces: `highlight_citations(draft_text: str) -> str` (pure function, no Streamlit/`requests` dependency), from `rendering`. Consumed by Task 7.

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/frontend/tests/test_rendering.py`:

```python
"""Tests de rendering.highlight_citations: convierte marcadores [[chunk_id]]
en texto resaltado (negrita Markdown) para mostrarse con st.markdown."""

from rendering import highlight_citations


def test_highlight_citations_bolds_single_marker():
    result = highlight_citations("Texto con cita [[chunk_001]].")

    assert result == "Texto con cita **[chunk_001]**."


def test_highlight_citations_bolds_multiple_markers():
    result = highlight_citations("Cita [[chunk_001]] y otra [[chunk_002]].")

    assert result == "Cita **[chunk_001]** y otra **[chunk_002]**."


def test_highlight_citations_passes_through_text_without_markers():
    result = highlight_citations("Texto sin ninguna cita.")

    assert result == "Texto sin ninguna cita."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rendering.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rendering'`.

- [ ] **Step 3: Write minimal implementation**

Create `algoworks-rfp-poc/frontend/rendering.py`:

```python
"""Funciones puras de transformación para mostrar datos del PipelineResult.
Sin dependencias de Streamlit: son testeables sin un harness de UI."""

import re

_CITATION_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


def highlight_citations(draft_text: str) -> str:
    return _CITATION_PATTERN.sub(lambda match: f"**[{match.group(1)}]**", draft_text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rendering.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/frontend/rendering.py algoworks-rfp-poc/frontend/tests/test_rendering.py
git commit -m "feat: add highlight_citations rendering helper"
```

---

## Task 6: Sample RFPs — data files + loader

**Files:**
- Create: `algoworks-rfp-poc/data/sample_rfps/rfp_experiencia_arquitectura.txt`
- Create: `algoworks-rfp-poc/data/sample_rfps/rfp_sla_no_respaldado.txt`
- Create: `algoworks-rfp-poc/frontend/sample_rfps.py`

**Interfaces:**
- Produces: `list_samples() -> dict[str, str]` (from `sample_rfps`), mapping a human-readable display name to the full RFP text. Consumed by Task 7. No dedicated test file per the reduced testing scope (spec §9) — this is data/wiring, verified by a direct import check in Step 2 below (same treatment the backend plan gives its own trivial loaders).

- [ ] **Step 1: Write the sample RFP files and the loader**

Create `algoworks-rfp-poc/data/sample_rfps/rfp_experiencia_arquitectura.txt`:

```
1. El proveedor debe demostrar experiencia previa en proyectos de integración de datos de tamaño y complejidad similares.
2. El proveedor debe describir su arquitectura para integración de datos en tiempo real.
```

Create `algoworks-rfp-poc/data/sample_rfps/rfp_sla_no_respaldado.txt`:

```
1. El proveedor debe describir su arquitectura para procesamiento de datos en tiempo real usando tecnologías de streaming.
2. El proveedor debe garantizar una latencia end-to-end menor a 50 milisegundos en su plataforma de streaming, respaldada por un SLA contractual.
```

Create `algoworks-rfp-poc/frontend/sample_rfps.py`:

```python
"""Carga las RFP de ejemplo desde data/sample_rfps/ para el selector del
frontend (spec: docs/superpowers/specs/2026-09-18-frontend-design.md, §7)."""

from pathlib import Path

SAMPLE_RFPS_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_rfps"

_DISPLAY_NAMES = {
    "rfp_experiencia_arquitectura.txt": "Experiencia previa + arquitectura (caso feliz)",
    "rfp_sla_no_respaldado.txt": "SLA de latencia sin respaldo (caso adversarial)",
}


def list_samples() -> dict[str, str]:
    samples: dict[str, str] = {}
    for path in sorted(SAMPLE_RFPS_DIR.glob("*.txt")):
        display_name = _DISPLAY_NAMES.get(path.name, path.stem)
        samples[display_name] = path.read_text(encoding="utf-8")
    return samples
```

- [ ] **Step 2: Verify it imports and reads both files**

Run (from `algoworks-rfp-poc/frontend/`):
```bash
uv run python -c "from sample_rfps import list_samples; samples = list_samples(); print(list(samples.keys())); assert len(samples) == 2"
```
Expected: prints both display names with no errors.

- [ ] **Step 3: Commit**

```bash
git add algoworks-rfp-poc/data/sample_rfps/rfp_experiencia_arquitectura.txt algoworks-rfp-poc/data/sample_rfps/rfp_sla_no_respaldado.txt algoworks-rfp-poc/frontend/sample_rfps.py
git commit -m "feat: add sample RFPs and loader for the demo picker"
```

---

## Task 7: `app.py` — page assembly

**Files:**
- Create: `algoworks-rfp-poc/frontend/app.py`

**Interfaces:**
- Consumes: `BackendError`, `check_health`, `process_rfp`, `get_trace`, `submit_feedback` (Tasks 2-4), `highlight_citations` (Task 5), `list_samples` (Task 6).
- Produces: the runnable Streamlit page. Nothing later depends on `app.py` — this is the final integration task.
- No dedicated automated test (spec §9: Streamlit widget code has poor unit-test ROI). Verified by a syntax check (Step 2) and the manual smoke-test pass (Step 3).

- [ ] **Step 1: Write the page**

Create `algoworks-rfp-poc/frontend/app.py`:

```python
"""Página Streamlit del PoC de RFP: consume la API del backend y muestra el
panel de explicabilidad completo.
Spec: docs/superpowers/specs/2026-09-18-frontend-design.md
"""

import os
from uuid import uuid4

import streamlit as st

from api_client import BackendError, check_health, get_trace, process_rfp, submit_feedback
from rendering import highlight_citations
from sample_rfps import list_samples

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
FREE_TEXT_OPTION = "— texto libre —"

st.set_page_config(page_title="Algoworks RFP PoC", layout="wide")

if "pipeline_result" not in st.session_state:
    st.session_state["pipeline_result"] = None
if "feedback" not in st.session_state:
    st.session_state["feedback"] = {}
if "rfp_id" not in st.session_state:
    st.session_state["rfp_id"] = f"rfp_{uuid4().hex[:8]}"

st.title("Algoworks RFP PoC — Panel de explicabilidad")

backend_is_up = check_health(BASE_URL)
if backend_is_up:
    st.caption("🟢 Backend conectado")
else:
    st.caption(f"🔴 Backend no disponible en {BASE_URL}")

st.header("1. RFP de entrada")

samples = list_samples()
sample_names = [FREE_TEXT_OPTION, *samples.keys()]
selected_sample = st.selectbox("RFP de ejemplo", sample_names)
default_text = samples.get(selected_sample, "")

rfp_text = st.text_area("Texto del RFP", value=default_text, height=200)
rfp_id = st.text_input("rfp_id", value=st.session_state["rfp_id"])

process_clicked = st.button("Procesar RFP", disabled=not backend_is_up)

if process_clicked:
    with st.spinner("Procesando RFP… (puede tardar hasta un minuto)"):
        try:
            result = process_rfp(BASE_URL, rfp_id, rfp_text)
            st.session_state["pipeline_result"] = result
            st.session_state["feedback"] = {}
        except BackendError as exc:
            st.error(f"{exc.error}: {exc.detail}")

pipeline_result = st.session_state["pipeline_result"]

if pipeline_result:
    st.header("2. Resultado")

    metrics = pipeline_result["metrics"]
    columns = st.columns(5)
    columns[0].metric("Duración total", f"{metrics['total_duration_ms'] / 1000:.1f} s")
    columns[1].metric("Tokens totales", metrics["total_tokens"]["total_tokens"])
    columns[2].metric("Costo estimado", f"${metrics['total_tokens']['estimated_cost_usd']:.4f}")
    columns[3].metric("Reintentos usados", metrics["retries_used"])
    columns[4].metric("Citas alucinadas atrapadas", metrics["hallucinated_citations_caught"])

    audit = pipeline_result["reasoning_path_audit"]
    if audit["is_consistent"]:
        st.success("✓ Camino de ejecución consistente")
    else:
        st.error(f"✗ {len(audit['issues'])} problema(s) detectado(s) en el camino de ejecución")
        for issue in audit["issues"]:
            st.markdown(f"- {issue}")

    requirements = pipeline_result["requirements"]
    retrieved = pipeline_result["retrieved"]
    drafts = pipeline_result["drafts"]
    verification = pipeline_result["verification"]

    for index, requirement in enumerate(requirements):
        req_id = requirement["req_id"]
        draft = drafts.get(req_id)
        verdict = verification.get(req_id)
        feedback = st.session_state["feedback"].get(req_id)

        title = f"{requirement['section_target']} — {requirement['text'][:80]}…"
        if feedback is True:
            title = f"✓ Aceptado | {title}"
        elif feedback is False:
            title = f"✗ Rechazado | {title}"

        with st.expander(title, expanded=(index == 0)):
            st.markdown(f"**Requisito completo:** {requirement['text']}")
            st.caption(f"section_target: {requirement['section_target']}")

            st.subheader("Chunks recuperados")
            chunks = retrieved.get(req_id, [])
            if chunks:
                st.dataframe(
                    [
                        {
                            "chunk_id": chunk["chunk_id"],
                            "score": chunk["score"],
                            "justification": chunk["justification"],
                        }
                        for chunk in sorted(chunks, key=lambda chunk: chunk["score"], reverse=True)
                    ],
                    use_container_width=True,
                )

            if draft:
                st.subheader("Borrador")
                st.markdown(highlight_citations(draft["text"]))
                st.caption(f"Por qué el modelo citó estos fragmentos: {draft.get('reasoning', '')}")

                citation_similarities = draft.get("citation_similarities", [])
                if citation_similarities:
                    st.markdown(f"**Similitud general:** {draft.get('overall_similarity', 0.0):.2f}")
                    for citation in citation_similarities:
                        st.progress(
                            min(max(citation["similarity"], 0.0), 1.0),
                            text=f"{citation['chunk_id']}: {citation['similarity']:.2f}",
                        )

            if verdict:
                st.subheader("Veredicto del verificador")
                if verdict["supported"]:
                    st.success(f"Soportado (confianza: {verdict['confidence']:.2f})")
                else:
                    st.error(f"No soportado (confianza: {verdict['confidence']:.2f})")
                st.caption(f"Reintentos usados: {verdict.get('retries_used', 0)}")
                st.caption(verdict.get("reasoning", ""))
                for issue in verdict.get("issues", []):
                    st.markdown(f"- {issue}")

            accept_col, reject_col = st.columns(2)
            if accept_col.button("Aceptar", key=f"accept_{req_id}"):
                try:
                    submit_feedback(BASE_URL, req_id, True)
                    st.session_state["feedback"][req_id] = True
                    st.rerun()
                except BackendError as exc:
                    st.warning(f"No se pudo registrar el feedback: {exc.detail}")
            if reject_col.button("Rechazar", key=f"reject_{req_id}"):
                try:
                    submit_feedback(BASE_URL, req_id, False)
                    st.session_state["feedback"][req_id] = False
                    st.rerun()
                except BackendError as exc:
                    st.warning(f"No se pudo registrar el feedback: {exc.detail}")

    with st.expander("Ver trace log completo (trazabilidad técnica)", expanded=False):
        trace_log = pipeline_result["trace_log"]
        st.dataframe(
            [
                {
                    "node": event["node"],
                    "duration_ms": event.get("duration_ms", 0.0),
                    "tokens": (event.get("tokens") or {}).get("total_tokens", 0),
                    "reasoning": event["reasoning"],
                }
                for event in trace_log
            ],
            use_container_width=True,
        )
        if st.button("Refrescar trace desde el backend"):
            try:
                refreshed = get_trace(BASE_URL, pipeline_result["rfp_id"])
                st.session_state["pipeline_result"]["trace_log"] = refreshed
                st.rerun()
            except BackendError as exc:
                st.warning(f"No se pudo refrescar el trace: {exc.detail}")
```

- [ ] **Step 2: Verify it parses and imports cleanly**

Run (from `algoworks-rfp-poc/frontend/`):
```bash
uv run python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read())"
uv run python -c "import app" --help 2>&1 | head -1 || true
```
The first command must succeed silently (valid Python syntax). Streamlit scripts aren't meant to be imported directly outside `streamlit run` (they'll try to access the script-run context), so don't worry about the second command's output — Step 3's manual run is the real check.

- [ ] **Step 3: Manual smoke test**

With the backend running (`uv run uvicorn api.main:app --reload --port 8000` from `algoworks-rfp-poc/backend/`), run from `algoworks-rfp-poc/frontend/`:

```bash
uv run streamlit run app.py
```

Click through and confirm:
- The header shows "🟢 Backend conectado".
- Selecting a sample RFP fills the textarea.
- Clicking "Procesar RFP" shows the spinner, then the metrics bar, path-audit banner, and per-requirement expander cards render with chunks, the highlighted draft, similarity bars, and the verdict.
- Clicking "Aceptar" on a card updates its expander title to show "✓ Aceptado" and doesn't clear the rest of the page.
- Expanding "Ver trace log completo" shows the trace table, and "Refrescar trace desde el backend" re-fetches it without error.
- Stopping the backend and reloading the page flips the header to "🔴 Backend no disponible…" and disables the "Procesar RFP" button.

- [ ] **Step 4: Commit**

```bash
git add algoworks-rfp-poc/frontend/app.py
git commit -m "feat: assemble the Streamlit explainability page"
```

---

## Self-Review Notes

- **Spec coverage:** framework/stack (Task 1), `api_client.py`'s full contract including the error-handling table (Tasks 2-4), `highlight_citations` (Task 5), sample RFP content and loader (Task 6), the complete page structure — header/health, input section, metrics bar, path-audit banner, per-requirement cards with chunks/draft/reasoning/similarity/verdict/accept-reject, raw trace log with manual refresh (Task 7) — all covered. Sub-projects B/C are explicitly out of scope per the spec and not addressed here.
- **Placeholder scan:** no `TBD`/`implement later` markers; every step has real, runnable code.
- **Type consistency checked:** `BackendError(error, detail)` constructor and `.error`/`.detail` attributes are used identically across Tasks 2-4 and in `app.py`'s `except BackendError as exc` blocks (Task 7); `check_health`/`process_rfp`/`get_trace`/`submit_feedback` signatures match between their definitions (Tasks 2-4) and their call sites in `app.py` (Task 7); `list_samples()`'s returned `dict[str, str]` (display name → text) matches how `app.py` builds `sample_names`/`default_text`; `highlight_citations(draft_text: str) -> str` matches its single call site in `app.py`.
