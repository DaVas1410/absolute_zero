# Backend RFP Pipeline (RAG + LangGraph + Traceability) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded mock in `backend/api/main.py` with a real, testable LangGraph pipeline (`extract_requirements → retrieve_chunks → generate_draft → verify_citations → compute_traceability_metrics`, with a conditional 1-retry loop from `verify_citations` back to `generate_draft`) backed by a local Chroma vectorstore over a small dummy corpus, Groq as the primary LLM with an Ollama local fallback, and full per-node explainability instrumentation (reasoning, RAG grounding similarity, a deterministic execution-path audit, and latency/token/cost metrics).

**Architecture:** Each graph node is a small pure-ish factory function `make_<node>_node(...) -> Callable[[GraphState], dict]` that reads from and returns partial updates to a shared `GraphState` TypedDict, so nodes can be unit-tested in isolation with fake LLM/vectorstore/embeddings doubles (no real network calls in the test suite). Every LLM call inside a node goes through `graph/llm_tracking.py`'s `invoke_tracked`/`invoke_structured_tracked` helpers, which extract token usage and estimate cost so every `TraceEvent` carries real (or honestly-zero) instrumentation. A final `compute_traceability_metrics` node runs once the retry loop settles: it computes cosine similarity between each draft and the chunks it cites, runs a non-LLM audit of the graph's own execution path, and aggregates pipeline-wide metrics. `backend/graph/graph.py` wires all 5 nodes into a compiled `StateGraph` and exposes `run_pipeline(...) -> PipelineResult`. `backend/api/main.py` gets a `get_pipeline_runner()` FastAPI dependency so the real pipeline is used in production and a fake is swapped in for tests via `app.dependency_overrides`.

**Tech Stack:** LangGraph (`langgraph` 1.2.11, already installed), `langchain-groq`, `langchain-ollama`, `langchain-chroma`, `sentence-transformers`, Pydantic v2, `pytest` + FastAPI `TestClient`. All package versions are already pinned in `backend/uv.lock` — no new dependencies needed.

**Spec:** `algoworks-rfp-poc/CLAUDE.md` (sections 2, 4, 6, 7, 8) and `docs/superpowers/specs/2026-09-18-traceability-metrics-design.md` (sub-project A — reasoning capture, grounding similarity, path audit, instrumentation). `algoworks-rfp-poc/backend/api/schemas.py` is the data contract this plan extends additively (do not rename/retype existing fields).

## Global Constraints

- Graph shape: `extract_requirements → retrieve_chunks → generate_draft → verify_citations → compute_traceability_metrics`, with a conditional edge from `verify_citations` back to `generate_draft`, **max. 1 retry per requirement** (CLAUDE.md §2; retry target updated to route to `compute_traceability_metrics` instead of `END` once the retry loop settles, per traceability spec §4.5).
- `extract_requirements` must use LLM structured output with `section_target` restricted to a closed enum, and must fall back to a no-LLM numbered-line split if structured output fails (CLAUDE.md §2).
- `retrieve_chunks` must use embeddings + cosine similarity over a local Chroma vectorstore, and generate a natural-language `justification` per candidate chunk via a second, short LLM prompt (CLAUDE.md §2).
- `generate_draft` must cite `[[chunk_id]]` inline per factual claim; code (not the LLM) must validate that every cited `chunk_id` actually exists among the retrieved chunks for that requirement — hallucinated IDs are an automatic citation error (CLAUDE.md §2). It uses structured output (`_DraftOutput`: `draft_text` + `reasoning`) instead of plain-text `.invoke` (traceability spec §4.1).
- `verify_citations` must check whether the cited chunk actually supports the claim (NLI-style yes/no + why); on failure it triggers the retry edge (max 1), otherwise the requirement is left flagged for human review via `supported: false` (CLAUDE.md §2). Its structured verdict (`_NliVerdict`) gains a `reasoning` field, and each `VerificationResult` records `retries_used` (traceability spec §4.2).
- **Every node must append its own `TraceEvent` to `trace_log`** — never deferred to the end (CLAUDE.md §2, §7) — and that `TraceEvent` must carry real `duration_ms` (wall-clock via `time.perf_counter()`) and `tokens` (via the shared tracking helpers; `None` only for nodes that make no LLM calls, i.e. `compute_traceability_metrics`) (traceability spec §5).
- `compute_traceability_metrics` runs once, after the retry loop settles, makes no LLM calls, and: (1) computes cosine similarity between each draft and the chunks it cites (per-citation and overall), (2) runs a deterministic audit of the graph's own execution path (`audit_reasoning_path`), (3) aggregates pipeline-wide `PipelineMetrics` (traceability spec §4.3).
- All structured LLM output uses `.with_structured_output(schema, include_raw=True)` via `invoke_structured_tracked` — never hand-parsed free text when it can be avoided (CLAUDE.md §7; `include_raw=True` per traceability spec §5, needed to recover token usage alongside the parsed object).
- Prompts are versioned as `.txt` files under `backend/graph/prompts/`, never hardcoded inline in node code (CLAUDE.md §7).
- Variable/function names in English; docstrings/comments in Spanish are fine (CLAUDE.md §7).
- LLM stack: Groq for `generate_draft`/`verify_citations` (larger model) and a smaller/faster Groq model for `extract_requirements`/`retrieve_chunks`; Ollama local as offline fallback if Groq connectivity fails (CLAUDE.md §6). Confirmed unchanged during traceability-spec brainstorming (traceability spec §2).
- `backend/api/schemas.py` is the frozen data contract — **do not change existing field names or types**; every schema addition in this plan is purely additive (new models, new fields with defaults, except `PipelineResult.metrics`/`reasoning_path_audit` which are required since a real result always has them) (CLAUDE.md §4; traceability spec §3).
- **Schema/state gap this plan resolves:** the traceability spec's `compute_traceability_metrics` step 2 says to "embed that chunk's text," but `RetrievedChunk` (the only per-chunk record carried in `GraphState["retrieved"]`) has no `text` field — only `chunk_id`, `score`, `justification`. Embedding the LLM-written `justification` instead of the actual source text would measure similarity against commentary, not grounding, defeating the point of an independent check. This plan resolves it by threading a plain `chunk_texts_by_id: dict[str, str]` lookup (built once from `load_dummy_chunks()`, chunk_id → `Chunk.text`) into `compute_traceability_metrics` alongside `embeddings` — a node-construction parameter, not a new `GraphState` field or schema model, so it doesn't touch the frozen contract.
- Backend starts with its own small dummy corpus (3-5 chunks) instead of blocking on real data (CLAUDE.md §8).
- Don't automate more than the one concrete flow described above; no real/legal documents anywhere (CLAUDE.md §8).
- Testing scope is deliberately reduced for hackathon time (traceability spec §6): cover pure logic and connectivity-risk logic (retry/routing limits, hallucination detection, the no-LLM fallback, the Groq→Ollama fallback, cosine similarity + path audit + metrics aggregation, the token-tracking accumulator, end-to-end graph + API tests). Skip tests for trivial wiring/loaders (`rag/corpus.py`, `rag/embed.py`, `graph/prompts/__init__.py`, `get_chat_llm()`'s construction glue) and redundant happy-path variants of nodes with no decision branch.

---

## File Structure

```
algoworks-rfp-poc/
├── backend/
│   ├── rag/
│   │   ├── corpus.py          # NEW — loads the dummy Chunk corpus from data/knowledge_base/
│   │   ├── embed.py           # MODIFY (currently a stub) — SentenceTransformerEmbeddings
│   │   └── store.py           # MODIFY (currently a stub) — Chroma build + similarity_search
│   ├── graph/
│   │   ├── state.py           # MODIFY (currently a stub) — GraphState TypedDict + MAX_GENERATE_RETRIES
│   │   ├── llm.py             # NEW — FallbackChatModel + get_chat_llm()
│   │   ├── llm_tracking.py    # NEW — TokenAccumulator, invoke_tracked, invoke_structured_tracked, estimate_cost_usd
│   │   ├── graph.py           # MODIFY (currently a stub) — build_graph() + run_pipeline()
│   │   ├── prompts/
│   │   │   ├── __init__.py            # NEW — load_prompt()
│   │   │   ├── extract_requirements.txt      # NEW
│   │   │   ├── retrieve_chunks_justification.txt  # NEW
│   │   │   ├── generate_draft.txt            # NEW
│   │   │   └── verify_citations.txt          # NEW
│   │   └── nodes/
│   │       ├── extract_requirements.py           # NEW
│   │       ├── retrieve_chunks.py                # NEW
│   │       ├── generate_draft.py                 # NEW
│   │       ├── verify_citations.py               # NEW
│   │       └── compute_traceability_metrics.py   # NEW
│   ├── api/
│   │   ├── schemas.py          # MODIFY — additive traceability fields/models
│   │   └── main.py             # MODIFY — replace the hardcoded mock with the real pipeline
│   └── tests/
│       ├── fakes.py            # NEW — shared test doubles (FakeEmbeddings, ScriptedChatModel, FakeVectorstore)
│       ├── test_schemas.py     # MODIFY — cover new fields/models and their defaults
│       ├── test_corpus.py      # NEW
│       ├── test_embed.py       # NEW
│       ├── test_store.py       # NEW
│       ├── test_prompts.py     # NEW
│       ├── test_llm_tracking.py               # NEW
│       ├── test_node_extract_requirements.py  # NEW
│       ├── test_node_retrieve_chunks.py       # NEW
│       ├── test_node_generate_draft.py        # NEW
│       ├── test_node_verify_citations.py      # NEW
│       ├── test_node_compute_traceability_metrics.py  # NEW
│       ├── test_graph.py      # NEW
│       ├── test_llm.py        # NEW
│       └── test_api.py        # MODIFY — dependency-override the real pipeline runner
└── data/
    └── knowledge_base/
        └── dummy_chunks.json  # NEW — 5 fictitious Chunk records
```

All new test files live in `backend/tests/` (flat, matching the existing `test_schemas.py`/`test_api.py` layout — `pythonpath = ["."]` is already configured in `backend/pyproject.toml`, so `from api...`, `from graph...`, `from rag...` imports work from any test file without extra path setup).

---

## Task 1: Dummy knowledge base corpus + loader

**Files:**
- Create: `algoworks-rfp-poc/data/knowledge_base/dummy_chunks.json`
- Create: `algoworks-rfp-poc/backend/rag/corpus.py`
- Test: `algoworks-rfp-poc/backend/tests/test_corpus.py`

**Interfaces:**
- Produces: `load_dummy_chunks(path: pathlib.Path = DEFAULT_CORPUS_PATH) -> list[Chunk]` (from `rag.corpus`), used by Task 15 (`api/main.py`) both for the vectorstore and for the `chunk_texts_by_id` lookup that `compute_traceability_metrics` needs (Task 12).

- [ ] **Step 1: Write the dummy corpus data file**

Create `algoworks-rfp-poc/data/knowledge_base/dummy_chunks.json`:

```json
[
  {
    "chunk_id": "chunk_001",
    "text": "Algoworks lideró la integración de datos entre 6 sistemas ERP y un data warehouse central para un cliente de manufactura, procesando 2.3M de registros mensuales en un proyecto de 4 meses.",
    "source": "Propuesta_ClienteManufactura_2023.md",
    "section_type": "experiencia_previa",
    "metadata": {"anio": 2023}
  },
  {
    "chunk_id": "chunk_002",
    "text": "En 2022, Algoworks desarrolló una plataforma de sincronización de inventario en tiempo real para una cadena de retail con 40 tiendas, reduciendo discrepancias de stock en un 87%.",
    "source": "Propuesta_ClienteRetail_2022.md",
    "section_type": "experiencia_previa",
    "metadata": {"anio": 2022}
  },
  {
    "chunk_id": "chunk_003",
    "text": "Algoworks migró un data lake on-premise de 8TB a una arquitectura cloud (Azure Data Lake) para un cliente de logística, sin downtime durante el corte de producción.",
    "source": "Propuesta_ClienteLogistica_2021.md",
    "section_type": "experiencia_previa",
    "metadata": {"anio": 2021}
  },
  {
    "chunk_id": "chunk_004",
    "text": "La arquitectura de referencia de Algoworks para integración de datos en tiempo real usa Apache Kafka como bus de eventos y Spark Structured Streaming para el procesamiento, con checkpoints para garantizar entrega exactly-once.",
    "source": "Capacidades_Tecnicas_Algoworks.md",
    "section_type": "capacidades_tecnicas",
    "metadata": {}
  },
  {
    "chunk_id": "chunk_005",
    "text": "El equipo de datos de Algoworks incluye 3 ingenieros certificados en Confluent Kafka y 2 certificados en Databricks, con un promedio de 5 años de experiencia en plataformas de streaming.",
    "source": "Equipo_Algoworks.md",
    "section_type": "equipo",
    "metadata": {}
  }
]
```

- [ ] **Step 2: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_corpus.py`:

```python
"""Tests del loader de la corpus dummy de conocimiento."""

from api.schemas import Chunk
from rag.corpus import load_dummy_chunks


def test_load_dummy_chunks_returns_valid_unique_chunks():
    chunks = load_dummy_chunks()

    assert len(chunks) >= 3
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_load_dummy_chunks_covers_multiple_section_types():
    chunks = load_dummy_chunks()

    section_types = {chunk.section_type for chunk in chunks}
    assert len(section_types) >= 2
```

- [ ] **Step 3: Run test to verify it fails**

Run (from `algoworks-rfp-poc/backend/`): `uv run pytest tests/test_corpus.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.corpus'`

- [ ] **Step 4: Write minimal implementation**

Create `algoworks-rfp-poc/backend/rag/corpus.py`:

```python
"""Carga la corpus dummy de conocimiento (CLAUDE.md, sección 8: backend
arranca con sus propios chunks dummy, sin bloquear por datos reales).
"""

import json
from pathlib import Path

from api.schemas import Chunk

DEFAULT_CORPUS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "knowledge_base" / "dummy_chunks.json"
)


def load_dummy_chunks(path: Path = DEFAULT_CORPUS_PATH) -> list[Chunk]:
    raw_chunks = json.loads(path.read_text(encoding="utf-8"))
    return [Chunk.model_validate(item) for item in raw_chunks]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_corpus.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add algoworks-rfp-poc/data/knowledge_base/dummy_chunks.json algoworks-rfp-poc/backend/rag/corpus.py algoworks-rfp-poc/backend/tests/test_corpus.py
git commit -m "feat: add dummy knowledge base corpus and loader"
```

---

## Task 2: Embeddings wrapper (sentence-transformers)

**Files:**
- Modify: `algoworks-rfp-poc/backend/rag/embed.py`
- Test: `algoworks-rfp-poc/backend/tests/test_embed.py`

**Interfaces:**
- Produces: `SentenceTransformerEmbeddings(model_name: str = DEFAULT_MODEL_NAME)` implementing `langchain_core.embeddings.Embeddings` (`embed_documents`, `embed_query`), used by Task 15 (`api/main.py`) for the real vectorstore AND the real `compute_traceability_metrics` node. NOT used in any other task's tests (those use the `FakeEmbeddings` double from Task 3 to stay hermetic and fast).

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_embed.py`:

```python
"""Test de integración liviano del wrapper de embeddings. Descarga el
modelo sentence-transformers la primera vez que corre (requiere red o
caché local de HuggingFace); las demás pruebas de RAG usan FakeEmbeddings
para no depender de esto.
"""

from rag.embed import SentenceTransformerEmbeddings


def test_embed_documents_and_query_return_same_dimensionality():
    embeddings = SentenceTransformerEmbeddings()

    doc_vectors = embeddings.embed_documents(["hola mundo", "otro texto de prueba"])
    query_vector = embeddings.embed_query("hola mundo")

    assert len(doc_vectors) == 2
    assert len(doc_vectors[0]) > 0
    assert len(doc_vectors[0]) == len(doc_vectors[1]) == len(query_vector)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_embed.py -v`
Expected: FAIL — `rag/embed.py` currently has no `SentenceTransformerEmbeddings` class (only a placeholder docstring), so this is an `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Replace the contents of `algoworks-rfp-poc/backend/rag/embed.py`:

```python
"""Wrapper de embeddings con sentence-transformers, con la interfaz
Embeddings de LangChain para poder usarse directamente con Chroma.
"""

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(list(texts), convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode([text], convert_to_numpy=True)[0].tolist()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_embed.py -v`
Expected: PASS (first run may take longer while the model downloads/caches).

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/rag/embed.py algoworks-rfp-poc/backend/tests/test_embed.py
git commit -m "feat: implement sentence-transformers embeddings wrapper"
```

---

## Task 3: Chroma vectorstore + shared test fakes

**Files:**
- Modify: `algoworks-rfp-poc/backend/rag/store.py`
- Create: `algoworks-rfp-poc/backend/tests/fakes.py`
- Test: `algoworks-rfp-poc/backend/tests/test_store.py`

**Interfaces:**
- Consumes: `Chunk` (from `api.schemas`).
- Produces: `build_vectorstore(chunks: list[Chunk], embeddings: Embeddings, persist_directory: str | None = None) -> Chroma` and `similarity_search(vectorstore: Chroma, query: str, k: int) -> list[tuple[str, str, float]]` (chunk_id, text, score), used by Task 9 (`retrieve_chunks` node) and Task 15 (`api/main.py`).
- Produces (test double, `tests/fakes.py`): `FakeEmbeddings(vocabulary: list[str])` — deterministic bag-of-words embedding for hermetic tests. This file will be extended by Tasks 8, 9 and 12 with more fakes.

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/fakes.py`:

```python
"""Dobles de prueba compartidos por los tests del backend (RAG y nodos del
grafo), para no depender de red ni de modelos reales en la suite.
"""

from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    """Embeddings deterministas basados en presencia de palabras clave:
    dos textos son 'similares' si comparten más palabras del vocabulario.
    """

    def __init__(self, vocabulary: list[str]):
        self._vocabulary = vocabulary

    def _vectorize(self, text: str) -> list[float]:
        lowered = text.lower()
        return [float(word in lowered) for word in self._vocabulary]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectorize(text)
```

Create `algoworks-rfp-poc/backend/tests/test_store.py`:

```python
"""Tests del vectorstore local (Chroma) sobre un corpus pequeño y
embeddings deterministas (FakeEmbeddings), sin red ni modelos reales.
"""

from api.schemas import Chunk
from rag.store import build_vectorstore, similarity_search
from tests.fakes import FakeEmbeddings

VOCABULARY = ["kafka", "retail", "manufactura", "logistica"]


def _sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id="chunk_kafka",
            text="Arquitectura basada en Kafka para streaming de datos.",
            source="doc_a.md",
            section_type="capacidades_tecnicas",
        ),
        Chunk(
            chunk_id="chunk_retail",
            text="Proyecto de sincronización de inventario para retail.",
            source="doc_b.md",
            section_type="experiencia_previa",
        ),
    ]


def test_similarity_search_returns_most_relevant_chunk_first():
    vectorstore = build_vectorstore(_sample_chunks(), FakeEmbeddings(VOCABULARY))

    results = similarity_search(vectorstore, "Necesitamos experiencia en retail", k=2)

    assert results[0][0] == "chunk_retail"
    assert len(results) == 2
    assert all(isinstance(score, float) for _, _, score in results)


def test_similarity_search_respects_k():
    vectorstore = build_vectorstore(_sample_chunks(), FakeEmbeddings(VOCABULARY))

    results = similarity_search(vectorstore, "kafka streaming", k=1)

    assert len(results) == 1
    assert results[0][0] == "chunk_kafka"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_store.py -v`
Expected: FAIL — `rag/store.py` has no `build_vectorstore`/`similarity_search` (`ImportError`).

- [ ] **Step 3: Write minimal implementation**

Replace the contents of `algoworks-rfp-poc/backend/rag/store.py`:

```python
"""Vectorstore local (Chroma) para el corpus de conocimiento ficticio."""

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from api.schemas import Chunk

COLLECTION_NAME = "algoworks_rfp_corpus"


def build_vectorstore(
    chunks: list[Chunk],
    embeddings: Embeddings,
    persist_directory: str | None = None,
) -> Chroma:
    documents = [
        Document(
            page_content=chunk.text,
            metadata={
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "section_type": chunk.section_type,
            },
        )
        for chunk in chunks
    ]
    ids = [chunk.chunk_id for chunk in chunks]
    return Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        ids=ids,
        collection_name=COLLECTION_NAME,
        persist_directory=persist_directory,
    )


def similarity_search(vectorstore: Chroma, query: str, k: int) -> list[tuple[str, str, float]]:
    results = vectorstore.similarity_search_with_relevance_scores(query, k=k)
    return [
        (document.metadata["chunk_id"], document.page_content, score)
        for document, score in results
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/rag/store.py algoworks-rfp-poc/backend/tests/fakes.py algoworks-rfp-poc/backend/tests/test_store.py
git commit -m "feat: implement Chroma vectorstore and shared test fakes"
```

---

## Task 4: Schema contract extension (traceability fields)

**Files:**
- Modify: `algoworks-rfp-poc/backend/api/schemas.py`
- Modify: `algoworks-rfp-poc/backend/tests/test_schemas.py`

**Interfaces:**
- Produces (new models): `CitationSimilarity`, `TokenUsage`, `PipelineMetrics`, `ReasoningPathAudit` (from `api.schemas`), consumed starting Task 10.
- Produces (new fields, all additive): `DraftSection.reasoning: str = ""`, `DraftSection.citation_similarities: list[CitationSimilarity] = []`, `DraftSection.overall_similarity: float = 0.0`, `VerificationResult.reasoning: str = ""`, `VerificationResult.retries_used: int = 0`, `TraceEvent.duration_ms: float = 0.0`, `TraceEvent.tokens: TokenUsage | None = None`, `PipelineResult.metrics: PipelineMetrics` (required), `PipelineResult.reasoning_path_audit: ReasoningPathAudit` (required).
- This is the frozen-contract change CLAUDE.md §4 requires announcing to the team before merging — every change here is additive (no existing field renamed/retyped), per the hard rule.

- [ ] **Step 1: Write the failing test**

Replace the contents of `algoworks-rfp-poc/backend/tests/test_schemas.py`:

```python
"""Smoke test del contrato de datos: valida que el contrato completo
(incluyendo los campos de trazabilidad de sub-project A) importa e
instancia correctamente. No cubre logica de negocio (aun no implementada).
"""

from datetime import datetime

from api.schemas import (
    Chunk,
    CitationSimilarity,
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


def _sample_trace_event(node: str = "retrieve_chunks") -> TraceEvent:
    return TraceEvent(
        node=node,
        timestamp=datetime(2026, 9, 18, 12, 0, 0),
        input_summary="requirement=req_001",
        output_summary="1 chunk recuperado",
        reasoning="El chunk_001 tiene la mayor similitud coseno con el requisito.",
    )


def test_trace_event_defaults_have_no_duration_or_tokens():
    trace_event = _sample_trace_event()

    assert trace_event.duration_ms == 0.0
    assert trace_event.tokens is None


def test_trace_event_accepts_duration_and_token_usage():
    trace_event = TraceEvent(
        node="generate_draft",
        timestamp=datetime(2026, 9, 18, 12, 0, 0),
        input_summary="...",
        output_summary="...",
        reasoning="...",
        duration_ms=123.4,
        tokens=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost_usd=0.001),
    )

    assert trace_event.duration_ms == 123.4
    assert trace_event.tokens.total_tokens == 150


def test_draft_section_defaults_have_no_reasoning_or_similarity():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])

    assert draft.reasoning == ""
    assert draft.citation_similarities == []
    assert draft.overall_similarity == 0.0


def test_draft_section_accepts_citation_similarities():
    draft = DraftSection(
        req_id="req_001",
        text="Texto [[chunk_001]].",
        cited_chunks=["chunk_001"],
        reasoning="Se citó chunk_001 porque describe experiencia previa relevante.",
        citation_similarities=[CitationSimilarity(chunk_id="chunk_001", similarity=0.87)],
        overall_similarity=0.87,
    )

    assert draft.citation_similarities[0].chunk_id == "chunk_001"
    assert draft.overall_similarity == 0.87


def test_verification_result_defaults_have_no_reasoning_or_retries():
    verification = VerificationResult(req_id="req_001", supported=True, issues=[], confidence=0.9)

    assert verification.reasoning == ""
    assert verification.retries_used == 0


def test_pipeline_result_round_trip_with_metrics_and_audit():
    chunk = Chunk(
        chunk_id="chunk_001",
        text="Algoworks entrego 12 proyectos de integracion de datos en 2023.",
        source="Propuesta_ClienteX_2023.md",
        section_type="experiencia_previa",
    )
    requirement = Requirement(
        req_id="req_001",
        text="El proveedor debe demostrar experiencia previa en proyectos similares.",
        section_target="experiencia_previa",
    )
    retrieved = RetrievedChunk(
        chunk_id=chunk.chunk_id,
        score=0.87,
        justification="El chunk describe experiencia previa relevante en integracion de datos.",
    )
    draft = DraftSection(
        req_id=requirement.req_id,
        text="Algoworks cuenta con experiencia comprobada [[chunk_001]].",
        cited_chunks=[chunk.chunk_id],
        reasoning="Se citó chunk_001 por ser el más relevante.",
        citation_similarities=[CitationSimilarity(chunk_id="chunk_001", similarity=0.9)],
        overall_similarity=0.9,
    )
    verification = VerificationResult(
        req_id=requirement.req_id,
        supported=True,
        issues=[],
        confidence=0.92,
        reasoning="El chunk_001 respalda completamente la afirmación.",
        retries_used=0,
    )
    metrics = PipelineMetrics(
        total_duration_ms=842.5,
        total_tokens=TokenUsage(input_tokens=500, output_tokens=200, total_tokens=700, estimated_cost_usd=0.002),
        retries_used=0,
        requirements_supported=1,
        requirements_needing_review=0,
        hallucinated_citations_caught=0,
    )
    reasoning_path_audit = ReasoningPathAudit(
        is_consistent=True,
        node_sequence=["extract_requirements", "retrieve_chunks", "generate_draft", "verify_citations"],
        issues=[],
    )

    result = PipelineResult(
        rfp_id="rfp_001",
        requirements=[requirement],
        retrieved={requirement.req_id: [retrieved]},
        drafts={requirement.req_id: draft},
        verification={requirement.req_id: verification},
        trace_log=[_sample_trace_event()],
        metrics=metrics,
        reasoning_path_audit=reasoning_path_audit,
    )

    assert result.rfp_id == "rfp_001"
    assert result.drafts[requirement.req_id].cited_chunks == [chunk.chunk_id]
    assert result.metrics.requirements_supported == 1
    assert result.reasoning_path_audit.is_consistent is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'CitationSimilarity' from 'api.schemas'` (none of the new models/fields exist yet).

- [ ] **Step 3: Write minimal implementation**

Replace the contents of `algoworks-rfp-poc/backend/api/schemas.py`:

```python
"""Contrato de datos del pipeline RFP.

Fuente de verdad: CLAUDE.md, sección 4, y
docs/superpowers/specs/2026-09-18-traceability-metrics-design.md (sub-project A).
No cambiar nombres de campos ni tipos existentes sin avisar en el chat del
equipo — frontend y backend dependen de que este contrato sea estable desde
la hora 0. Las adiciones de sub-project A son todas aditivas.
"""

from datetime import datetime

from pydantic import BaseModel


class Chunk(BaseModel):
    chunk_id: str
    text: str
    source: str  # ej. "Propuesta_ClienteX_2023.md"
    section_type: str  # "experiencia_previa" | "capacidades_tecnicas" | "equipo" | ...
    metadata: dict = {}


class Requirement(BaseModel):
    req_id: str
    text: str
    section_target: str


class RetrievedChunk(BaseModel):
    chunk_id: str
    score: float
    justification: str


class CitationSimilarity(BaseModel):
    chunk_id: str
    similarity: float  # similitud coseno, embedding del texto citado <-> embedding del chunk


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0  # best-effort; 0.0 significa "desconocido", no "gratis"


class DraftSection(BaseModel):
    req_id: str
    text: str  # contiene marcadores [[chunk_id]] inline
    cited_chunks: list[str]
    reasoning: str = ""  # explicación del LLM de qué chunks usó y por qué (generate_draft)
    citation_similarities: list[CitationSimilarity] = []  # compute_traceability_metrics
    overall_similarity: float = 0.0  # compute_traceability_metrics


class VerificationResult(BaseModel):
    req_id: str
    supported: bool
    issues: list[str]
    confidence: float
    reasoning: str = ""  # motivo del veredicto (verify_citations)
    retries_used: int = 0  # reintentos ya consumidos antes de este veredicto


class TraceEvent(BaseModel):
    node: str
    timestamp: datetime
    input_summary: str
    output_summary: str
    reasoning: str
    duration_ms: float = 0.0
    tokens: TokenUsage | None = None  # None = el nodo no hizo ninguna llamada a LLM


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
    issues: list[str]  # vacío cuando is_consistent es True


class PipelineResult(BaseModel):
    rfp_id: str
    requirements: list[Requirement]
    retrieved: dict[str, list[RetrievedChunk]]
    drafts: dict[str, DraftSection]
    verification: dict[str, VerificationResult]
    trace_log: list[TraceEvent]
    metrics: PipelineMetrics
    reasoning_path_audit: ReasoningPathAudit
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/api/schemas.py algoworks-rfp-poc/backend/tests/test_schemas.py
git commit -m "feat: extend data contract with traceability metrics fields (additive)"
```

---

## Task 5: GraphState

**Files:**
- Modify: `algoworks-rfp-poc/backend/graph/state.py`
- Test: none (a pure type definition; it is exercised indirectly by every later node/graph test). Skipping a dedicated test file here is intentional — there is no behavior to assert on a `TypedDict` declaration.

**Interfaces:**
- Produces: `GraphState` (TypedDict) and `MAX_GENERATE_RETRIES: int`, consumed by every node in Tasks 8-12 and by `graph.py` in Task 13.

`GraphState` fields:
- `rfp_id: str`, `rfp_text: str` — set once at pipeline start.
- `requirements: list[Requirement]` — set by `extract_requirements`.
- `retrieved: dict[str, list[RetrievedChunk]]` — set by `retrieve_chunks` (keyed by `req_id`).
- `pending_req_ids: list[str]` — requirements `generate_draft` must (re)generate on this pass; recomputed by `verify_citations` for the retry loop.
- `hallucinated_citations: dict[str, list[str]]` — chunk_ids cited by `generate_draft` that don't exist among the retrieved chunks for that requirement (keyed by `req_id`); **overwritten** each retry pass, so it only reflects the most recent pass.
- `hallucination_catches: int` — internal-only running total of hallucinated chunk_ids caught across **all** passes/retries (unlike `hallucinated_citations`, this is never overwritten, only incremented); read by `compute_traceability_metrics` for `PipelineMetrics.hallucinated_citations_caught`. Not part of the public `PipelineResult` contract.
- `drafts: dict[str, DraftSection]`, `verification: dict[str, VerificationResult]` — mirror the `PipelineResult` fields.
- `retry_counts: dict[str, int]` — number of `generate_draft` retries already used per `req_id` (max `MAX_GENERATE_RETRIES`).
- `trace_log: list[TraceEvent]` — append-only, one event per node execution.
- `metrics: PipelineMetrics | None` — `None` until `compute_traceability_metrics` runs (the only node that sets it).
- `reasoning_path_audit: ReasoningPathAudit | None` — `None` until `compute_traceability_metrics` runs.

- [ ] **Step 1: Write the implementation directly**

Replace the contents of `algoworks-rfp-poc/backend/graph/state.py`:

```python
"""Estado compartido del grafo LangGraph del pipeline de RFP."""

from typing import TypedDict

from api.schemas import (
    DraftSection,
    PipelineMetrics,
    ReasoningPathAudit,
    Requirement,
    RetrievedChunk,
    TraceEvent,
    VerificationResult,
)

MAX_GENERATE_RETRIES = 1


class GraphState(TypedDict):
    rfp_id: str
    rfp_text: str
    requirements: list[Requirement]
    retrieved: dict[str, list[RetrievedChunk]]
    pending_req_ids: list[str]
    hallucinated_citations: dict[str, list[str]]
    hallucination_catches: int
    drafts: dict[str, DraftSection]
    verification: dict[str, VerificationResult]
    retry_counts: dict[str, int]
    trace_log: list[TraceEvent]
    metrics: PipelineMetrics | None
    reasoning_path_audit: ReasoningPathAudit | None
```

- [ ] **Step 2: Verify it imports cleanly**

Run (from `algoworks-rfp-poc/backend/`): `uv run python -c "from graph.state import GraphState, MAX_GENERATE_RETRIES; print(MAX_GENERATE_RETRIES)"`
Expected: prints `1` with no errors.

- [ ] **Step 3: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/state.py
git commit -m "feat: define shared GraphState for the LangGraph pipeline"
```

---

## Task 6: Prompt loader + versioned prompt files

**Files:**
- Create: `algoworks-rfp-poc/backend/graph/prompts/__init__.py`
- Create: `algoworks-rfp-poc/backend/graph/prompts/extract_requirements.txt`
- Create: `algoworks-rfp-poc/backend/graph/prompts/retrieve_chunks_justification.txt`
- Create: `algoworks-rfp-poc/backend/graph/prompts/generate_draft.txt`
- Create: `algoworks-rfp-poc/backend/graph/prompts/verify_citations.txt`
- Delete: `algoworks-rfp-poc/backend/graph/prompts/.gitkeep` (no longer needed once the directory has real files)
- Test: `algoworks-rfp-poc/backend/tests/test_prompts.py`

**Interfaces:**
- Produces: `load_prompt(filename: str) -> str` (from `graph.prompts`), consumed by Tasks 8-11. Each prompt file uses `str.format(...)`-style named placeholders (documented per file below). `generate_draft.txt` and `verify_citations.txt` explicitly ask the model for a natural-language `reasoning` alongside its main output, since Tasks 10-11 parse that into a structured `reasoning` field via `.with_structured_output(...)` — the schema enforces the field exists, the prompt wording is what makes the LLM's answer to it actually useful.

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_prompts.py`:

```python
"""Tests del loader de prompts versionados como archivos de texto."""

import pytest

from graph.prompts import load_prompt


def test_load_prompt_returns_file_contents():
    prompt = load_prompt("extract_requirements.txt")

    assert "{rfp_text}" in prompt


def test_load_prompt_raises_for_missing_file():
    with pytest.raises(FileNotFoundError):
        load_prompt("no_existe.txt")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph.prompts'` (it's currently an empty directory with only `.gitkeep`).

- [ ] **Step 3: Write the prompt files and the loader**

Create `algoworks-rfp-poc/backend/graph/prompts/extract_requirements.txt`:

```
Eres un asistente que extrae requisitos estructurados de un RFP (Request for Proposal).

Lee el siguiente texto de RFP y devuelve la lista de requisitos que el proveedor debe cumplir. Para cada requisito, asigna un req_id corto y único, y un section_target de este conjunto cerrado: "experiencia_previa", "capacidades_tecnicas", "equipo".

Texto del RFP:
{rfp_text}
```

Create `algoworks-rfp-poc/backend/graph/prompts/retrieve_chunks_justification.txt`:

```
Eres un asistente que explica en una frase por qué un fragmento de conocimiento es relevante para un requisito de RFP.

Requisito:
{requirement_text}

Fragmento recuperado:
{chunk_text}

Explica en una sola frase, en español, por qué este fragmento es relevante para el requisito.
```

Create `algoworks-rfp-poc/backend/graph/prompts/generate_draft.txt`:

```
Eres un asistente que redacta una sección de una propuesta técnica en respuesta a un requisito de RFP.

Requisito:
{requirement_text}

Fragmentos de conocimiento disponibles (usa SOLO estos, citando su chunk_id entre dobles corchetes, ej. [[chunk_001]], por cada afirmación factual):
{chunks_block}

Redacta un párrafo breve (3-5 frases) que responda al requisito citando el chunk_id de cada afirmación factual que uses. No inventes chunk_id que no estén en la lista de arriba.

Además del párrafo redactado, explica en 1-2 frases tu razonamiento: qué chunks elegiste usar y por qué los consideraste relevantes para este requisito.
```

Create `algoworks-rfp-poc/backend/graph/prompts/verify_citations.txt`:

```
Eres un verificador que revisa si un borrador de propuesta está respaldado por los fragmentos de conocimiento que cita.

Borrador:
{draft_text}

Fragmentos citados:
{chunks_block}

Indica si el borrador está completamente respaldado por los fragmentos citados (supported: true/false), lista los problemas encontrados (issues, vacío si no hay) y da un nivel de confianza entre 0 y 1 (confidence).

Explica también en 1-2 frases tu razonamiento: qué parte del borrador sí (o no) está respaldada por los fragmentos, y por qué llegaste a ese veredicto.
```

Create `algoworks-rfp-poc/backend/graph/prompts/__init__.py`:

```python
"""Carga prompts versionados como archivos de texto (CLAUDE.md, sección 7:
nunca hardcodeados en el código de los nodos).
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8").strip()
```

Delete the now-unnecessary placeholder:

```bash
rm algoworks-rfp-poc/backend/graph/prompts/.gitkeep
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/prompts algoworks-rfp-poc/backend/tests/test_prompts.py
git commit -m "feat: add versioned prompt files and loader"
```

---

## Task 7: LLM call tracking (latency-adjacent token/cost instrumentation)

**Files:**
- Create: `algoworks-rfp-poc/backend/graph/llm_tracking.py`
- Test: `algoworks-rfp-poc/backend/tests/test_llm_tracking.py`

**Interfaces:**
- Consumes: `TokenUsage` (from `api.schemas`).
- Produces: `TokenAccumulator` (class, `.add(usage: TokenUsage) -> None`, `.total() -> TokenUsage`), `invoke_tracked(llm, prompt: str, accumulator: TokenAccumulator) -> str`, `invoke_structured_tracked(llm, schema: type[BaseModel], prompt: str, accumulator: TokenAccumulator)`, `estimate_cost_usd(model_name: str, usage: TokenUsage) -> float` (all from `graph.llm_tracking`). Consumed by every node in Tasks 8-11 (not Task 12, which makes no LLM calls) and, indirectly, by Task 14's `FallbackChatModel` (which must accept the `include_raw` kwarg `invoke_structured_tracked` always passes).
- This module is deliberately self-contained: its tests use small local fakes (not `tests.fakes.ScriptedChatModel`), so it has no dependency on Task 3/8's fakes and nothing later depends on its *tests*, only its 4 public names.

**Design notes carried over from the spec:**
- `invoke_tracked` replaces `llm.invoke(prompt).content.strip()`. It reads `getattr(response, "usage_metadata", None)` and `getattr(response, "response_metadata", None)` defensively — a response without them (e.g. `tests.fakes.ScriptedChatModel`'s plain `SimpleNamespace(content=...)`) accumulates zero usage without raising.
- `invoke_structured_tracked` always calls `llm.with_structured_output(schema, include_raw=True).invoke(prompt)`, which returns a dict shaped `{"raw": <message>, "parsed": <schema instance or None>, "parsing_error": <exception or None>}` (this is the standard LangChain `include_raw=True` contract). It accumulates usage from `raw`, re-raises `parsing_error` if it is not `None`, and otherwise returns `parsed`.
- `estimate_cost_usd` uses a small hardcoded price table keyed by the **model name strings currently configured** via `GROQ_MODEL_SMALL`/`GROQ_MODEL_LARGE` env vars (defaulting the same as Task 14's `get_chat_llm`, so the two modules agree without importing each other). Any other `model_name` (Ollama, empty, unrecognized) returns `0.0`.

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_llm_tracking.py`:

```python
"""Tests del módulo de tracking de llamadas LLM: acumulación de tokens,
extracción defensiva de usage_metadata/response_metadata, y estimación de
costo best-effort. No depende de red ni de modelos reales."""

from types import SimpleNamespace

import pytest

from api.schemas import TokenUsage
from graph.llm_tracking import (
    TokenAccumulator,
    estimate_cost_usd,
    invoke_structured_tracked,
    invoke_tracked,
)


def test_token_accumulator_sums_multiple_usages():
    accumulator = TokenAccumulator()

    accumulator.add(TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15, estimated_cost_usd=0.001))
    accumulator.add(TokenUsage(input_tokens=20, output_tokens=8, total_tokens=28, estimated_cost_usd=0.002))

    total = accumulator.total()
    assert total.input_tokens == 30
    assert total.output_tokens == 13
    assert total.total_tokens == 43
    assert total.estimated_cost_usd == pytest.approx(0.003)


def test_token_accumulator_total_is_zero_when_empty():
    total = TokenAccumulator().total()

    assert total == TokenUsage()


class _PlainResponse:
    def __init__(self, content: str):
        self.content = content


def test_invoke_tracked_returns_content_and_accumulates_zero_for_missing_usage_metadata():
    class _NoMetadataLLM:
        def invoke(self, prompt):
            return _PlainResponse(" respuesta sin metadata ")

    accumulator = TokenAccumulator()

    content = invoke_tracked(_NoMetadataLLM(), "prompt", accumulator)

    assert content == "respuesta sin metadata"
    assert accumulator.total() == TokenUsage()


def test_invoke_tracked_accumulates_real_usage_metadata(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL_SMALL", "test-small-model")

    class _WithMetadataLLM:
        def invoke(self, prompt):
            response = _PlainResponse("respuesta")
            response.usage_metadata = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
            response.response_metadata = {"model_name": "test-small-model"}
            return response

    accumulator = TokenAccumulator()

    invoke_tracked(_WithMetadataLLM(), "prompt", accumulator)

    total = accumulator.total()
    assert total.input_tokens == 100
    assert total.total_tokens == 150
    assert total.estimated_cost_usd > 0.0


class _StructuredLLM:
    def __init__(self, raw, parsed, parsing_error=None):
        self._raw = raw
        self._parsed = parsed
        self._parsing_error = parsing_error
        self.received_include_raw = None

    def with_structured_output(self, schema, include_raw: bool = False):
        self.received_include_raw = include_raw
        outer = self

        class _Runnable:
            def invoke(self, prompt):
                return {"raw": outer._raw, "parsed": outer._parsed, "parsing_error": outer._parsing_error}

        return _Runnable()


def test_invoke_structured_tracked_returns_parsed_and_accumulates_usage():
    raw = _PlainResponse("")
    raw.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    raw.response_metadata = {}
    parsed = SimpleNamespace(field="valor")
    llm = _StructuredLLM(raw=raw, parsed=parsed)
    accumulator = TokenAccumulator()

    result = invoke_structured_tracked(llm, SimpleNamespace, "prompt", accumulator)

    assert result is parsed
    assert llm.received_include_raw is True
    assert accumulator.total().total_tokens == 15


def test_invoke_structured_tracked_reraises_parsing_error():
    raw = _PlainResponse("")
    llm = _StructuredLLM(raw=raw, parsed=None, parsing_error=ValueError("no se pudo parsear"))
    accumulator = TokenAccumulator()

    with pytest.raises(ValueError, match="no se pudo parsear"):
        invoke_structured_tracked(llm, SimpleNamespace, "prompt", accumulator)


def test_estimate_cost_usd_returns_zero_for_unknown_model():
    assert estimate_cost_usd("modelo-desconocido", TokenUsage(input_tokens=1000, output_tokens=1000)) == 0.0


def test_estimate_cost_usd_returns_positive_for_configured_groq_model(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL_LARGE", "test-large-model")

    cost = estimate_cost_usd("test-large-model", TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000))

    assert cost > 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_llm_tracking.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph.llm_tracking'`.

- [ ] **Step 3: Write minimal implementation**

Create `algoworks-rfp-poc/backend/graph/llm_tracking.py`:

```python
"""Instrumentación de llamadas LLM: acumula tokens/costo por nodo y
reemplaza .invoke()/.with_structured_output().invoke() por variantes que
registran uso, sin romper el flujo cuando el modelo no reporta metadata
(p. ej. los dobles de prueba)."""

import os

from pydantic import BaseModel

from api.schemas import TokenUsage

# USD por millón de tokens (input, output). Tabla chica y aproximada, solo
# para los modelos Groq configurados via env vars; cualquier otro
# model_name (Ollama, vacío, desconocido) cotiza en 0.0.
_DEFAULT_GROQ_MODEL_SMALL = "llama-3.1-8b-instant"
_DEFAULT_GROQ_MODEL_LARGE = "llama-3.3-70b-versatile"
_PRICE_PER_MILLION_TOKENS_USD: dict[str, tuple[float, float]] = {
    _DEFAULT_GROQ_MODEL_SMALL: (0.05, 0.08),
    _DEFAULT_GROQ_MODEL_LARGE: (0.59, 0.79),
}


class TokenAccumulator:
    """Un acumulador por ejecución de nodo; se le van sumando las llamadas
    LLM que haga ese nodo, y al final se lee su total para el TraceEvent."""

    def __init__(self) -> None:
        self._usages: list[TokenUsage] = []

    def add(self, usage: TokenUsage) -> None:
        self._usages.append(usage)

    def total(self) -> TokenUsage:
        return TokenUsage(
            input_tokens=sum(usage.input_tokens for usage in self._usages),
            output_tokens=sum(usage.output_tokens for usage in self._usages),
            total_tokens=sum(usage.total_tokens for usage in self._usages),
            estimated_cost_usd=sum(usage.estimated_cost_usd for usage in self._usages),
        )


def _extract_usage_and_model(response) -> tuple[TokenUsage, str]:
    usage_metadata = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}
    model_name = response_metadata.get("model_name") or response_metadata.get("model") or ""
    usage = TokenUsage(
        input_tokens=usage_metadata.get("input_tokens", 0),
        output_tokens=usage_metadata.get("output_tokens", 0),
        total_tokens=usage_metadata.get("total_tokens", 0),
    )
    return usage, model_name


def _tracked_usage(response) -> TokenUsage:
    usage, model_name = _extract_usage_and_model(response)
    return usage.model_copy(update={"estimated_cost_usd": estimate_cost_usd(model_name, usage)})


def invoke_tracked(llm, prompt: str, accumulator: TokenAccumulator) -> str:
    response = llm.invoke(prompt)
    accumulator.add(_tracked_usage(response))
    return response.content.strip()


def invoke_structured_tracked(llm, schema: type[BaseModel], prompt: str, accumulator: TokenAccumulator):
    response = llm.with_structured_output(schema, include_raw=True).invoke(prompt)
    accumulator.add(_tracked_usage(response["raw"]))
    if response["parsing_error"] is not None:
        raise response["parsing_error"]
    return response["parsed"]


def estimate_cost_usd(model_name: str, usage: TokenUsage) -> float:
    prices = _prices_by_configured_model_name()
    price = prices.get(model_name)
    if price is None:
        return 0.0
    input_price_per_million, output_price_per_million = price
    return (
        usage.input_tokens * input_price_per_million + usage.output_tokens * output_price_per_million
    ) / 1_000_000


def _prices_by_configured_model_name() -> dict[str, tuple[float, float]]:
    small_model = os.environ.get("GROQ_MODEL_SMALL", _DEFAULT_GROQ_MODEL_SMALL)
    large_model = os.environ.get("GROQ_MODEL_LARGE", _DEFAULT_GROQ_MODEL_LARGE)
    return {
        small_model: _PRICE_PER_MILLION_TOKENS_USD[_DEFAULT_GROQ_MODEL_SMALL],
        large_model: _PRICE_PER_MILLION_TOKENS_USD[_DEFAULT_GROQ_MODEL_LARGE],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_llm_tracking.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/llm_tracking.py algoworks-rfp-poc/backend/tests/test_llm_tracking.py
git commit -m "feat: add LLM call tracking (token/cost instrumentation)"
```

---

## Task 8: Node — `extract_requirements`

**Files:**
- Create: `algoworks-rfp-poc/backend/graph/nodes/extract_requirements.py`
- Modify: `algoworks-rfp-poc/backend/tests/fakes.py` (add `ScriptedChatModel`)
- Test: `algoworks-rfp-poc/backend/tests/test_node_extract_requirements.py`

**Interfaces:**
- Consumes: `GraphState`, `load_prompt` (from `graph.prompts`), `Requirement`/`TraceEvent` (from `api.schemas`), `TokenAccumulator`/`invoke_structured_tracked` (from `graph.llm_tracking`, Task 7).
- Produces: `make_extract_requirements_node(llm) -> Callable[[GraphState], dict]`. The returned node function reads `state["rfp_text"]`/`state["rfp_id"]`/`state["trace_log"]` and returns `{"requirements": ..., "pending_req_ids": ..., "retry_counts": ..., "trace_log": ...}` where the appended `TraceEvent` carries real `duration_ms` and `tokens`. Consumed by Task 13 (`graph.py`).
- Produces (test double, `tests/fakes.py`): `ScriptedChatModel(plain_responses=None, structured_responses=None)` — an LLM double whose `.invoke(prompt)` pops from `plain_responses` (returns an object with `.content`, no `usage_metadata`/`response_metadata`, so tracked calls against it always accumulate zero usage) and whose `.with_structured_output(schema, include_raw=False)` pops from `structured_responses`: when `include_raw` is `False` it returns the popped object directly (unused by any task in this plan, kept for direct/manual test use); when `True` (what `invoke_structured_tracked` always passes) it returns `{"raw": SimpleNamespace(content="", usage_metadata=None, response_metadata={}), "parsed": <popped object>, "parsing_error": None}`. Reused by Tasks 9, 10, 11, 13.

- [ ] **Step 1: Add `ScriptedChatModel` to the shared fakes**

Add to `algoworks-rfp-poc/backend/tests/fakes.py` (append below `FakeEmbeddings`):

```python
from types import SimpleNamespace


class ScriptedChatModel:
    """LLM de prueba que devuelve respuestas predefinidas, en orden, tanto
    para llamadas de texto plano (.invoke) como para salida estructurada
    (.with_structured_output(...).invoke). No hace ninguna llamada real ni
    reporta usage_metadata/response_metadata (las llamadas trackeadas
    contra este doble siempre acumulan uso cero).
    """

    def __init__(self, plain_responses=None, structured_responses=None):
        self._plain_responses = list(plain_responses or [])
        self._structured_responses = list(structured_responses or [])

    def invoke(self, prompt: str):
        text = self._plain_responses.pop(0)
        return SimpleNamespace(content=text)

    def with_structured_output(self, schema, include_raw: bool = False):
        outer = self

        class _StructuredRunnable:
            def invoke(self, prompt: str):
                parsed = outer._structured_responses.pop(0)
                if include_raw:
                    return {
                        "raw": SimpleNamespace(content="", usage_metadata=None, response_metadata={}),
                        "parsed": parsed,
                        "parsing_error": None,
                    }
                return parsed

        return _StructuredRunnable()
```

- [ ] **Step 2: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_node_extract_requirements.py`:

```python
"""Tests del nodo extract_requirements: caso feliz (structured output) y
caso de fallback (split por líneas numeradas cuando el LLM falla)."""

from types import SimpleNamespace

from graph.nodes.extract_requirements import make_extract_requirements_node
from tests.fakes import ScriptedChatModel


def _base_state(rfp_text: str) -> dict:
    return {"rfp_id": "rfp_001", "rfp_text": rfp_text, "trace_log": []}


def test_extract_requirements_uses_structured_output_when_it_succeeds():
    extracted = SimpleNamespace(
        requirements=[
            SimpleNamespace(req_id="req_001", text="Debe tener experiencia previa.", section_target="experiencia_previa"),
            SimpleNamespace(req_id="req_002", text="Debe describir su arquitectura.", section_target="capacidades_tecnicas"),
        ]
    )
    llm = ScriptedChatModel(structured_responses=[extracted])
    node = make_extract_requirements_node(llm)

    result = node(_base_state("1. Debe tener experiencia previa.\n2. Debe describir su arquitectura."))

    assert [r.req_id for r in result["requirements"]] == ["req_001", "req_002"]
    assert result["requirements"][0].section_target == "experiencia_previa"
    assert result["pending_req_ids"] == ["req_001", "req_002"]
    assert result["retry_counts"] == {"req_001": 0, "req_002": 0}
    assert len(result["trace_log"]) == 1
    assert result["trace_log"][0].node == "extract_requirements"
    assert result["trace_log"][0].duration_ms >= 0.0
    assert result["trace_log"][0].tokens is not None


def test_extract_requirements_falls_back_to_numbered_line_split_on_llm_failure():
    class RaisingLLM:
        def with_structured_output(self, schema, include_raw: bool = False):
            raise RuntimeError("structured output no soportado / conectividad caída")

    node = make_extract_requirements_node(RaisingLLM())

    rfp_text = "1. Debe tener experiencia previa.\n2. Debe describir su arquitectura.\nTexto suelto sin numerar."
    result = node(_base_state(rfp_text))

    assert len(result["requirements"]) == 2
    assert result["requirements"][0].text == "Debe tener experiencia previa."
    assert result["requirements"][1].text == "Debe describir su arquitectura."
    assert "fallback" in result["trace_log"][0].reasoning.lower()
    assert result["trace_log"][0].tokens.total_tokens == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_node_extract_requirements.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph.nodes.extract_requirements'`.

- [ ] **Step 4: Write minimal implementation**

Create `algoworks-rfp-poc/backend/graph/nodes/extract_requirements.py`:

```python
"""Nodo extract_requirements: parsea el RFP a requisitos estructurados."""

import re
import time
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from api.schemas import Requirement, TraceEvent
from graph.llm_tracking import TokenAccumulator, invoke_structured_tracked
from graph.prompts import load_prompt
from graph.state import GraphState

SectionTarget = Literal["experiencia_previa", "capacidades_tecnicas", "equipo"]

_NUMBERED_LINE = re.compile(r"^\s*\d+[.)]\s*(.+)$")


class _ExtractedRequirement(BaseModel):
    req_id: str
    text: str
    section_target: SectionTarget


class _ExtractedRequirements(BaseModel):
    requirements: list[_ExtractedRequirement]


def _fallback_split_by_numbered_lines(rfp_text: str) -> list[Requirement]:
    requirements: list[Requirement] = []
    for line in rfp_text.splitlines():
        match = _NUMBERED_LINE.match(line)
        if not match:
            continue
        requirements.append(
            Requirement(
                req_id=f"req_{len(requirements) + 1:03d}",
                text=match.group(1).strip(),
                section_target="capacidades_tecnicas",
            )
        )
    return requirements


def make_extract_requirements_node(llm):
    prompt_template = load_prompt("extract_requirements.txt")

    def extract_requirements(state: GraphState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()
        prompt = prompt_template.format(rfp_text=state["rfp_text"])

        try:
            extracted = invoke_structured_tracked(llm, _ExtractedRequirements, prompt, accumulator)
            requirements = [
                Requirement(req_id=item.req_id, text=item.text, section_target=item.section_target)
                for item in extracted.requirements
            ]
            reasoning = (
                "Se extrajeron los requisitos usando structured output del LLM, "
                "con section_target restringido al enum cerrado."
            )
        except Exception:
            requirements = _fallback_split_by_numbered_lines(state["rfp_text"])
            reasoning = (
                "El structured output del LLM falló; se usó el fallback sin LLM "
                "de split por líneas numeradas."
            )

        trace_event = TraceEvent(
            node="extract_requirements",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"rfp_id={state['rfp_id']}, {len(state['rfp_text'])} caracteres de RFP",
            output_summary=f"{len(requirements)} requisitos extraídos",
            reasoning=reasoning,
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "requirements": requirements,
            "pending_req_ids": [r.req_id for r in requirements],
            "retry_counts": {r.req_id: 0 for r in requirements},
            "trace_log": [*state["trace_log"], trace_event],
        }

    return extract_requirements
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_node_extract_requirements.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/nodes/extract_requirements.py algoworks-rfp-poc/backend/tests/fakes.py algoworks-rfp-poc/backend/tests/test_node_extract_requirements.py
git commit -m "feat: implement extract_requirements graph node"
```

---

## Task 9: Node — `retrieve_chunks`

**Files:**
- Create: `algoworks-rfp-poc/backend/graph/nodes/retrieve_chunks.py`
- Modify: `algoworks-rfp-poc/backend/tests/fakes.py` (add `FakeVectorstore`)
- Test: `algoworks-rfp-poc/backend/tests/test_node_retrieve_chunks.py`

**Interfaces:**
- Consumes: `GraphState`, `load_prompt`, `rag.store.similarity_search`, `RetrievedChunk`/`TraceEvent` (from `api.schemas`), `TokenAccumulator`/`invoke_tracked` (from `graph.llm_tracking`), `ScriptedChatModel` (from `tests.fakes`, Task 8).
- Produces: `make_retrieve_chunks_node(llm, vectorstore, top_k: int = DEFAULT_TOP_K) -> Callable[[GraphState], dict]`. Reads `state["requirements"]`/`state["trace_log"]`, returns `{"retrieved": ..., "trace_log": ...}` with real `duration_ms`/`tokens`. Consumed by Task 13.
- Produces (test double, `tests/fakes.py`): `FakeVectorstore(results_by_query: dict[str, list[tuple[str, str, float]]])` exposing `.similarity_search_with_relevance_scores(query, k)` returning `list[tuple[Document, float]]`, so `rag.store.similarity_search`'s real code path is exercised by the node test.

- [ ] **Step 1: Add `FakeVectorstore` to the shared fakes**

Add to `algoworks-rfp-poc/backend/tests/fakes.py` (append below `ScriptedChatModel`):

```python
from langchain_core.documents import Document


class FakeVectorstore:
    """Doble de Chroma: expone solo similarity_search_with_relevance_scores,
    devolviendo resultados preprogramados por texto de query exacto.
    """

    def __init__(self, results_by_query: dict[str, list[tuple[str, str, float]]]):
        self._results_by_query = results_by_query

    def similarity_search_with_relevance_scores(self, query: str, k: int = 4):
        candidates = self._results_by_query.get(query, [])
        documents_with_scores = [
            (Document(page_content=text, metadata={"chunk_id": chunk_id}), score)
            for chunk_id, text, score in candidates
        ]
        return documents_with_scores[:k]
```

- [ ] **Step 2: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_node_retrieve_chunks.py`:

```python
"""Tests del nodo retrieve_chunks: similitud + justificación por chunk."""

from graph.nodes.retrieve_chunks import make_retrieve_chunks_node
from api.schemas import Requirement
from tests.fakes import FakeVectorstore, ScriptedChatModel


def test_retrieve_chunks_attaches_justification_per_candidate():
    requirement = Requirement(req_id="req_001", text="experiencia en retail", section_target="experiencia_previa")
    vectorstore = FakeVectorstore(
        {
            "experiencia en retail": [
                ("chunk_002", "Proyecto de retail.", 0.9),
                ("chunk_001", "Proyecto de manufactura.", 0.5),
            ]
        }
    )
    llm = ScriptedChatModel(plain_responses=["Justificación A.", "Justificación B."])
    node = make_retrieve_chunks_node(llm, vectorstore, top_k=2)

    result = node({"requirements": [requirement], "trace_log": []})

    retrieved = result["retrieved"]["req_001"]
    assert [chunk.chunk_id for chunk in retrieved] == ["chunk_002", "chunk_001"]
    assert retrieved[0].score == 0.9
    assert retrieved[0].justification == "Justificación A."
    assert retrieved[1].justification == "Justificación B."
    assert len(result["trace_log"]) == 1
    assert result["trace_log"][0].node == "retrieve_chunks"
    assert result["trace_log"][0].duration_ms >= 0.0
    assert result["trace_log"][0].tokens.total_tokens == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_node_retrieve_chunks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph.nodes.retrieve_chunks'`.

- [ ] **Step 4: Write minimal implementation**

Create `algoworks-rfp-poc/backend/graph/nodes/retrieve_chunks.py`:

```python
"""Nodo retrieve_chunks: recupera chunks candidatos por similitud y genera
su justificación en lenguaje natural."""

import time
from datetime import datetime, timezone

from api.schemas import RetrievedChunk, TraceEvent
from graph.llm_tracking import TokenAccumulator, invoke_tracked
from graph.prompts import load_prompt
from graph.state import GraphState
from rag.store import similarity_search

DEFAULT_TOP_K = 3


def make_retrieve_chunks_node(llm, vectorstore, top_k: int = DEFAULT_TOP_K):
    prompt_template = load_prompt("retrieve_chunks_justification.txt")

    def retrieve_chunks(state: GraphState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()
        retrieved: dict[str, list[RetrievedChunk]] = {}

        for requirement in state["requirements"]:
            candidates = similarity_search(vectorstore, requirement.text, k=top_k)
            retrieved_for_requirement = []
            for chunk_id, chunk_text, score in candidates:
                justification_prompt = prompt_template.format(
                    requirement_text=requirement.text, chunk_text=chunk_text
                )
                justification = invoke_tracked(llm, justification_prompt, accumulator)
                retrieved_for_requirement.append(
                    RetrievedChunk(chunk_id=chunk_id, score=score, justification=justification)
                )
            retrieved[requirement.req_id] = retrieved_for_requirement

        trace_event = TraceEvent(
            node="retrieve_chunks",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(state['requirements'])} requisitos",
            output_summary=", ".join(
                f"{req_id}: {len(chunks)} chunks" for req_id, chunks in retrieved.items()
            ),
            reasoning=(
                f"Se recuperaron hasta {top_k} chunks por similitud coseno por "
                "requisito y se generó una justificación en lenguaje natural "
                "para cada uno."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "retrieved": retrieved,
            "trace_log": [*state["trace_log"], trace_event],
        }

    return retrieve_chunks
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_node_retrieve_chunks.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/nodes/retrieve_chunks.py algoworks-rfp-poc/backend/tests/fakes.py algoworks-rfp-poc/backend/tests/test_node_retrieve_chunks.py
git commit -m "feat: implement retrieve_chunks graph node"
```

---

## Task 10: Node — `generate_draft`

**Files:**
- Create: `algoworks-rfp-poc/backend/graph/nodes/generate_draft.py`
- Test: `algoworks-rfp-poc/backend/tests/test_node_generate_draft.py`

**Interfaces:**
- Consumes: `GraphState`, `load_prompt`, `DraftSection`/`TraceEvent` (from `api.schemas`), `TokenAccumulator`/`invoke_structured_tracked` (from `graph.llm_tracking`), `ScriptedChatModel` (from `tests.fakes`).
- Produces: `make_generate_draft_node(llm) -> Callable[[GraphState], dict]`. Reads `state["pending_req_ids"]`, `state["requirements"]`, `state["retrieved"]`, `state["drafts"]`, `state["hallucinated_citations"]`, `state["hallucination_catches"]`, `state["trace_log"]`; returns `{"drafts": ..., "hallucinated_citations": ..., "hallucination_catches": ..., "trace_log": ...}`. Consumed by Task 13.
- Uses structured output (`_DraftOutput`: `draft_text` + `reasoning`) via `invoke_structured_tracked` instead of plain-text `.invoke` (traceability spec §4.1) — `DraftSection.reasoning` is populated from the LLM's own explanation of which chunks it used and why.
- `hallucination_catches` is a running total across the whole pipeline run (unlike `hallucinated_citations`, which is overwritten per pass) — this node increments it by however many hallucinated `chunk_id`s it finds in *this* pass, on top of whatever value it received in state.

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_node_generate_draft.py`:

```python
"""Tests del nodo generate_draft: citación válida y detección de citas
alucinadas (chunk_id que no existe entre los chunks recuperados)."""

from types import SimpleNamespace

from api.schemas import Requirement, RetrievedChunk
from graph.nodes.generate_draft import make_generate_draft_node
from tests.fakes import ScriptedChatModel


def _state_for(req_id: str) -> dict:
    requirement = Requirement(req_id=req_id, text="Requisito de prueba.", section_target="experiencia_previa")
    retrieved_chunk = RetrievedChunk(chunk_id="chunk_001", score=0.9, justification="Relevante.")
    return {
        "requirements": [requirement],
        "retrieved": {req_id: [retrieved_chunk]},
        "pending_req_ids": [req_id],
        "drafts": {},
        "hallucinated_citations": {},
        "hallucination_catches": 0,
        "trace_log": [],
    }


def test_generate_draft_records_valid_citation():
    draft_output = SimpleNamespace(
        draft_text="Texto con cita [[chunk_001]].",
        reasoning="Se usó chunk_001 porque respalda directamente el requisito.",
    )
    llm = ScriptedChatModel(structured_responses=[draft_output])
    node = make_generate_draft_node(llm)

    result = node(_state_for("req_001"))

    draft = result["drafts"]["req_001"]
    assert draft.text == "Texto con cita [[chunk_001]]."
    assert draft.cited_chunks == ["chunk_001"]
    assert draft.reasoning == "Se usó chunk_001 porque respalda directamente el requisito."
    assert result["hallucinated_citations"]["req_001"] == []
    assert result["hallucination_catches"] == 0
    assert len(result["trace_log"]) == 1
    assert result["trace_log"][0].node == "generate_draft"
    assert result["trace_log"][0].duration_ms >= 0.0


def test_generate_draft_flags_hallucinated_citation_and_increments_running_total():
    draft_output = SimpleNamespace(
        draft_text="Texto con cita inventada [[chunk_099]].",
        reasoning="Se citó chunk_099.",
    )
    llm = ScriptedChatModel(structured_responses=[draft_output])
    node = make_generate_draft_node(llm)

    state = _state_for("req_001")
    state["hallucination_catches"] = 2  # ya venía de un pass anterior

    result = node(state)

    draft = result["drafts"]["req_001"]
    assert draft.cited_chunks == []
    assert result["hallucinated_citations"]["req_001"] == ["chunk_099"]
    assert result["hallucination_catches"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_node_generate_draft.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph.nodes.generate_draft'`.

- [ ] **Step 3: Write minimal implementation**

Create `algoworks-rfp-poc/backend/graph/nodes/generate_draft.py`:

```python
"""Nodo generate_draft: redacta el borrador de cada sección citando
chunk_id inline, y valida en código que las citas existan de verdad."""

import re
import time
from datetime import datetime, timezone

from pydantic import BaseModel

from api.schemas import DraftSection, RetrievedChunk, TraceEvent
from graph.llm_tracking import TokenAccumulator, invoke_structured_tracked
from graph.prompts import load_prompt
from graph.state import GraphState

_CITATION_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


class _DraftOutput(BaseModel):
    draft_text: str
    reasoning: str


def _build_chunks_block(chunks: list[RetrievedChunk]) -> str:
    return "\n".join(f"- {chunk.chunk_id}: {chunk.justification}" for chunk in chunks)


def make_generate_draft_node(llm):
    prompt_template = load_prompt("generate_draft.txt")

    def generate_draft(state: GraphState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()
        drafts = dict(state["drafts"])
        hallucinated_citations = dict(state["hallucinated_citations"])
        hallucination_catches = state["hallucination_catches"]
        requirements_by_id = {r.req_id: r for r in state["requirements"]}

        for req_id in state["pending_req_ids"]:
            requirement = requirements_by_id[req_id]
            retrieved_chunks = state["retrieved"].get(req_id, [])
            valid_chunk_ids = {chunk.chunk_id for chunk in retrieved_chunks}

            prompt = prompt_template.format(
                requirement_text=requirement.text,
                chunks_block=_build_chunks_block(retrieved_chunks),
            )
            output = invoke_structured_tracked(llm, _DraftOutput, prompt, accumulator)
            draft_text = output.draft_text.strip()

            cited_ids = list(dict.fromkeys(_CITATION_PATTERN.findall(draft_text)))
            valid_cited = [chunk_id for chunk_id in cited_ids if chunk_id in valid_chunk_ids]
            hallucinated = [chunk_id for chunk_id in cited_ids if chunk_id not in valid_chunk_ids]

            drafts[req_id] = DraftSection(
                req_id=req_id,
                text=draft_text,
                cited_chunks=valid_cited,
                reasoning=output.reasoning,
            )
            hallucinated_citations[req_id] = hallucinated
            hallucination_catches += len(hallucinated)

        trace_event = TraceEvent(
            node="generate_draft",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(state['pending_req_ids'])} requisitos a (re)generar",
            output_summary=(
                f"{len(state['pending_req_ids'])} DraftSection generados, "
                f"{sum(1 for ids in hallucinated_citations.values() if ids)} con citas alucinadas"
            ),
            reasoning=(
                "El post-procesamiento validó que cada chunk_id citado exista "
                "entre los chunks recuperados para ese requisito; los que no "
                "existen se registran como citas alucinadas para verify_citations."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "drafts": drafts,
            "hallucinated_citations": hallucinated_citations,
            "hallucination_catches": hallucination_catches,
            "trace_log": [*state["trace_log"], trace_event],
        }

    return generate_draft
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_node_generate_draft.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/nodes/generate_draft.py algoworks-rfp-poc/backend/tests/test_node_generate_draft.py
git commit -m "feat: implement generate_draft graph node"
```

---

## Task 11: Node — `verify_citations` + retry routing

**Files:**
- Create: `algoworks-rfp-poc/backend/graph/nodes/verify_citations.py`
- Test: `algoworks-rfp-poc/backend/tests/test_node_verify_citations.py`

**Interfaces:**
- Consumes: `GraphState`, `MAX_GENERATE_RETRIES` (from `graph.state`), `load_prompt`, `VerificationResult`/`TraceEvent` (from `api.schemas`), `TokenAccumulator`/`invoke_structured_tracked` (from `graph.llm_tracking`), `ScriptedChatModel`.
- Produces: `make_verify_citations_node(llm, max_retries: int = MAX_GENERATE_RETRIES) -> Callable[[GraphState], dict]` returning `{"verification": ..., "retry_counts": ..., "pending_req_ids": ..., "trace_log": ...}`, and `should_retry(state: GraphState) -> str` returning `"generate_draft"` or `"compute_traceability_metrics"` (updated from `"__end__"` per traceability spec §4.5, since the graph now has a terminal metrics/audit node). Both consumed by Task 13.
- Uses structured output (`_NliVerdict`: `supported` + `issues` + `confidence` + `reasoning`) via `invoke_structured_tracked`. `VerificationResult.reasoning` and `.retries_used` are new (traceability spec §4.2): when a requirement is auto-marked unsupported because of hallucinated citations (no LLM call made), `reasoning` is the fixed string `"No se llamó al LLM de verificación: se detectaron citas a chunk_id inexistentes antes de esta etapa."`; `retries_used` is always `retry_counts.get(req_id, 0)` **as read at the start of this node's pass, before any increment this pass might make** — 0 for a first-pass verdict, 1 for a verdict produced after one retry.

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_node_verify_citations.py`:

```python
"""Tests del nodo verify_citations: skip automático por cita alucinada,
verificación NLI vía LLM, y routing de reintento (máx. 1)."""

from types import SimpleNamespace

from api.schemas import DraftSection, RetrievedChunk
from graph.nodes.verify_citations import make_verify_citations_node, should_retry
from tests.fakes import ScriptedChatModel


def _base_state(req_id: str, draft: DraftSection, hallucinated: list[str], retry_count: int = 0) -> dict:
    return {
        "drafts": {req_id: draft},
        "hallucinated_citations": {req_id: hallucinated},
        "retrieved": {req_id: [RetrievedChunk(chunk_id="chunk_001", score=0.9, justification="Relevante.")]},
        "pending_req_ids": [req_id],
        "verification": {},
        "retry_counts": {req_id: retry_count},
        "trace_log": [],
    }


def test_hallucinated_citation_is_marked_unsupported_without_calling_llm():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_099]].", cited_chunks=[])
    node = make_verify_citations_node(ScriptedChatModel())

    result = node(_base_state("req_001", draft, hallucinated=["chunk_099"]))

    verification = result["verification"]["req_001"]
    assert verification.supported is False
    assert "chunk_099" in verification.issues[0]
    assert "no se llamó al llm" in verification.reasoning.lower()
    assert verification.retries_used == 0
    assert result["pending_req_ids"] == ["req_001"]
    assert result["retry_counts"]["req_001"] == 1


def test_supported_verdict_from_llm_clears_pending():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])
    verdict = SimpleNamespace(supported=True, issues=[], confidence=0.95, reasoning="El chunk respalda la afirmación.")
    node = make_verify_citations_node(ScriptedChatModel(structured_responses=[verdict]))

    result = node(_base_state("req_001", draft, hallucinated=[]))

    verification = result["verification"]["req_001"]
    assert verification.supported is True
    assert verification.reasoning == "El chunk respalda la afirmación."
    assert verification.retries_used == 0
    assert result["pending_req_ids"] == []
    assert result["retry_counts"]["req_001"] == 0


def test_unsupported_verdict_exhausts_retry_budget():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])
    verdict = SimpleNamespace(supported=False, issues=["no respalda la afirmación"], confidence=0.2, reasoning="No hay respaldo.")
    node = make_verify_citations_node(ScriptedChatModel(structured_responses=[verdict]), max_retries=1)

    result = node(_base_state("req_001", draft, hallucinated=[], retry_count=1))

    verification = result["verification"]["req_001"]
    assert verification.supported is False
    assert verification.retries_used == 1
    assert result["pending_req_ids"] == []


def test_should_retry_routes_to_generate_draft_when_pending():
    assert should_retry({"pending_req_ids": ["req_001"]}) == "generate_draft"


def test_should_retry_routes_to_compute_traceability_metrics_when_empty():
    assert should_retry({"pending_req_ids": []}) == "compute_traceability_metrics"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_node_verify_citations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph.nodes.verify_citations'`.

- [ ] **Step 3: Write minimal implementation**

Create `algoworks-rfp-poc/backend/graph/nodes/verify_citations.py`:

```python
"""Nodo verify_citations: verifica si cada borrador está respaldado por
sus citas, y decide si se reintenta generate_draft (máx. 1 vez)."""

import time
from datetime import datetime, timezone

from pydantic import BaseModel

from api.schemas import RetrievedChunk, TraceEvent, VerificationResult
from graph.llm_tracking import TokenAccumulator, invoke_structured_tracked
from graph.prompts import load_prompt
from graph.state import MAX_GENERATE_RETRIES, GraphState

_NO_LLM_CALL_REASONING = (
    "No se llamó al LLM de verificación: se detectaron citas a chunk_id "
    "inexistentes antes de esta etapa."
)


class _NliVerdict(BaseModel):
    supported: bool
    issues: list[str]
    confidence: float
    reasoning: str


def _build_chunks_block(cited_chunks: list[str], retrieved_chunks: list[RetrievedChunk]) -> str:
    chunk_by_id = {chunk.chunk_id: chunk for chunk in retrieved_chunks}
    lines = [
        f"- {chunk_id}: {chunk_by_id[chunk_id].justification}"
        for chunk_id in cited_chunks
        if chunk_id in chunk_by_id
    ]
    return "\n".join(lines)


def make_verify_citations_node(llm, max_retries: int = MAX_GENERATE_RETRIES):
    prompt_template = load_prompt("verify_citations.txt")

    def verify_citations(state: GraphState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()
        verification = dict(state["verification"])
        retry_counts = dict(state["retry_counts"])
        next_pending: list[str] = []

        for req_id in state["pending_req_ids"]:
            draft = state["drafts"][req_id]
            hallucinated = state["hallucinated_citations"].get(req_id, [])
            retries_used_so_far = retry_counts.get(req_id, 0)

            if hallucinated:
                result = VerificationResult(
                    req_id=req_id,
                    supported=False,
                    issues=[
                        f"El chunk_id '{chunk_id}' citado no existe entre los chunks recuperados."
                        for chunk_id in hallucinated
                    ],
                    confidence=0.0,
                    reasoning=_NO_LLM_CALL_REASONING,
                    retries_used=retries_used_so_far,
                )
            else:
                prompt = prompt_template.format(
                    draft_text=draft.text,
                    chunks_block=_build_chunks_block(draft.cited_chunks, state["retrieved"].get(req_id, [])),
                )
                verdict = invoke_structured_tracked(llm, _NliVerdict, prompt, accumulator)
                result = VerificationResult(
                    req_id=req_id,
                    supported=verdict.supported,
                    issues=verdict.issues,
                    confidence=verdict.confidence,
                    reasoning=verdict.reasoning,
                    retries_used=retries_used_so_far,
                )

            verification[req_id] = result

            if not result.supported and retries_used_so_far < max_retries:
                retry_counts[req_id] = retries_used_so_far + 1
                next_pending.append(req_id)

        trace_event = TraceEvent(
            node="verify_citations",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(state['pending_req_ids'])} borradores verificados",
            output_summary=(
                f"{sum(1 for r in verification.values() if r.supported)} soportados, "
                f"{len(next_pending)} enviados a reintento"
            ),
            reasoning=(
                "Los requisitos con citas alucinadas se marcan automáticamente "
                "como no soportados sin llamar al LLM; el resto se verifica con "
                "un prompt tipo NLI. Los no soportados con reintentos disponibles "
                f"vuelven a generate_draft (máx. {max_retries} reintento(s)); el "
                "resto queda marcado para revisión humana."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "verification": verification,
            "retry_counts": retry_counts,
            "pending_req_ids": next_pending,
            "trace_log": [*state["trace_log"], trace_event],
        }

    return verify_citations


def should_retry(state: GraphState) -> str:
    return "generate_draft" if state["pending_req_ids"] else "compute_traceability_metrics"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_node_verify_citations.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/nodes/verify_citations.py algoworks-rfp-poc/backend/tests/test_node_verify_citations.py
git commit -m "feat: implement verify_citations graph node and retry routing"
```

---

## Task 12: Node — `compute_traceability_metrics` (grounding similarity, path audit, metrics)

**Files:**
- Create: `algoworks-rfp-poc/backend/graph/nodes/compute_traceability_metrics.py`
- Test: `algoworks-rfp-poc/backend/tests/test_node_compute_traceability_metrics.py`

**Interfaces:**
- Consumes: `GraphState`, `MAX_GENERATE_RETRIES` (from `graph.state`), `CitationSimilarity`/`PipelineMetrics`/`ReasoningPathAudit`/`TokenUsage`/`TraceEvent` (from `api.schemas`), `FakeEmbeddings` (from `tests.fakes`, Task 3, test only).
- Produces: `cosine_similarity(a: list[float], b: list[float]) -> float` (pure function, no other caller in this plan but exposed for direct testing), `audit_reasoning_path(state: GraphState) -> ReasoningPathAudit` (pure function), `make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id: dict[str, str]) -> Callable[[GraphState], dict]`. Reads `state["drafts"]`, `state["retrieved"]`, `state["requirements"]`, `state["verification"]`, `state["retry_counts"]`, `state["hallucination_catches"]`, `state["trace_log"]`; returns `{"drafts": ..., "trace_log": ..., "metrics": ..., "reasoning_path_audit": ...}`. Consumed by Task 13.
- `chunk_texts_by_id` is a plain `dict[str, str]` mapping `chunk_id -> Chunk.text`, built once from `load_dummy_chunks()` (Task 1) by Task 15's `api/main.py` — see the Global Constraints note on why `RetrievedChunk` alone (no `text` field) isn't enough to compute real grounding similarity.
- Makes **no LLM calls** — pure code plus the `embeddings` model already used to build the vectorstore. Its own `TraceEvent.tokens` is always `None`.

**Behavior:**
1. For each `req_id` with a `DraftSection`: embed the full `draft.text` once; for each `chunk_id` in `draft.cited_chunks` that exists in both `state["retrieved"][req_id]` and `chunk_texts_by_id`, embed that chunk's real text and compute `cosine_similarity(draft_embedding, chunk_embedding)` → `CitationSimilarity`. `overall_similarity` is the cosine similarity between the draft embedding and the component-wise mean of the cited chunks' embeddings. No valid cited chunks → `citation_similarities = []`, `overall_similarity = 0.0`. Updated `DraftSection`s are built via `.model_copy(update={...})` (never mutated in place).
2. `audit_reasoning_path(state)` — a deterministic, non-LLM second opinion — checks: (a) `node_sequence = [event.node for event in state["trace_log"]]` matches `extract_requirements, retrieve_chunks, (generate_draft, verify_citations)+`; (b) every `retry_counts[req_id] <= MAX_GENERATE_RETRIES`; (c) every `chunk_id` in every `DraftSection.cited_chunks` exists in `state["retrieved"][req_id]` — this re-checks something `generate_draft` already guarantees, and that redundancy is the point (defense in depth, not "trust the node that already claims it validated this"); (d) every `req_id` in `state["verification"]` also appears in `state["requirements"]`. `is_consistent = len(issues) == 0`.
3. Aggregates `PipelineMetrics` from the final state: total duration/tokens summed across `trace_log`, `retries_used = sum(retry_counts.values())`, supported/needing-review counts from `verification`, and `hallucinated_citations_caught = state["hallucination_catches"]`.

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_node_compute_traceability_metrics.py`:

```python
"""Tests del nodo compute_traceability_metrics: similitud coseno
borrador<->chunks citados, auditoría determinista del camino de ejecución
del grafo (incluyendo un estado deliberadamente roto), y agregación de
métricas de todo el pipeline."""

from datetime import datetime, timezone

from api.schemas import DraftSection, Requirement, RetrievedChunk, TokenUsage, TraceEvent, VerificationResult
from graph.nodes.compute_traceability_metrics import (
    audit_reasoning_path,
    cosine_similarity,
    make_compute_traceability_metrics_node,
)
from tests.fakes import FakeEmbeddings

VOCABULARY = ["kafka", "retail", "manufactura"]


def test_cosine_similarity_of_identical_vectors_is_one():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_of_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_of_zero_vector_is_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def _trace_event(node: str, duration_ms: float = 10.0, tokens=None) -> TraceEvent:
    return TraceEvent(
        node=node,
        timestamp=datetime.now(timezone.utc),
        input_summary="...",
        output_summary="...",
        reasoning="...",
        duration_ms=duration_ms,
        tokens=tokens,
    )


def _valid_state() -> dict:
    requirement = Requirement(req_id="req_001", text="experiencia en kafka", section_target="capacidades_tecnicas")
    retrieved_chunk = RetrievedChunk(chunk_id="chunk_001", score=0.9, justification="Relevante para kafka.")
    draft = DraftSection(req_id="req_001", text="Usamos kafka en el proyecto [[chunk_001]].", cited_chunks=["chunk_001"])
    verification = VerificationResult(req_id="req_001", supported=True, issues=[], confidence=0.9)

    return {
        "requirements": [requirement],
        "retrieved": {"req_001": [retrieved_chunk]},
        "drafts": {"req_001": draft},
        "verification": {"req_001": verification},
        "retry_counts": {"req_001": 0},
        "hallucination_catches": 0,
        "trace_log": [
            _trace_event("extract_requirements"),
            _trace_event("retrieve_chunks"),
            _trace_event("generate_draft", tokens=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)),
            _trace_event("verify_citations"),
        ],
    }


def test_audit_reasoning_path_returns_consistent_for_valid_single_pass_sequence():
    audit = audit_reasoning_path(_valid_state())

    assert audit.is_consistent is True
    assert audit.issues == []
    assert audit.node_sequence == [
        "extract_requirements", "retrieve_chunks", "generate_draft", "verify_citations",
    ]


def test_audit_reasoning_path_returns_consistent_for_a_valid_retry_sequence():
    state = _valid_state()
    state["trace_log"] = [
        _trace_event("extract_requirements"),
        _trace_event("retrieve_chunks"),
        _trace_event("generate_draft"),
        _trace_event("verify_citations"),
        _trace_event("generate_draft"),
        _trace_event("verify_citations"),
    ]

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is True


def test_audit_reasoning_path_flags_broken_node_sequence():
    state = _valid_state()
    state["trace_log"] = [_trace_event("extract_requirements"), _trace_event("generate_draft")]

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is False
    assert len(audit.issues) == 1


def test_audit_reasoning_path_flags_retries_beyond_the_configured_maximum():
    state = _valid_state()
    state["retry_counts"] = {"req_001": 5}

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is False
    assert any("req_001" in issue for issue in audit.issues)


def test_audit_reasoning_path_flags_hallucinated_citation_slipping_through():
    state = _valid_state()
    state["drafts"]["req_001"] = state["drafts"]["req_001"].model_copy(update={"cited_chunks": ["chunk_099"]})

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is False
    assert any("chunk_099" in issue for issue in audit.issues)


def test_audit_reasoning_path_flags_orphaned_verification_result():
    state = _valid_state()
    state["verification"]["req_999"] = VerificationResult(req_id="req_999", supported=True, issues=[], confidence=0.5)

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is False
    assert any("req_999" in issue for issue in audit.issues)


def test_compute_traceability_metrics_node_aggregates_metrics_and_attaches_similarities():
    embeddings = FakeEmbeddings(VOCABULARY)
    chunk_texts_by_id = {"chunk_001": "Arquitectura basada en kafka."}
    node = make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id)

    result = node(_valid_state())

    draft = result["drafts"]["req_001"]
    assert draft.citation_similarities[0].chunk_id == "chunk_001"
    assert draft.citation_similarities[0].similarity == 1.0
    assert draft.overall_similarity == 1.0

    metrics = result["metrics"]
    assert metrics.requirements_supported == 1
    assert metrics.requirements_needing_review == 0
    assert metrics.total_tokens.total_tokens == 15
    assert metrics.hallucinated_citations_caught == 0
    assert metrics.retries_used == 0

    assert result["reasoning_path_audit"].is_consistent is True
    assert result["trace_log"][-1].node == "compute_traceability_metrics"
    assert result["trace_log"][-1].tokens is None


def test_compute_traceability_metrics_node_skips_similarity_when_no_valid_citations():
    embeddings = FakeEmbeddings(VOCABULARY)
    node = make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id={})

    result = node(_valid_state())

    draft = result["drafts"]["req_001"]
    assert draft.citation_similarities == []
    assert draft.overall_similarity == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_node_compute_traceability_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph.nodes.compute_traceability_metrics'`.

- [ ] **Step 3: Write minimal implementation**

Create `algoworks-rfp-poc/backend/graph/nodes/compute_traceability_metrics.py`:

```python
"""Nodo compute_traceability_metrics: corre una sola vez, cuando el retry
loop se vació. Calcula similitud coseno borrador<->chunks citados, audita
de forma determinista (sin LLM) el camino de ejecución del grafo, y agrega
las métricas de todo el pipeline (latencia, tokens, reintentos)."""

import math
import time
from datetime import datetime, timezone

from api.schemas import (
    CitationSimilarity,
    DraftSection,
    PipelineMetrics,
    ReasoningPathAudit,
    TokenUsage,
    TraceEvent,
)
from graph.state import MAX_GENERATE_RETRIES, GraphState


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    length = len(vectors[0])
    return [sum(vector[i] for vector in vectors) / len(vectors) for i in range(length)]


def _compute_draft_similarities(
    draft: DraftSection,
    retrieved_chunks,
    chunk_texts_by_id: dict[str, str],
    embeddings,
) -> tuple[list[CitationSimilarity], float]:
    valid_chunk_ids = {chunk.chunk_id for chunk in retrieved_chunks}
    valid_cited = [
        chunk_id
        for chunk_id in draft.cited_chunks
        if chunk_id in valid_chunk_ids and chunk_id in chunk_texts_by_id
    ]
    if not valid_cited:
        return [], 0.0

    draft_embedding = embeddings.embed_query(draft.text)
    citation_similarities: list[CitationSimilarity] = []
    chunk_embeddings: list[list[float]] = []
    for chunk_id in valid_cited:
        chunk_embedding = embeddings.embed_query(chunk_texts_by_id[chunk_id])
        chunk_embeddings.append(chunk_embedding)
        citation_similarities.append(
            CitationSimilarity(chunk_id=chunk_id, similarity=cosine_similarity(draft_embedding, chunk_embedding))
        )

    overall_similarity = cosine_similarity(draft_embedding, _mean_vector(chunk_embeddings))
    return citation_similarities, overall_similarity


def audit_reasoning_path(state: GraphState) -> ReasoningPathAudit:
    node_sequence = [event.node for event in state["trace_log"]]
    issues: list[str] = []

    expected_prefix = ["extract_requirements", "retrieve_chunks"]
    body = node_sequence[len(expected_prefix):]
    valid_shape = (
        node_sequence[: len(expected_prefix)] == expected_prefix
        and len(body) >= 2
        and len(body) % 2 == 0
        and body[-1] == "verify_citations"
        and all(
            body[i] == "generate_draft" and body[i + 1] == "verify_citations"
            for i in range(0, len(body), 2)
        )
    )
    if not valid_shape:
        issues.append(
            f"La secuencia de nodos {node_sequence} no sigue el patrón esperado "
            "extract_requirements, retrieve_chunks, (generate_draft, verify_citations)+."
        )

    for req_id, retries in state["retry_counts"].items():
        if retries > MAX_GENERATE_RETRIES:
            issues.append(
                f"El requisito {req_id} usó {retries} reintentos, más que el "
                f"máximo permitido ({MAX_GENERATE_RETRIES})."
            )

    for req_id, draft in state["drafts"].items():
        valid_chunk_ids = {chunk.chunk_id for chunk in state["retrieved"].get(req_id, [])}
        for chunk_id in draft.cited_chunks:
            if chunk_id not in valid_chunk_ids:
                issues.append(
                    f"El draft de {req_id} cita chunk_id '{chunk_id}', que no "
                    "existe entre los chunks recuperados para ese requisito."
                )

    requirement_ids = {requirement.req_id for requirement in state["requirements"]}
    for req_id in state["verification"]:
        if req_id not in requirement_ids:
            issues.append(
                f"Hay un VerificationResult para req_id '{req_id}', que no "
                "aparece entre los requisitos extraídos."
            )

    return ReasoningPathAudit(is_consistent=len(issues) == 0, node_sequence=node_sequence, issues=issues)


def make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id: dict[str, str]):
    def compute_traceability_metrics(state: GraphState) -> dict:
        started_at = time.perf_counter()

        drafts = dict(state["drafts"])
        for req_id, draft in drafts.items():
            retrieved_chunks = state["retrieved"].get(req_id, [])
            citation_similarities, overall_similarity = _compute_draft_similarities(
                draft, retrieved_chunks, chunk_texts_by_id, embeddings
            )
            drafts[req_id] = draft.model_copy(
                update={"citation_similarities": citation_similarities, "overall_similarity": overall_similarity}
            )

        reasoning_path_audit = audit_reasoning_path(state)

        total_tokens = TokenUsage(
            input_tokens=sum(event.tokens.input_tokens for event in state["trace_log"] if event.tokens),
            output_tokens=sum(event.tokens.output_tokens for event in state["trace_log"] if event.tokens),
            total_tokens=sum(event.tokens.total_tokens for event in state["trace_log"] if event.tokens),
            estimated_cost_usd=sum(event.tokens.estimated_cost_usd for event in state["trace_log"] if event.tokens),
        )
        metrics = PipelineMetrics(
            total_duration_ms=sum(event.duration_ms for event in state["trace_log"]),
            total_tokens=total_tokens,
            retries_used=sum(state["retry_counts"].values()),
            requirements_supported=sum(1 for v in state["verification"].values() if v.supported),
            requirements_needing_review=sum(1 for v in state["verification"].values() if not v.supported),
            hallucinated_citations_caught=state["hallucination_catches"],
        )

        trace_event = TraceEvent(
            node="compute_traceability_metrics",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(drafts)} borradores finales, {len(state['trace_log'])} eventos de trace previos",
            output_summary=(
                f"{metrics.requirements_supported}/{len(state['verification'])} requisitos soportados, "
                f"{metrics.hallucinated_citations_caught} citas alucinadas detectadas en total"
            ),
            reasoning=(
                "Auditoría determinista (sin LLM) de la secuencia de nodos y las "
                "citas, más similitud coseno borrador<->chunks citados: camino "
                f"{'consistente' if reasoning_path_audit.is_consistent else 'con problemas'}."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=None,
        )

        return {
            "drafts": drafts,
            "trace_log": [*state["trace_log"], trace_event],
            "metrics": metrics,
            "reasoning_path_audit": reasoning_path_audit,
        }

    return compute_traceability_metrics
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_node_compute_traceability_metrics.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/nodes/compute_traceability_metrics.py algoworks-rfp-poc/backend/tests/test_node_compute_traceability_metrics.py
git commit -m "feat: implement compute_traceability_metrics graph node"
```

---

## Task 13: Graph assembly (`build_graph` + `run_pipeline`)

**Files:**
- Modify: `algoworks-rfp-poc/backend/graph/graph.py`
- Test: `algoworks-rfp-poc/backend/tests/test_graph.py`

**Interfaces:**
- Consumes: all `make_*_node` factories and `should_retry` (Tasks 8-12), `GraphState` (Task 5), `PipelineResult` (from `api.schemas`).
- Produces: `build_graph(llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id: dict[str, str], top_k: int = 3) -> CompiledStateGraph` and `run_pipeline(rfp_id: str, rfp_text: str, llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id: dict[str, str], top_k: int = 3) -> PipelineResult`. Both gain the `embeddings`/`chunk_texts_by_id` parameters (traceability spec §4.5) needed by `compute_traceability_metrics`. Consumed by Task 15 (`api/main.py`).

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_graph.py`:

```python
"""Test de integración del grafo completo: camino feliz (todo soportado a
la primera) y camino adversarial (falla, 1 reintento, sigue sin soportarse
y queda marcado para revisión humana)."""

from types import SimpleNamespace

from graph.graph import run_pipeline
from tests.fakes import FakeEmbeddings, FakeVectorstore, ScriptedChatModel

VOCABULARY = ["experiencia", "kafka"]


def _vectorstore_for(requirement_text: str, chunk_id: str, chunk_text: str) -> FakeVectorstore:
    return FakeVectorstore({requirement_text: [(chunk_id, chunk_text, 0.9)]})


def test_run_pipeline_happy_path_supports_on_first_try():
    extracted = SimpleNamespace(
        requirements=[SimpleNamespace(req_id="req_001", text="experiencia previa", section_target="experiencia_previa")]
    )
    draft_output = SimpleNamespace(draft_text="Texto [[chunk_001]].", reasoning="Se citó el chunk más relevante.")
    verdict = SimpleNamespace(supported=True, issues=[], confidence=0.9, reasoning="El chunk respalda la afirmación.")

    llm_small = ScriptedChatModel(structured_responses=[extracted], plain_responses=["Justificación."])
    llm_large = ScriptedChatModel(structured_responses=[draft_output, verdict])
    vectorstore = _vectorstore_for("experiencia previa", "chunk_001", "Texto de referencia.")
    embeddings = FakeEmbeddings(VOCABULARY)
    chunk_texts_by_id = {"chunk_001": "Texto de referencia con experiencia."}

    result = run_pipeline(
        "rfp_001", "1. experiencia previa", llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id
    )

    assert result.rfp_id == "rfp_001"
    assert result.verification["req_001"].supported is True
    assert result.metrics.requirements_supported == 1
    assert result.reasoning_path_audit.is_consistent is True
    nodes = [event.node for event in result.trace_log]
    assert nodes == [
        "extract_requirements",
        "retrieve_chunks",
        "generate_draft",
        "verify_citations",
        "compute_traceability_metrics",
    ]


def test_run_pipeline_retries_once_then_gives_up():
    extracted = SimpleNamespace(
        requirements=[SimpleNamespace(req_id="req_001", text="experiencia previa", section_target="experiencia_previa")]
    )
    draft_output_1 = SimpleNamespace(draft_text="Texto [[chunk_001]].", reasoning="Primer intento.")
    draft_output_2 = SimpleNamespace(draft_text="Texto [[chunk_001]] revisado.", reasoning="Segundo intento.")
    unsupported = SimpleNamespace(
        supported=False, issues=["no respalda la afirmación"], confidence=0.1, reasoning="No hay respaldo suficiente."
    )

    llm_small = ScriptedChatModel(structured_responses=[extracted], plain_responses=["Justificación."])
    llm_large = ScriptedChatModel(structured_responses=[draft_output_1, unsupported, draft_output_2, unsupported])
    vectorstore = _vectorstore_for("experiencia previa", "chunk_001", "Texto de referencia.")
    embeddings = FakeEmbeddings(VOCABULARY)
    chunk_texts_by_id = {"chunk_001": "Texto de referencia con experiencia."}

    result = run_pipeline(
        "rfp_001", "1. experiencia previa", llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id
    )

    assert result.verification["req_001"].supported is False
    assert result.verification["req_001"].retries_used == 1
    assert result.metrics.retries_used == 1
    nodes = [event.node for event in result.trace_log]
    assert nodes == [
        "extract_requirements",
        "retrieve_chunks",
        "generate_draft",
        "verify_citations",
        "generate_draft",
        "verify_citations",
        "compute_traceability_metrics",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_graph.py -v`
Expected: FAIL — `graph/graph.py` currently has no `run_pipeline`/`build_graph` (only a placeholder docstring), so `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Replace the contents of `algoworks-rfp-poc/backend/graph/graph.py`:

```python
"""Construye y compila el grafo LangGraph del pipeline de RFP:
extract_requirements -> retrieve_chunks -> generate_draft -> verify_citations
-> compute_traceability_metrics, con reintento condicional de
verify_citations a generate_draft (max. 1)."""

from langgraph.graph import END, StateGraph

from api.schemas import PipelineResult
from graph.nodes.compute_traceability_metrics import make_compute_traceability_metrics_node
from graph.nodes.extract_requirements import make_extract_requirements_node
from graph.nodes.generate_draft import make_generate_draft_node
from graph.nodes.retrieve_chunks import make_retrieve_chunks_node
from graph.nodes.verify_citations import make_verify_citations_node, should_retry
from graph.state import GraphState

DEFAULT_TOP_K = 3


def build_graph(
    llm_small,
    llm_large,
    vectorstore,
    embeddings,
    chunk_texts_by_id: dict[str, str],
    top_k: int = DEFAULT_TOP_K,
):
    graph = StateGraph(GraphState)
    graph.add_node("extract_requirements", make_extract_requirements_node(llm_small))
    graph.add_node("retrieve_chunks", make_retrieve_chunks_node(llm_small, vectorstore, top_k))
    graph.add_node("generate_draft", make_generate_draft_node(llm_large))
    graph.add_node("verify_citations", make_verify_citations_node(llm_large))
    graph.add_node(
        "compute_traceability_metrics",
        make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id),
    )

    graph.set_entry_point("extract_requirements")
    graph.add_edge("extract_requirements", "retrieve_chunks")
    graph.add_edge("retrieve_chunks", "generate_draft")
    graph.add_edge("generate_draft", "verify_citations")
    graph.add_conditional_edges(
        "verify_citations",
        should_retry,
        {"generate_draft": "generate_draft", "compute_traceability_metrics": "compute_traceability_metrics"},
    )
    graph.add_edge("compute_traceability_metrics", END)
    return graph.compile()


def run_pipeline(
    rfp_id: str,
    rfp_text: str,
    llm_small,
    llm_large,
    vectorstore,
    embeddings,
    chunk_texts_by_id: dict[str, str],
    top_k: int = DEFAULT_TOP_K,
) -> PipelineResult:
    compiled_graph = build_graph(llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id, top_k)
    initial_state: GraphState = {
        "rfp_id": rfp_id,
        "rfp_text": rfp_text,
        "requirements": [],
        "retrieved": {},
        "pending_req_ids": [],
        "hallucinated_citations": {},
        "hallucination_catches": 0,
        "drafts": {},
        "verification": {},
        "retry_counts": {},
        "trace_log": [],
        "metrics": None,
        "reasoning_path_audit": None,
    }
    final_state = compiled_graph.invoke(initial_state)
    return PipelineResult(
        rfp_id=rfp_id,
        requirements=final_state["requirements"],
        retrieved=final_state["retrieved"],
        drafts=final_state["drafts"],
        verification=final_state["verification"],
        trace_log=final_state["trace_log"],
        metrics=final_state["metrics"],
        reasoning_path_audit=final_state["reasoning_path_audit"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_graph.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/graph.py algoworks-rfp-poc/backend/tests/test_graph.py
git commit -m "feat: assemble the LangGraph pipeline with the retry loop and metrics node"
```

---

## Task 14: LLM provider — Groq primary, Ollama fallback

**Files:**
- Create: `algoworks-rfp-poc/backend/graph/llm.py`
- Test: `algoworks-rfp-poc/backend/tests/test_llm.py`

**Interfaces:**
- Produces: `FallbackChatModel(primary, fallback)` (with `.invoke` and `.with_structured_output(schema, include_raw=False)`, matching the duck-typed interface every node's `invoke_tracked`/`invoke_structured_tracked` call expects) and `get_chat_llm(size: Literal["small", "large"]) -> FallbackChatModel`. Consumed by Task 15 (`api/main.py`) — no other task depends on this module, since all node/graph tests use `ScriptedChatModel` instead.
- `with_structured_output` must accept and forward `include_raw` to both the primary and fallback model, since `graph.llm_tracking.invoke_structured_tracked` (Task 7) always calls it with `include_raw=True` to recover token usage — real `ChatGroq`/`ChatOllama` instances support this kwarg natively.

- [ ] **Step 1: Write the failing test**

Create `algoworks-rfp-poc/backend/tests/test_llm.py`:

```python
"""Tests del wrapper de fallback Groq -> Ollama. No hace llamadas reales:
usa dobles locales que pueden simular una falla del proveedor principal."""

from types import SimpleNamespace

import pytest

from graph.llm import FallbackChatModel, get_chat_llm


class _FailingLLM:
    def invoke(self, prompt):
        raise RuntimeError("sin conectividad")

    def with_structured_output(self, schema, include_raw: bool = False):
        raise RuntimeError("sin conectividad")


class _OkLLM:
    def __init__(self, label: str):
        self._label = label
        self.calls = 0
        self.received_include_raw = None

    def invoke(self, prompt):
        self.calls += 1
        return SimpleNamespace(content=self._label)

    def with_structured_output(self, schema, include_raw: bool = False):
        self.received_include_raw = include_raw
        parent = self

        class _Structured:
            def invoke(self, prompt):
                parent.calls += 1
                return SimpleNamespace(label=parent._label)

        return _Structured()


def test_invoke_uses_primary_when_it_succeeds():
    primary = _OkLLM("primary")
    fallback = _OkLLM("fallback")
    model = FallbackChatModel(primary, fallback)

    response = model.invoke("prompt")

    assert response.content == "primary"
    assert primary.calls == 1
    assert fallback.calls == 0


def test_invoke_falls_back_when_primary_raises():
    model = FallbackChatModel(_FailingLLM(), _OkLLM("fallback"))

    response = model.invoke("prompt")

    assert response.content == "fallback"


def test_with_structured_output_falls_back_when_primary_raises():
    model = FallbackChatModel(_FailingLLM(), _OkLLM("fallback"))

    response = model.with_structured_output(object).invoke("prompt")

    assert response.label == "fallback"


def test_with_structured_output_forwards_include_raw_to_both_models():
    primary = _OkLLM("primary")
    fallback = _OkLLM("fallback")
    model = FallbackChatModel(primary, fallback)

    model.with_structured_output(object, include_raw=True)

    assert primary.received_include_raw is True


def test_get_chat_llm_builds_groq_primary_and_ollama_fallback(monkeypatch):
    captured = {}

    class _FakeChatGroq:
        def __init__(self, model, api_key=None):
            captured["groq_model"] = model

    class _FakeChatOllama:
        def __init__(self, model, base_url=None):
            captured["ollama_model"] = model

    monkeypatch.setattr("graph.llm.ChatGroq", _FakeChatGroq)
    monkeypatch.setattr("graph.llm.ChatOllama", _FakeChatOllama)
    monkeypatch.setenv("GROQ_MODEL_SMALL", "test-small-model")

    llm = get_chat_llm("small")

    assert isinstance(llm, FallbackChatModel)
    assert captured["groq_model"] == "test-small-model"
    assert "ollama_model" in captured
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph.llm'`.

- [ ] **Step 3: Write minimal implementation**

Create `algoworks-rfp-poc/backend/graph/llm.py`:

```python
"""Provee el LLM de chat: Groq como proveedor principal, Ollama local como
fallback si falla la conectividad (CLAUDE.md, secciones 2 y 6)."""

import os
from typing import Literal

from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama


class FallbackChatModel:
    """Intenta el modelo principal (Groq); si falla, reintenta con el de
    fallback (Ollama local)."""

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    def invoke(self, prompt):
        try:
            return self._primary.invoke(prompt)
        except Exception:
            return self._fallback.invoke(prompt)

    def with_structured_output(self, schema, include_raw: bool = False):
        return _FallbackStructuredRunnable(
            self._primary.with_structured_output(schema, include_raw=include_raw),
            self._fallback.with_structured_output(schema, include_raw=include_raw),
        )


class _FallbackStructuredRunnable:
    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    def invoke(self, prompt):
        try:
            return self._primary.invoke(prompt)
        except Exception:
            return self._fallback.invoke(prompt)


def get_chat_llm(size: Literal["small", "large"]) -> FallbackChatModel:
    groq_model = (
        os.environ.get("GROQ_MODEL_SMALL", "llama-3.1-8b-instant")
        if size == "small"
        else os.environ.get("GROQ_MODEL_LARGE", "llama-3.3-70b-versatile")
    )
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1")
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    primary = ChatGroq(model=groq_model, api_key=os.environ.get("GROQ_API_KEY"))
    fallback = ChatOllama(model=ollama_model, base_url=ollama_base_url)
    return FallbackChatModel(primary, fallback)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_llm.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add algoworks-rfp-poc/backend/graph/llm.py algoworks-rfp-poc/backend/tests/test_llm.py
git commit -m "feat: add Groq primary / Ollama fallback chat model provider"
```

---

## Task 15: Wire the real pipeline into the API

**Files:**
- Modify: `algoworks-rfp-poc/backend/api/main.py`
- Modify: `algoworks-rfp-poc/backend/tests/test_api.py`

**Interfaces:**
- Consumes: `run_pipeline` (Task 13), `get_chat_llm` (Task 14), `load_dummy_chunks` (Task 1), `SentenceTransformerEmbeddings` (Task 2), `build_vectorstore` (Task 3).
- Produces: `get_pipeline_runner() -> Callable[[str, str], PipelineResult]` FastAPI dependency on `POST /rfp/process`, overridden in tests via `app.dependency_overrides`.

This task removes `_build_mock_pipeline_result` from `main.py` (the `# TODO: reemplazar por invocación real del grafo LangGraph` is now resolved) and must update `test_api.py` in the same commit, since the existing tests would otherwise try to build a real Groq/Ollama/Chroma pipeline and fail without credentials/network. The corpus is loaded once and reused both to build the vectorstore and to build the `chunk_texts_by_id` lookup `compute_traceability_metrics` needs (see Task 12 and the Global Constraints note).

- [ ] **Step 1: Write the failing test**

Replace the contents of `algoworks-rfp-poc/backend/tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_pipeline_runner' from 'api.main'` (it doesn't exist yet).

- [ ] **Step 3: Write minimal implementation**

In `algoworks-rfp-poc/backend/api/main.py`:

1. Update the imports block to add:

```python
from functools import lru_cache
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request

from graph.graph import run_pipeline
from graph.llm import get_chat_llm
from rag.corpus import load_dummy_chunks
from rag.embed import SentenceTransformerEmbeddings
from rag.store import build_vectorstore
```

(keep the existing `logging`, `http.HTTPStatus`, `fastapi.exceptions.RequestValidationError`, `fastapi.middleware.cors.CORSMiddleware`, `fastapi.responses.JSONResponse`, `pydantic.BaseModel`, `starlette.exceptions.HTTPException as StarletteHTTPException`, and `api.schemas` imports as they are — the `datetime`/`timezone` import and the whole `_build_mock_pipeline_result` function are removed in this task, since only that function used them.)

2. Delete the entire `_build_mock_pipeline_result` function (from its `def _build_mock_pipeline_result(rfp_id: str) -> PipelineResult:` line through its closing `return PipelineResult(...)` block).

3. In its place, add:

```python
PipelineRunner = Callable[[str, str], PipelineResult]


@lru_cache(maxsize=1)
def _get_corpus_resources():
    chunks = load_dummy_chunks()
    embeddings = SentenceTransformerEmbeddings()
    vectorstore = build_vectorstore(chunks, embeddings)
    chunk_texts_by_id = {chunk.chunk_id: chunk.text for chunk in chunks}
    return vectorstore, embeddings, chunk_texts_by_id


def _default_pipeline_runner(rfp_id: str, rfp_text: str) -> PipelineResult:
    llm_small = get_chat_llm("small")
    llm_large = get_chat_llm("large")
    vectorstore, embeddings, chunk_texts_by_id = _get_corpus_resources()
    return run_pipeline(rfp_id, rfp_text, llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id)


def get_pipeline_runner() -> PipelineRunner:
    return _default_pipeline_runner
```

4. Update the `/rfp/process` route to use the dependency:

```python
@app.post("/rfp/process", response_model=PipelineResult)
def process_rfp(
    payload: RFPProcessRequest,
    pipeline_runner: PipelineRunner = Depends(get_pipeline_runner),
) -> PipelineResult:
    result = pipeline_runner(payload.rfp_id, payload.rfp_text)
    _pipeline_results[payload.rfp_id] = result
    return result
```

Leave `GET /health`, `GET /rfp/{rfp_id}/trace`, `POST /rfp/{req_id}/feedback`, the exception handlers, `RFPProcessRequest`, `FeedbackRequest`, and `_pipeline_results` exactly as they are.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the full backend test suite**

Run: `uv run pytest -v`
Expected: every test across `test_schemas.py`, `test_corpus.py`, `test_embed.py`, `test_store.py`, `test_prompts.py`, `test_llm_tracking.py`, `test_node_*.py`, `test_graph.py`, `test_llm.py`, `test_api.py` passes.

- [ ] **Step 6: Commit**

```bash
git add algoworks-rfp-poc/backend/api/main.py algoworks-rfp-poc/backend/tests/test_api.py
git commit -m "feat: wire the real LangGraph pipeline into POST /rfp/process"
```

---

## Post-implementation manual check (not automated)

Once `GROQ_API_KEY` is set (and, optionally, a local Ollama with the configured model pulled for offline fallback testing), do one real end-to-end run to sanity-check prompt quality and latency — this cannot be covered by the hermetic test suite above:

```bash
uv run uvicorn api.main:app --reload --port 8000
curl -X POST http://localhost:8000/rfp/process \
  -H "Content-Type: application/json" \
  -d '{"rfp_id": "rfp_manual_001", "rfp_text": "1. El proveedor debe demostrar experiencia previa en integración de datos.\n2. El proveedor debe describir su arquitectura para datos en tiempo real."}'
curl http://localhost:8000/rfp/rfp_manual_001/trace
```

Check that: `drafts[*].text` actually contains `[[chunk_id]]` markers that resolve to real corpus chunks, `drafts[*].reasoning` reads as a genuine explanation of chunk choice, `verification` reflects genuine NLI judgments (not always `true`), `drafts[*].overall_similarity` / `citation_similarities` look sane (high for well-grounded drafts, noticeably lower for the adversarial case), `metrics.total_tokens`/`total_duration_ms` are non-zero and roughly plausible, `reasoning_path_audit.is_consistent` is `true`, and `trace_log[*].reasoning` reads as a believable explanation — this is the traceability/explainability narrative the hackathon judges will be shown.

---

## Self-Review Notes

- **Spec coverage:** `extract_requirements` structured-output + numbered-line fallback (Task 8), `retrieve_chunks` embeddings+cosine+justification (Tasks 2/3/9), `generate_draft` citation + hallucination post-processing + structured `reasoning` (Task 10), `verify_citations` NLI + `reasoning`/`retries_used` + 1-retry conditional edge (Task 11/13), `compute_traceability_metrics` grounding similarity + path audit + metrics aggregation (Task 12), per-node `TraceEvent` with real `duration_ms`/`tokens` (every node task via Task 7's tracking helpers), prompts as versioned `.txt` files with explicit reasoning instructions (Task 6), the additive schema extension (Task 4), Groq+Ollama fallback with `include_raw` support (Task 14), dummy corpus (Task 1), API wiring replacing the mock and threading `embeddings`/`chunk_texts_by_id` through (Task 15) — all covered. The `RetrievedChunk`-has-no-`text` gap between the traceability spec's literal wording and the frozen schema is called out and resolved in Global Constraints and Task 12.
- **Placeholder scan:** no `TBD`/`implement later` markers; every step has real, runnable code.
- **Type consistency checked:** `GraphState` fields (Task 5) match exactly what every node reads/returns (Tasks 8-12) and what `run_pipeline`'s initial state sets (Task 13); `make_*_node` factory names and `should_retry` (now routing to `"compute_traceability_metrics"`) are used identically in `graph.py`; `ScriptedChatModel`/`FakeVectorstore`/`FakeEmbeddings` are defined once in `tests/fakes.py` (Tasks 3/8/9) and imported by name everywhere else, with `ScriptedChatModel.with_structured_output`'s `include_raw` branch matching the `{"raw", "parsed", "parsing_error"}` shape `invoke_structured_tracked` (Task 7) expects; `_DraftOutput`/`_NliVerdict` field names (`draft_text`/`reasoning`, `supported`/`issues`/`confidence`/`reasoning`) match what Tasks 10/11 read off the parsed result; `get_pipeline_runner`/`PipelineRunner` names match between `main.py` and `test_api.py` (Task 15); `build_graph`/`run_pipeline` signatures (Task 13) match the call site in `_default_pipeline_runner` (Task 15) and in `test_graph.py`.

