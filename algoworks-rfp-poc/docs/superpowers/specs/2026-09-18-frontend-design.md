# Frontend Design (Streamlit explainability UI)

> Companion to `docs/superpowers/specs/2026-09-18-traceability-metrics-design.md` (sub-project A, backend). This spec covers the frontend that consumes the full backend API — the base 4 endpoints (CLAUDE.md §5) plus the traceability fields sub-project A adds to `PipelineResult` — and turns them into the demo the hackathon judges see. Nothing about the frontend existed before this spec (`frontend/` is an empty placeholder directory).

## 1. Problem

CLAUDE.md §3 assigns the frontend one paragraph: "UI que consume la API, muestra el panel de explicabilidad (chunks + score + justificación + borrador citado + veredicto del verificador) y permite aceptar/rechazar cada sección (human-in-the-loop)." §6 leaves the framework open. Neither says how to structure the page, how much of sub-project A's new data (per-draft reasoning, grounding similarity, the reasoning-path audit, pipeline metrics) to surface, how the human-in-the-loop flow should feel given the backend doesn't persist feedback, or how the user gets an RFP into the pipeline in the first place. This spec makes all of those decisions concrete.

## 2. Goals / Non-goals

**Goals:**
- A single-page Streamlit app that drives `POST /rfp/process` and renders the full `PipelineResult`, including sub-project A's traceability fields — the hackathon is scored specifically on trazabilidad/explicabilidad (CLAUDE.md §1), so the UI should not under-show data the backend already computes.
- A believable human-in-the-loop accept/reject interaction per requirement section, even though `POST /{req_id}/feedback` doesn't persist anything server-side today.
- A demo-ready path: a sample-RFP picker so the person driving the demo doesn't need to type a convincing RFP live.
- A thin, testable `api_client.py` boundary between Streamlit UI code and the backend HTTP contract.

**Explicitly out of scope for this spec** (queued elsewhere, per `docs/superpowers/specs/2026-09-18-traceability-metrics-design.md` §7 and root `CLAUDE.md`'s sub-project list):
- Sub-project B: the "neural network"-style RAG/requirement/draft visualization.
- Sub-project C: SSE streaming of pipeline progress (`POST /rfp/process/stream`). This frontend calls the existing synchronous `POST /rfp/process` and blocks (with a spinner) until it returns.
- Any backend change. This spec treats the API contract (`docs/CONTRATO_DATOS.md`, to be regenerated alongside the backend plan's Task 4 schema change) as fixed and external.
- Persisting feedback, user accounts, multi-user session handling, or deployment/hosting concerns — this is a local demo app (`streamlit run`), not a shipped product.

## 3. Stack

- **Framework:** Streamlit (confirmed over React/Next — solo hackathon build, Python-only keeps context-switching down, and CLAUDE.md §6 names it as the default).
- **Dependency management:** `uv`, mirroring `backend/`'s existing convention (`frontend/pyproject.toml` + `frontend/uv.lock`), so the repo doesn't gain a second dependency-management tool. Dependencies: `streamlit`, `requests`, plus `pytest`/`responses` for the one test file.
- **HTTP:** plain `requests` against the FastAPI backend (`http://localhost:8000` by default, overridable via `BACKEND_URL` env var or `.streamlit/secrets.toml`). No GraphQL/websocket layer — matches the backend's plain REST + CORS-open setup (CLAUDE.md §5).
- The frontend does **not** import `backend/api/schemas.py` — it's a separate Python project/venv with no reason to depend on the backend package. The JSON contract is consumed as plain `dict`s; `docs/CONTRATO_DATOS.md` is the shared reference both sides read, not shared code.

## 4. File structure

```
algoworks-rfp-poc/
├── frontend/
│   ├── pyproject.toml         # NEW — streamlit, requests, pytest, responses
│   ├── app.py                 # NEW — page layout, orchestrates the sections below
│   ├── api_client.py          # NEW — thin wrapper around the 4 backend endpoints
│   ├── sample_rfps.py         # NEW — lists/loads canned RFP texts from data/sample_rfps/
│   ├── rendering.py           # NEW — pure helper functions that turn PipelineResult dicts into display-ready strings/tables (citation-marker highlighting, metric formatting)
│   └── tests/
│       └── test_api_client.py # NEW — api_client.py's parsing/error-handling logic, HTTP mocked
└── data/
    └── sample_rfps/
        ├── rfp_experiencia_arquitectura.txt   # NEW — happy-path-shaped sample
        └── rfp_sla_no_respaldado.txt          # NEW — shaped to plausibly trigger an unsupported verdict
```

`app.py` stays orchestration-only (widget layout + session-state wiring); anything that transforms data without touching Streamlit widgets lives in `rendering.py` so it's unit-testable without a Streamlit test harness. `api_client.py` is the only module that imports `requests`.

## 5. Page structure

Single page, top to bottom, no tabs (avoids Streamlit's more fragile multi-page/tab state handling for a solo build):

1. **Header** — app title; a small status indicator calls `GET /health` on every rerun (cheap enough not to bother caching) and shows a green "Backend conectado" or red "Backend no disponible en `<url>`" dot. When red, the input form below is disabled (`st.button(..., disabled=True)`) with a caption explaining why, instead of letting the user hit a raw exception on submit.
2. **Input section** — always visible:
   - `st.selectbox` "RFP de ejemplo" listing the files in `data/sample_rfps/` (via `sample_rfps.list_samples()`) plus a "— texto libre —" option; selecting a sample pre-fills the textarea below (does not lock it — the user can still edit).
   - `st.text_area` for the RFP text, pre-filled per the above.
   - `st.text_input` for `rfp_id`, defaulting to `f"rfp_{uuid4().hex[:8]}"` (regenerated each time the page first loads, editable).
   - `st.button("Procesar RFP")` — on click, wrapped in `st.spinner("Procesando RFP… (puede tardar hasta un minuto)")`, calls `api_client.process_rfp(rfp_id, rfp_text)` and stores the result in `st.session_state["pipeline_result"]`; also resets `st.session_state["feedback"] = {}` for the new result.
3. **Results section** — renders only when `st.session_state.get("pipeline_result")` is set:
   - **Metrics bar** — `st.columns(5)`, one `st.metric` each for: duration (ms → formatted as "1.2 s"), total tokens, estimated cost (USD, 4 decimals), retries used, hallucinated citations caught — straight from `PipelineResult.metrics`.
   - **Path audit banner** — `st.success("✓ Camino de ejecución consistente")` when `reasoning_path_audit.is_consistent`, else `st.error("✗ N problema(s) detectado(s) en el camino de ejecución")` followed by each `issues` entry as a bullet. Placed right under the metrics bar, above the per-requirement cards, since it's the "independent second opinion" the whole spec is built around (traceability spec §1) and shouldn't be buried in a per-card expander.
   - **Per-requirement cards** — one `st.expander(f"{requirement.section_target} — {requirement.text[:80]}…")` per `Requirement`, expanded by default only for the first one (subsequent ones collapsed, so the page doesn't turn into an unreadable wall for RFPs with many requirements). Each card renders, top to bottom:
     - Requirement text (full) and `section_target` as a small colored `st.badge`-style caption.
     - Retrieved chunks: `st.dataframe` with columns `chunk_id`, `score`, `justification`, sorted by score descending (already the order the API returns them in).
     - The draft: `st.markdown(rendering.highlight_citations(draft.text))`, where `highlight_citations` regex-replaces `[[chunk_id]]` with `**[chunk_id]**` (bold, no custom HTML component — a real hover tooltip needs a custom Streamlit component, which is out of scope for the time budget) so citations are visually distinguishable and cross-referenceable against the chunks table above.
     - The draft's `reasoning` text, in a `st.caption` styled block introduced as "Por qué el modelo citó estos fragmentos:".
     - Grounding: for each `citation_similarities` entry, a small inline `st.progress(similarity)` bar labeled with `chunk_id`; `overall_similarity` shown as a bold summary number above them.
     - Verifier verdict: `st.success`/`st.error` (by `supported`) showing `confidence`, `retries_used`, `reasoning`, and each `issues` entry as a bullet.
     - Accept/Reject: two `st.button`s side by side. Clicking either calls `api_client.submit_feedback(req_id, accepted)` and sets `st.session_state["feedback"][req_id] = accepted`; the card's title row shows a "✓ Aceptado" / "✗ Rechazado" badge once `feedback` has an entry for that `req_id`, styled distinctly from the verifier's own supported/unsupported badge so the two concepts (LLM verdict vs. human decision) are never visually conflated.
   - **Raw trace log** — one more `st.expander("Ver trace log completo (trazabilidad técnica)", expanded=False)` at the very bottom, containing `st.dataframe` of `trace_log` (columns: node, duration_ms, tokens.total_tokens, reasoning) — for a "look, I can also pull the raw execution trace" demo beat, and usable as a stand-in for exercising `GET /rfp/{id}/trace` directly (a "Refrescar trace" button inside this expander re-fetches via that endpoint instead of reusing the value embedded in the original `POST /rfp/process` response, so the demo can show that endpoint working independently).

## 6. `api_client.py` contract

```python
def check_health(base_url: str) -> bool: ...
def process_rfp(base_url: str, rfp_id: str, rfp_text: str, timeout: float = 120.0) -> dict: ...
def get_trace(base_url: str, rfp_id: str, timeout: float = 10.0) -> list[dict]: ...
def submit_feedback(base_url: str, req_id: str, accepted: bool, timeout: float = 10.0) -> dict: ...

class BackendError(Exception):
    """Raised with the parsed {"error", "detail"} body, or a synthesized
    one for network/timeout failures that never reached the backend."""
```

- `check_health` returns `False` on any exception (connection refused, timeout) rather than raising — the header status indicator is best-effort by design.
- `process_rfp`/`get_trace`/`submit_feedback` raise `BackendError` on any non-2xx response (parsing the standard `{"error", "detail"}` body when present, or synthesizing `{"error": "Connection Error", "detail": str(exc)}` for `requests.exceptions.RequestException`/`Timeout`) — `app.py` catches `BackendError` at each call site and renders `st.error(exc.detail)` without losing whatever was already on the page (a failed `submit_feedback` call, e.g., must not clear the already-rendered `pipeline_result`).
- No retries inside `api_client.py` — a failed call surfaces immediately; the user re-clicks if they want to try again. Matches the reduced-scope philosophy: this is a demo app, not production HTTP-resilience code.

## 7. Sample RFP content

Two files under `data/sample_rfps/` (plain `.txt`, numbered-line format so they also exercise `extract_requirements`'s no-LLM fallback path if needed):

- `rfp_experiencia_arquitectura.txt` — mirrors the two requirements already used as the backend's own manual-check example (CLAUDE.md-adjacent: experiencia previa en integración de datos + arquitectura para datos en tiempo real) — chosen because the dummy corpus (`data/knowledge_base/dummy_chunks.json`, backend plan Task 1) has directly relevant chunks for both, so it's likely to produce a clean "supported" demo path.
- `rfp_sla_no_respaldado.txt` — a requirement asking for a specific numeric SLA/guarantee (e.g., "garantía de latencia end-to-end menor a 50ms") that no chunk in the dummy corpus actually states — shaped to plausibly trigger the generator citing a real chunk about the right topic (Kafka/streaming) without real support for the specific number, giving the verifier a real chance to catch an unsupported claim for the demo's adversarial beat. This is a plausibility bet on LLM behavior, not a deterministic test fixture — `data/eval_cases/` (backend-owned) remains the actual adversarial test case; this sample is only for the live demo narrative.

`sample_rfps.list_samples() -> dict[str, str]` reads both files once (module-level, no caching layer needed for 2 files) and returns `{display_name: file_text}`, keyed off a human-readable name derived from the filename.

## 8. Error handling summary

| Scenario | Behavior |
|---|---|
| `GET /health` unreachable on page load | Red status dot; input form disabled with an explanatory caption. |
| `POST /rfp/process` times out or backend down | `st.error` with the connection error detail; previous `pipeline_result` (if any) stays rendered. |
| `POST /rfp/process` returns 4xx/5xx | `st.error(detail)` from the standard error shape; no partial result is stored. |
| `POST /{req_id}/feedback` fails | Inline `st.warning` on that card only; does not clear `pipeline_result` or other cards' feedback state. |
| `GET /rfp/{id}/trace` (manual refresh) fails | Inline `st.warning` inside the trace expander only. |

## 9. Testing scope

Matching the reduced-scope philosophy already applied to the backend (traceability spec §6): Streamlit widget/layout code has poor unit-test ROI (mostly wiring, no meaningful assertions on rendered output without a heavier test harness this hackathon doesn't have time for). So:

**Covered with tests** (`frontend/tests/test_api_client.py`, HTTP mocked via `responses`, no network):
- `process_rfp`/`get_trace`/`submit_feedback` return parsed JSON on 200.
- Each raises `BackendError` with the right `.detail` on a 404/422/500 matching the standard error shape.
- `check_health` returns `True`/`False` correctly, including on a simulated `ConnectionError`.
- `rendering.highlight_citations` — pure function, easy to assert on: input with multiple `[[chunk_id]]` markers → expected bolded output, and a no-citation string passes through unchanged.

**Deliberately skipped** (manual smoke test instead, once before calling the frontend done): actual `app.py` widget rendering, layout correctness, and the full click-through flow (start backend, `streamlit run app.py`, pick a sample RFP, process it, expand a card, click Accept, confirm the badge appears, expand the trace log). This manual pass is the frontend's equivalent of the backend plan's "Post-implementation manual check."

## 10. Follow-up (not designed here)

- **Sub-project B** (RAG/requirement/draft visualization) would likely replace or augment the per-requirement `st.expander` list with a dedicated view once it has its own spec — this frontend's `PipelineResult`-consuming structure is meant to accommodate that without a rewrite (the retrieved/drafts/verification data is already parsed into plain dicts in `app.py`, not locked into the card-rendering code path).
- **Sub-project C** (SSE streaming) would change `api_client.process_rfp` from a single blocking call into a streaming consumer feeding incremental `st.status`/`st.write_stream` updates instead of one `st.spinner` — flagged here so a future spec knows where the seam is, not designed now.
