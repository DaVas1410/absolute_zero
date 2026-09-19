# Traceability Metrics & Grounding Design (Sub-project A)

> Extends the backend RFP pipeline (`extract_requirements → retrieve_chunks → generate_draft → verify_citations`, already specced in `algoworks-rfp-poc/CLAUDE.md` and planned in `docs/superpowers/plans/2026-09-18-backend-rfp-pipeline.md`) with explainability data for the hackathon demo: per-node metrics, explicit LLM reasoning, RAG grounding scores, and a deterministic execution-path audit.

## 1. Problem

The base pipeline (already specced, not yet implemented) produces a `PipelineResult` with drafts, citations and a pass/fail verdict per requirement, but doesn't expose *how confident we should be* in that verdict beyond the LLM's own yes/no. For the hackathon pitch we need to show, quantitatively and narratively:

- How long each step took and how much it cost (tokens).
- How many times the system had to retry itself, and how often it caught its own hallucinated citations.
- Whether the generated text is actually semantically close to the chunks it cites (independent of whether the LLM *says* it's supported).
- An independent, non-LLM audit confirming the graph's execution actually followed the rules we designed (retry limits, citation existence) — a second opinion that isn't "trust the LLM."

## 2. Goals / Non-goals

**Goals (this spec):**
- Extend the data contract (additively) with reasoning, similarity, and metrics fields.
- Capture LLM chain-of-thought for `generate_draft` and `verify_citations` via structured output (not free-text parsing, per CLAUDE.md §7).
- Compute cosine similarity between generated drafts and the RAG chunks they cite, at both per-citation and per-draft granularity.
- Add a deterministic (no-LLM) audit of the graph's execution path.
- Instrument per-node latency and best-effort token/cost tracking.

**Explicitly out of scope for this spec** (queued as their own future specs, since they consume this spec's output):
- **Sub-project B**: a "neural network" style visualization of RAG/requirement/draft connections for the presentation.
- **Sub-project C**: real-time streaming (SSE) of pipeline progress to the frontend.
- Any change to `POST /rfp/process`'s request shape or the other 3 existing endpoints.
- LLM provider choice: unchanged from CLAUDE.md §6 — **Groq primary (Llama 3.3 70B for generation/verification, a smaller/faster Groq model for extraction/retrieval), Ollama local as offline fallback.** Confirmed during brainstorming: Groq's speed/quality (needed for a convincing adversarial-citation catch, CLAUDE.md §3) outweighs the offline-only alternative for a venue that will have wifi; the Ollama fallback already covers the connectivity-risk case without giving up quality.

## 3. Data contract changes (`backend/api/schemas.py`)

All changes are additive — no existing field is renamed, retyped, or removed, so existing frontend code that only reads today's fields keeps working unchanged.

**New models:**

```python
class CitationSimilarity(BaseModel):
    chunk_id: str
    similarity: float  # cosine similarity, citation text embedding <-> chunk embedding

class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0  # best-effort; 0.0 means "unknown", not "free"

class PipelineMetrics(BaseModel):
    total_duration_ms: float
    total_tokens: TokenUsage
    retries_used: int
    requirements_supported: int
    requirements_needing_review: int
    hallucinated_citations_caught: int

class ReasoningPathAudit(BaseModel):
    is_consistent: bool
    node_sequence: list[str]
    issues: list[str]  # empty when is_consistent is True
```

**New fields on existing models:**

| Model | New field | Default | Set by |
|---|---|---|---|
| `DraftSection` | `reasoning: str` | `""` | `generate_draft` |
| `DraftSection` | `citation_similarities: list[CitationSimilarity]` | `[]` | `compute_traceability_metrics` |
| `DraftSection` | `overall_similarity: float` | `0.0` | `compute_traceability_metrics` |
| `VerificationResult` | `reasoning: str` | `""` | `verify_citations` |
| `VerificationResult` | `retries_used: int` | `0` | `verify_citations` |
| `TraceEvent` | `duration_ms: float` | `0.0` | every node |
| `TraceEvent` | `tokens: TokenUsage \| None` | `None` | every node (None = no LLM call made) |
| `PipelineResult` | `metrics: PipelineMetrics` | *(required)* | `compute_traceability_metrics` |
| `PipelineResult` | `reasoning_path_audit: ReasoningPathAudit` | *(required)* | `compute_traceability_metrics` |

`metrics` and `reasoning_path_audit` have no default because a real `PipelineResult` always has them — they're produced by the last node before the graph ends.

## 4. Node changes

### 4.1 `generate_draft` — plain text → structured output

Currently calls `llm.invoke(prompt).content`. Changes to structured output to comply with CLAUDE.md §7 ("never hand-parse free text when structured output is feasible") and to get an explicit reasoning field:

```python
class _DraftOutput(BaseModel):
    draft_text: str
    reasoning: str
```

The node calls `invoke_structured_tracked(llm, _DraftOutput, prompt, accumulator)` (see §5), then runs the existing citation-existence post-processing against `.draft_text` exactly as already specced, and stores `.reasoning` on `DraftSection.reasoning`.

### 4.2 `verify_citations` — add `reasoning`, `retries_used`

`_NliVerdict` gains a `reasoning: str` field:

```python
class _NliVerdict(BaseModel):
    supported: bool
    issues: list[str]
    confidence: float
    reasoning: str
```

- When a requirement is auto-marked unsupported because of hallucinated citations (no LLM call made), `VerificationResult.reasoning` is set to a fixed deterministic string: `"No se llamó al LLM de verificación: se detectaron citas a chunk_id inexistentes antes de esta etapa."`
- `VerificationResult.retries_used` is set to `retry_counts.get(req_id, 0)` **before** this node potentially increments it for a further retry — i.e. it records how many retries had already happened *leading up to* this verdict (0 for a first-pass verdict, 1 for a verdict produced after one retry).

### 4.3 New node — `compute_traceability_metrics`

Runs **once**, after the retry loop settles (`pending_req_ids` empty), before `END`. No LLM calls — pure code + the embeddings model. Factory: `make_compute_traceability_metrics_node(embeddings)`.

For each `req_id` with a `DraftSection`:
1. Embed the full `draft.text` once (`embeddings.embed_query`).
2. For each `chunk_id` in `draft.cited_chunks` that exists in `state["retrieved"][req_id]`: embed that chunk's text and compute `cosine_similarity(draft_embedding, chunk_embedding)` → append a `CitationSimilarity`.
3. `overall_similarity` = cosine similarity between the draft embedding and the **mean of the cited chunks' embeddings** (component-wise average, then re-normalized for the cosine calc). If there are no valid cited chunks, `citation_similarities = []` and `overall_similarity = 0.0`.
4. Build updated `DraftSection` objects via `draft.model_copy(update={...})` (Pydantic objects are immutable-by-convention here — always copy, never mutate in place).

`cosine_similarity(a: list[float], b: list[float]) -> float` is a small pure function living in this node's module (no new file needed — it has exactly one caller).

**Path audit** — `audit_reasoning_path(state) -> ReasoningPathAudit`, pure function, checks:
1. `node_sequence = [event.node for event in state["trace_log"]]` follows a valid path: starts `extract_requirements`, `retrieve_chunks`, then one or more `(generate_draft, verify_citations)` pairs, ending at `verify_citations` (this node's own event isn't in the sequence being audited — it appends its own event *after* running the audit). Any other shape is an issue.
2. Every `retry_counts[req_id] <= MAX_GENERATE_RETRIES` (from `graph.state`).
3. Every `chunk_id` in every `DraftSection.cited_chunks` exists in `state["retrieved"][req_id]` — this re-checks, independently, something `generate_draft` already guarantees; that redundancy *is the point* of an independent audit (defense in depth, not "trust the node that already claims it validated this").
4. Every `req_id` present in `state["verification"]` is also present in `state["requirements"]`.
5. `is_consistent = len(issues) == 0`.

**Metrics aggregation** from the final state:
```python
total_duration_ms = sum(event.duration_ms for event in state["trace_log"])
total_tokens = TokenUsage(
    input_tokens=sum(e.tokens.input_tokens for e in state["trace_log"] if e.tokens),
    output_tokens=sum(e.tokens.output_tokens for e in state["trace_log"] if e.tokens),
    total_tokens=sum(e.tokens.total_tokens for e in state["trace_log"] if e.tokens),
    estimated_cost_usd=sum(e.tokens.estimated_cost_usd for e in state["trace_log"] if e.tokens),
)
retries_used = sum(state["retry_counts"].values())
requirements_supported = sum(1 for v in state["verification"].values() if v.supported)
requirements_needing_review = sum(1 for v in state["verification"].values() if not v.supported)
hallucinated_citations_caught = state["hallucination_catches"]
```

The node appends its own `TraceEvent` (`node="compute_traceability_metrics"`, `tokens=None` since it makes no LLM calls, `reasoning` summarizing the audit result and average similarity) — every node logs itself, no exceptions.

### 4.4 `hallucination_catches` — new internal `GraphState` field

`hallucinated_citations` (already specced) gets **overwritten** each time `generate_draft` reprocesses a `req_id` on retry, so it can't be used to count total hallucinations caught across the whole run. New internal-only counter: `hallucination_catches: int`, initialized to `0`, incremented by `generate_draft` on every pass by the number of hallucinated `chunk_id`s found in that pass (summed across all requirements processed in that pass, across all passes/retries). This is internal `GraphState`, not part of the public contract, so it's free to add without the "hard rule" contract-change concern.

### 4.5 Graph wiring change

`should_retry` (already specced) now routes to `"compute_traceability_metrics"` instead of `"__end__"` when `pending_req_ids` is empty:

```python
def should_retry(state: GraphState) -> str:
    return "generate_draft" if state["pending_req_ids"] else "compute_traceability_metrics"
```

`graph.py` adds `graph.add_node("compute_traceability_metrics", make_compute_traceability_metrics_node(embeddings))`, updates the conditional edge's `path_map` to `{"generate_draft": "generate_draft", "compute_traceability_metrics": "compute_traceability_metrics"}`, and adds `graph.add_edge("compute_traceability_metrics", END)`. `build_graph`/`run_pipeline` gain an `embeddings` parameter (the same `Embeddings` instance used to build the vectorstore), threaded through from `api/main.py`.

## 5. Instrumentation (`backend/graph/llm_tracking.py`, new file)

**Latency:** each node wraps its own body with `time.perf_counter()` and puts the elapsed milliseconds on its own `TraceEvent.duration_ms`. No shared helper needed for this half.

**Tokens/cost:**

```python
class TokenAccumulator:
    """Un acumulador por ejecución de nodo; se le van sumando las llamadas
    LLM que haga ese nodo, y al final se lee su total para el TraceEvent."""
    def add(self, usage: TokenUsage) -> None: ...
    def total(self) -> TokenUsage: ...

def invoke_tracked(llm, prompt: str, accumulator: TokenAccumulator) -> str:
    """Reemplaza llm.invoke(prompt).content.strip(). Extrae usage_metadata
    y response_metadata (si existen) del response, sino cuenta cero."""

def invoke_structured_tracked(llm, schema: type[BaseModel], prompt: str, accumulator: TokenAccumulator):
    """Llama llm.with_structured_output(schema, include_raw=True).invoke(prompt).
    Acumula tokens desde raw, relanza si parsing_error no es None, devuelve parsed."""

def estimate_cost_usd(model_name: str, usage: TokenUsage) -> float:
    """Tabla de precios chica y hardcodeada solo para los modelos Groq
    configurados (GROQ_MODEL_SMALL/GROQ_MODEL_LARGE). Cualquier otro
    model_name (Ollama, vacío, desconocido) devuelve 0.0."""
```

`invoke_tracked`/`invoke_structured_tracked` read `getattr(response, "usage_metadata", None)` and `getattr(response, "response_metadata", {})` defensively — the `ScriptedChatModel` test double doesn't set these, so tracked calls against it always accumulate zero usage without raising.

Every node (`extract_requirements`, `retrieve_chunks`, `generate_draft`, `verify_citations`) is updated to: create one `TokenAccumulator` at the top of its function body, route every LLM call through `invoke_tracked`/`invoke_structured_tracked`, and attach `accumulator.total()` to its `TraceEvent.tokens`.

## 6. Testing scope (deliberately reduced for hackathon time)

**Covered with tests** (pure logic or connectivity-risk logic — cheap, no network, high payoff if it breaks live):
- `should_retry` routing and the 1-retry limit.
- `generate_draft`'s hallucinated-citation detection.
- `compute_traceability_metrics`: cosine similarity math, the path audit (including at least one deliberately-broken state to prove `issues` gets populated), and metrics aggregation.
- `extract_requirements`'s no-LLM fallback (numbered-line split) — CLAUDE.md flags this as a real hackathon connectivity risk.
- `graph/llm.py`'s Groq→Ollama fallback-on-exception behavior — same reason.
- `graph/llm_tracking.py`: accumulator math and graceful handling of missing `usage_metadata`.
- `test_graph.py` end-to-end (happy path + one-retry-then-still-unsupported path) and `test_api.py` — these are what actually prove the demo responds correctly.

**Deliberately skipped** (trivial wiring, cheaper to eyeball once in the manual smoke test than to write/maintain a test for):
- `rag/corpus.py`, `rag/embed.py`, `graph/prompts/__init__.py` loaders.
- `get_chat_llm()`'s env-var/construction wiring (the fallback *behavior* is tested; the construction glue is not).
- Redundant happy-path variants of nodes that have no decision branch (e.g., don't write three near-identical happy-path tests for `retrieve_chunks`).

## 7. Follow-up specs (not designed here)

- **Sub-project B — "neural network" visualization**: needs its own brainstorming pass once this spec's fields (`citation_similarities`, `overall_similarity`, `reasoning_path_audit`) exist to visualize. Candidate cheap fallback if time runs out: a static Mermaid/SVG architecture diagram (pattern borrowed from reviewing `aniket-work/autonomous-rfp-agent`'s `scripts/generate_diagrams.py`) instead of a fully interactive graph.
- **Sub-project C — SSE streaming of pipeline progress**: needs its own brainstorming pass; likely a new `POST /rfp/process/stream` endpoint alongside (not replacing) `POST /rfp/process`, wrapping `compiled_graph.stream(...)`.

## 8. Impact on the existing implementation plan

`docs/superpowers/plans/2026-09-18-backend-rfp-pipeline.md` was written before this spec and does not yet reflect any of the above (it has not been executed — no code exists yet). It needs to be revised/replaced to account for: the new `compute_traceability_metrics` node and its graph wiring, the `_DraftOutput`/`_NliVerdict` structured-output changes, the new `graph/llm_tracking.py` module threaded through all 4 existing nodes, the extended schema fields, and the reduced testing scope from §6. This happens next, via the writing-plans skill.
