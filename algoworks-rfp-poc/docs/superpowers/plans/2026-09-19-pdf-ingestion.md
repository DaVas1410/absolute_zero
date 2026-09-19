# PDF Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the RAG pipeline ingest PDFs on both sides — PDF proposals into the citable knowledge corpus, and a PDF as the incoming RFP — so the demo can show a real vector space being built from real documents instead of hand-written JSON.

**Architecture:** A shared `backend/rag/pdf_ingest.py` utility (pypdf extraction + LangChain `RecursiveCharacterTextSplitter` chunking) feeds two new, fully additive FastAPI endpoints: `POST /corpus/ingest` (mutates the live Chroma singleton + persists to a new `ingested_chunks.json`) and `POST /rfp/process/pdf` (extracts text, then reuses the existing pipeline runner unchanged).

**Tech Stack:** pypdf, langchain-text-splitters, python-multipart (new deps); fpdf2 (new dev dep, for generating test-fixture PDFs in-memory).

**Spec:** `docs/superpowers/specs/2026-09-19-pdf-ingestion-design.md`

## Global Constraints

- No system dependencies (no poppler/tesseract) — pure-Python PDF handling only.
- `POST /rfp/process` (JSON) and every existing schema field must keep working unchanged — all changes are additive (spec §1).
- `section_type`/`section_target` must be validated against the single closed enum `("experiencia_previa", "capacidades_tecnicas", "equipo")` — one source of truth in `api/schemas.py` (spec §2).
- Chunking: `RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=120)` (spec §2).
- `chunk_id` format: `f"{slugify(source)}_{i:03d}"`, 1-indexed (spec §2).
- Tests must not hit the network or download real models — use `FakeEmbeddings`/`build_vectorstore` (real Chroma, fake embeddings) exactly as `backend/tests/test_store.py` already does, and override FastAPI dependencies for anything touching the pipeline runner or corpus resources, exactly as `backend/tests/test_api.py` already does.

---

### Task 1: Shared `SectionType` enum + `CorpusIngestResult` schema

**Files:**
- Modify: `backend/api/schemas.py`
- Modify: `backend/graph/nodes/extract_requirements.py:15,23`
- Test: `backend/tests/test_schemas.py`

**Interfaces:**
- Produces: `api.schemas.SECTION_TYPES: tuple[str, ...]`, `api.schemas.SectionType` (a `Literal` type alias), `api.schemas.CorpusIngestResult(BaseModel)` with fields `source: str`, `section_type: str`, `chunks_added: list[Chunk]`, `chunk_count: int`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_schemas.py` (append at end of file):

```python
from api.schemas import SECTION_TYPES, CorpusIngestResult, SectionType


def test_section_types_constant_matches_literal_values():
    assert SECTION_TYPES == ("experiencia_previa", "capacidades_tecnicas", "equipo")
    assert SectionType.__args__ == SECTION_TYPES


def test_corpus_ingest_result_round_trip():
    chunk = Chunk(
        chunk_id="doc_001",
        text="Texto de prueba.",
        source="doc.pdf",
        section_type="experiencia_previa",
    )

    result = CorpusIngestResult(
        source="doc.pdf",
        section_type="experiencia_previa",
        chunks_added=[chunk],
        chunk_count=1,
    )

    assert result.chunk_count == 1
    assert result.chunks_added[0].chunk_id == "doc_001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_schemas.py -v`
Expected: FAIL with `ImportError: cannot import name 'SECTION_TYPES'`

- [ ] **Step 3: Implement**

In `backend/api/schemas.py`, add `Literal` to the existing `from pydantic import BaseModel` line's neighborhood (top of file) and add the new constant + schema. Insert right after the `Chunk` class (after line 20):

```python
from typing import Literal
```
(add this import at the top of the file, alongside `from datetime import datetime`)

```python
SECTION_TYPES: tuple[str, ...] = ("experiencia_previa", "capacidades_tecnicas", "equipo")
SectionType = Literal["experiencia_previa", "capacidades_tecnicas", "equipo"]
```
(insert directly after the `Chunk` class definition)

Add `CorpusIngestResult` at the end of the file, after `PipelineResult`:

```python
class CorpusIngestResult(BaseModel):
    source: str
    section_type: str
    chunks_added: list[Chunk]
    chunk_count: int
```

Now update `backend/graph/nodes/extract_requirements.py` to use the shared type instead of its own local `Literal`:

Replace line 10:
```python
from api.schemas import Requirement, TraceEvent
```
with:
```python
from api.schemas import Requirement, SectionType, TraceEvent
```

Replace line 15:
```python
SectionTarget = Literal["experiencia_previa", "capacidades_tecnicas", "equipo"]
```
with (delete the line entirely — no replacement needed).

Replace line 23 (`section_target: SectionTarget`) with:
```python
    section_target: SectionType
```

Also remove the now-unused `from typing import Literal` import on line 6 of `extract_requirements.py` (check it isn't used elsewhere in the file first — it isn't).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_schemas.py tests/test_node_extract_requirements.py -v`
Expected: PASS (all tests, including the pre-existing `extract_requirements` node tests — confirms the refactor didn't change behavior)

- [ ] **Step 5: Commit**

```bash
git add backend/api/schemas.py backend/graph/nodes/extract_requirements.py backend/tests/test_schemas.py
git commit -m "feat: add shared SectionType enum and CorpusIngestResult schema"
```

---

### Task 2: `rag/pdf_ingest.py` — PDF text extraction + chunking

**Files:**
- Create: `backend/rag/pdf_ingest.py`
- Modify: `backend/pyproject.toml`
- Test: `backend/tests/test_pdf_ingest.py`

**Interfaces:**
- Consumes: `api.schemas.Chunk` (from Task 1, unchanged).
- Produces: `rag.pdf_ingest.extract_pdf_text(file_bytes: bytes) -> str` (raises `ValueError` on empty/unreadable text), `rag.pdf_ingest.chunk_pdf_text(text: str, source: str, section_type: str) -> list[Chunk]`, `tests.fakes.make_pdf_bytes(text: str) -> bytes` (test helper, reused by Task 5 and Task 6).

- [ ] **Step 1: Add dependencies**

In `backend/pyproject.toml`, add to the `dependencies` list (after `"pydantic",`):
```toml
    "pypdf",
    "langchain-text-splitters",
```

Add to `[dependency-groups] dev` (after `"pytest",`):
```toml
    "fpdf2",
```

Run: `cd backend && uv sync`
Expected: installs `pypdf`, `langchain-text-splitters`, `fpdf2` with no errors.

- [ ] **Step 2: Write the failing test**

First, add a shared PDF-fixture helper to `backend/tests/fakes.py` (append at end of file, matching the existing convention of shared test doubles living here):

```python
from fpdf import FPDF


def make_pdf_bytes(text: str) -> bytes:
    """Genera un PDF sintético en memoria para tests (fpdf2, sin red ni
    archivos binarios versionados)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text.splitlines():
        pdf.multi_cell(0, 10, line)
    return bytes(pdf.output())
```

Create `backend/tests/test_pdf_ingest.py`:

```python
"""Tests de extracción de texto PDF y chunking (rag/pdf_ingest.py)."""

import pytest
from fpdf import FPDF

from rag.pdf_ingest import chunk_pdf_text, extract_pdf_text
from tests.fakes import make_pdf_bytes


def test_extract_pdf_text_returns_page_text():
    pdf_bytes = make_pdf_bytes("Algoworks entrego 12 proyectos de integracion de datos en 2023.")

    text = extract_pdf_text(pdf_bytes)

    assert "Algoworks" in text
    assert "2023" in text


def test_extract_pdf_text_raises_on_empty_pdf():
    pdf = FPDF()
    pdf.add_page()
    empty_pdf_bytes = bytes(pdf.output())

    with pytest.raises(ValueError):
        extract_pdf_text(empty_pdf_bytes)


def test_chunk_pdf_text_generates_sequential_chunk_ids():
    long_text = "Algoworks entrego proyectos de datos. " * 60

    chunks = chunk_pdf_text(long_text, source="Propuesta_Demo.pdf", section_type="experiencia_previa")

    assert len(chunks) > 1
    assert chunks[0].chunk_id == "propuesta_demo_001"
    assert chunks[1].chunk_id == "propuesta_demo_002"
    assert all(chunk.section_type == "experiencia_previa" for chunk in chunks)
    assert all(chunk.source == "Propuesta_Demo.pdf" for chunk in chunks)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pdf_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.pdf_ingest'`

- [ ] **Step 4: Implement**

Create `backend/rag/pdf_ingest.py`:

```python
"""Ingesta de PDFs: extracción de texto y chunking, compartido por la
ingesta del corpus de conocimiento y por el RFP de entrada (sub-project D,
ver docs/superpowers/specs/2026-09-19-pdf-ingestion-design.md).
"""

import re
from io import BytesIO

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from api.schemas import Chunk

CHUNK_SIZE = 700
CHUNK_OVERLAP = 120


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text:
        raise ValueError(
            "No se pudo extraer texto legible del PDF "
            "(¿es un PDF escaneado sin capa de texto?)."
        )
    return text


def _slugify(source: str) -> str:
    stem = re.sub(r"\.[^.]+$", "", source)
    slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    return slug or "documento"


def chunk_pdf_text(text: str, source: str, section_type: str) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    slug = _slugify(source)
    return [
        Chunk(
            chunk_id=f"{slug}_{i:03d}",
            text=piece,
            source=source,
            section_type=section_type,
        )
        for i, piece in enumerate(splitter.split_text(text), start=1)
    ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_pdf_ingest.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/rag/pdf_ingest.py backend/pyproject.toml backend/uv.lock backend/tests/test_pdf_ingest.py backend/tests/fakes.py
git commit -m "feat: add PDF text extraction and chunking utility"
```

---

### Task 3: Persist ingested chunks — `rag/corpus.py`

**Files:**
- Modify: `backend/rag/corpus.py`
- Create: `.gitignore` (repo root)
- Test: `backend/tests/test_corpus.py`

**Interfaces:**
- Consumes: `api.schemas.Chunk` (Task 1).
- Produces: `rag.corpus.DEFAULT_INGESTED_PATH: Path`, `rag.corpus.load_ingested_chunks(path: Path = DEFAULT_INGESTED_PATH) -> list[Chunk]` (returns `[]` if file doesn't exist), `rag.corpus.append_ingested_chunks(chunks: list[Chunk], path: Path = DEFAULT_INGESTED_PATH) -> None`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_corpus.py` (append at end of file):

```python
import json

from rag.corpus import append_ingested_chunks, load_ingested_chunks


def _sample_ingested_chunk(chunk_id: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        text="Texto de prueba ingerido desde PDF.",
        source="Propuesta_Demo.pdf",
        section_type="experiencia_previa",
    )


def test_load_ingested_chunks_returns_empty_list_when_file_missing(tmp_path):
    missing_path = tmp_path / "ingested_chunks.json"

    assert load_ingested_chunks(missing_path) == []


def test_append_ingested_chunks_persists_and_accumulates(tmp_path):
    path = tmp_path / "ingested_chunks.json"

    append_ingested_chunks([_sample_ingested_chunk("demo_001")], path)
    append_ingested_chunks([_sample_ingested_chunk("demo_002")], path)

    chunks = load_ingested_chunks(path)
    assert [chunk.chunk_id for chunk in chunks] == ["demo_001", "demo_002"]
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert len(raw) == 2
```

Also add `Chunk` to the existing `from api.schemas import Chunk` import at the top of `backend/tests/test_corpus.py` if not already imported (it already is, per the existing file — no change needed there).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_corpus.py -v`
Expected: FAIL with `ImportError: cannot import name 'append_ingested_chunks'`

- [ ] **Step 3: Implement**

Modify `backend/rag/corpus.py` — add after the existing `DEFAULT_CORPUS_PATH`/`load_dummy_chunks` (append to the file):

```python
DEFAULT_INGESTED_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "knowledge_base" / "ingested_chunks.json"
)


def load_ingested_chunks(path: Path = DEFAULT_INGESTED_PATH) -> list[Chunk]:
    if not path.exists():
        return []
    raw_chunks = json.loads(path.read_text(encoding="utf-8"))
    return [Chunk.model_validate(item) for item in raw_chunks]


def append_ingested_chunks(chunks: list[Chunk], path: Path = DEFAULT_INGESTED_PATH) -> None:
    combined = load_ingested_chunks(path) + chunks
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([chunk.model_dump() for chunk in combined], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

Create a root-level `.gitignore` (there is currently none at repo root, only `backend/.gitignore`) so runtime-ingested demo content doesn't get committed:

```
data/knowledge_base/ingested_chunks.json
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_corpus.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add backend/rag/corpus.py backend/tests/test_corpus.py .gitignore
git commit -m "feat: persist PDF-ingested chunks to ingested_chunks.json"
```

---

### Task 4: `rag/store.py` — add chunks to a live vectorstore

**Files:**
- Modify: `backend/rag/store.py`
- Test: `backend/tests/test_store.py`

**Interfaces:**
- Consumes: `api.schemas.Chunk`, `tests.fakes.FakeEmbeddings`, `rag.store.build_vectorstore`/`similarity_search` (all pre-existing).
- Produces: `rag.store.add_chunks(vectorstore: Chroma, chunks: list[Chunk]) -> None`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_store.py` (append at end of file, and add `add_chunks` to the existing `from rag.store import build_vectorstore, similarity_search` import line):

```python
def test_add_chunks_makes_new_chunk_retrievable():
    vectorstore = build_vectorstore(_sample_chunks(), FakeEmbeddings(VOCABULARY))

    add_chunks(
        vectorstore,
        [
            Chunk(
                chunk_id="chunk_manufactura",
                text="Nuevo proyecto de manufactura con Algoworks.",
                source="doc_c.md",
                section_type="experiencia_previa",
            )
        ],
    )

    results = similarity_search(vectorstore, "manufactura", k=1)

    assert results[0][0] == "chunk_manufactura"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_store.py -v`
Expected: FAIL with `ImportError: cannot import name 'add_chunks'`

- [ ] **Step 3: Implement**

In `backend/rag/store.py`, add after `build_vectorstore` (before `similarity_search`):

```python
def add_chunks(vectorstore: Chroma, chunks: list[Chunk]) -> None:
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
    vectorstore.add_documents(documents=documents, ids=ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_store.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add backend/rag/store.py backend/tests/test_store.py
git commit -m "feat: add add_chunks to mutate a live vectorstore in place"
```

---

### Task 5: `POST /corpus/ingest` endpoint

**Files:**
- Modify: `backend/api/main.py`
- Modify: `backend/pyproject.toml`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `rag.pdf_ingest.extract_pdf_text`/`chunk_pdf_text` (Task 2), `rag.corpus.append_ingested_chunks`/`DEFAULT_INGESTED_PATH`/`load_dummy_chunks`/`load_ingested_chunks` (Task 3), `rag.store.add_chunks` (Task 4), `api.schemas.CorpusIngestResult`/`SectionType` (Task 1).
- Produces: `api.main.get_corpus_resources() -> tuple[Chroma, Embeddings, dict[str, str]]` (FastAPI dependency, overridable in tests exactly like `get_pipeline_runner`), `POST /corpus/ingest` endpoint.

- [ ] **Step 1: Add `python-multipart` dependency**

In `backend/pyproject.toml`, add to `dependencies` (needed by FastAPI for file/form uploads):
```toml
    "python-multipart",
```

Run: `cd backend && uv sync`

- [ ] **Step 2: Write the failing test**

Add to `backend/tests/test_api.py`. First, extend the imports at the top:

```python
import io

from api.main import app, get_corpus_resources, get_pipeline_runner
from api.schemas import (
    Chunk,
    CorpusIngestResult,
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
from rag.store import build_vectorstore
from tests.fakes import FakeEmbeddings, make_pdf_bytes
```

(`get_pipeline_runner` was already imported — replace that whole import block; `make_pdf_bytes` is the shared helper added to `tests/fakes.py` in Task 2.)

Add a corpus-resources override fixture, alongside the existing `override_pipeline_runner` fixture:

```python
_CORPUS_VOCABULARY = ["kafka", "manufactura", "retail"]


def _fake_corpus_resources():
    chunks = [
        Chunk(
            chunk_id="chunk_seed",
            text="Chunk semilla sobre kafka.",
            source="seed.md",
            section_type="capacidades_tecnicas",
        )
    ]
    embeddings = FakeEmbeddings(_CORPUS_VOCABULARY)
    vectorstore = build_vectorstore(chunks, embeddings)
    chunk_texts_by_id = {chunk.chunk_id: chunk.text for chunk in chunks}
    return vectorstore, embeddings, chunk_texts_by_id


@pytest.fixture(autouse=True)
def override_corpus_resources(tmp_path, monkeypatch):
    import rag.corpus as corpus_module

    monkeypatch.setattr(corpus_module, "DEFAULT_INGESTED_PATH", tmp_path / "ingested_chunks.json")
    app.dependency_overrides[get_corpus_resources] = _fake_corpus_resources
    yield
    app.dependency_overrides.clear()
```

Add the test itself at the end of the file:

```python
def test_ingest_corpus_pdf_returns_chunks_and_makes_them_retrievable():
    pdf_bytes = make_pdf_bytes("Algoworks tiene experiencia en proyectos de manufactura.")

    response = client.post(
        "/corpus/ingest",
        files={"file": ("propuesta_manufactura.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"section_type": "experiencia_previa"},
    )

    assert response.status_code == 200
    result = CorpusIngestResult.model_validate(response.json())
    assert result.source == "propuesta_manufactura.pdf"
    assert result.section_type == "experiencia_previa"
    assert result.chunk_count >= 1
    assert result.chunks_added[0].chunk_id == "propuesta_manufactura_001"


def test_ingest_corpus_pdf_rejects_invalid_section_type():
    pdf_bytes = make_pdf_bytes("Contenido de prueba.")

    response = client.post(
        "/corpus/ingest",
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"section_type": "no_es_un_tipo_valido"},
    )

    assert response.status_code == 422


def test_ingest_corpus_pdf_rejects_empty_pdf():
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    empty_pdf_bytes = bytes(pdf.output())

    response = client.post(
        "/corpus/ingest",
        files={"file": ("vacio.pdf", io.BytesIO(empty_pdf_bytes), "application/pdf")},
        data={"section_type": "experiencia_previa"},
    )

    assert response.status_code == 422
    body = response.json()
    assert set(body.keys()) == {"error", "detail"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_api.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_corpus_resources'`

- [ ] **Step 4: Implement**

In `backend/api/main.py`:

Replace line 21 (`from rag.corpus import load_dummy_chunks`) with:
```python
from rag import corpus
```

Replace line 23 (`from rag.store import build_vectorstore`) with:
```python
from rag.store import add_chunks, build_vectorstore
```

Add new imports near the top, after the existing `from rag...` imports:
```python
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from api.schemas import CorpusIngestResult, PipelineResult, SectionType, TraceEvent
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from rag.pdf_ingest import extract_pdf_text, chunk_pdf_text
```
(Merge these into the existing import blocks rather than duplicating — `PipelineResult`/`TraceEvent` and `Depends, FastAPI, HTTPException, Request` are already imported on lines 11 and 18; just add `CorpusIngestResult, SectionType` to the line-18 import, and `File, Form, UploadFile` to the line-11 import.)

Replace line 88 (`chunks = load_dummy_chunks()`) with:
```python
    chunks = corpus.load_dummy_chunks() + corpus.load_ingested_chunks(corpus.DEFAULT_INGESTED_PATH)
```

Add a `CorpusResources` type alias and `get_corpus_resources` dependency function right after `_get_corpus_resources` (after line 92):

```python
CorpusResources = tuple[Chroma, Embeddings, dict[str, str]]


def get_corpus_resources() -> CorpusResources:
    return _get_corpus_resources()
```

Add the new endpoint after `process_rfp` (after line 126):

```python
@app.post("/corpus/ingest", response_model=CorpusIngestResult)
async def ingest_corpus_pdf(
    file: UploadFile = File(...),
    section_type: SectionType = Form(...),
    source: str | None = Form(None),
    corpus_resources: CorpusResources = Depends(get_corpus_resources),
) -> CorpusIngestResult:
    vectorstore, _embeddings, chunk_texts_by_id = corpus_resources
    file_bytes = await file.read()
    resolved_source = source or file.filename or "documento.pdf"

    try:
        text = extract_pdf_text(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    chunks = chunk_pdf_text(text, source=resolved_source, section_type=section_type)
    add_chunks(vectorstore, chunks)
    chunk_texts_by_id.update({chunk.chunk_id: chunk.text for chunk in chunks})
    corpus.append_ingested_chunks(chunks, path=corpus.DEFAULT_INGESTED_PATH)

    return CorpusIngestResult(
        source=resolved_source,
        section_type=section_type,
        chunks_added=chunks,
        chunk_count=len(chunks),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_api.py -v`
Expected: PASS (all tests, including the pre-existing ones — confirms nothing broke)

Then run the full suite to confirm no regressions anywhere:
Run: `cd backend && uv run pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/api/main.py backend/pyproject.toml backend/uv.lock backend/tests/test_api.py
git commit -m "feat: add POST /corpus/ingest endpoint for PDF corpus ingestion"
```

---

### Task 6: `POST /rfp/process/pdf` endpoint

**Files:**
- Modify: `backend/api/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `rag.pdf_ingest.extract_pdf_text` (Task 2), existing `PipelineRunner`/`get_pipeline_runner` (unchanged).
- Produces: `POST /rfp/process/pdf` endpoint, response shape identical to `POST /rfp/process`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api.py` (end of file):

```python
def test_process_rfp_pdf_returns_valid_pipeline_result():
    pdf_bytes = make_pdf_bytes("1. El proveedor debe tener experiencia previa en proyectos similares.")

    response = client.post(
        "/rfp/process/pdf",
        files={"file": ("rfp.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"rfp_id": "rfp_pdf_001"},
    )

    assert response.status_code == 200
    result = PipelineResult.model_validate(response.json())
    assert result.rfp_id == "rfp_pdf_001"


def test_process_rfp_pdf_rejects_empty_pdf():
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    empty_pdf_bytes = bytes(pdf.output())

    response = client.post(
        "/rfp/process/pdf",
        files={"file": ("vacio.pdf", io.BytesIO(empty_pdf_bytes), "application/pdf")},
        data={"rfp_id": "rfp_pdf_002"},
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_api.py -v -k process_rfp_pdf`
Expected: FAIL with 404 (route doesn't exist) — assertion `response.status_code == 200` fails.

- [ ] **Step 3: Implement**

In `backend/api/main.py`, add after the `process_rfp` endpoint (or after the new `/corpus/ingest` endpoint from Task 5):

```python
@app.post("/rfp/process/pdf", response_model=PipelineResult)
async def process_rfp_pdf(
    file: UploadFile = File(...),
    rfp_id: str = Form(...),
    pipeline_runner: PipelineRunner = Depends(get_pipeline_runner),
) -> PipelineResult:
    file_bytes = await file.read()

    try:
        rfp_text = extract_pdf_text(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = pipeline_runner(rfp_id, rfp_text)
    _pipeline_results[rfp_id] = result
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_api.py -v`
Expected: PASS (all tests)

Then run the full suite one more time:
Run: `cd backend && uv run pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/main.py backend/tests/test_api.py
git commit -m "feat: add POST /rfp/process/pdf endpoint for PDF RFP input"
```

---

## Post-plan follow-ups (not part of this plan)

- Doc-sync pass on `docs/API_PARA_FRONTEND.md` / `docs/CONTRATO_DATOS.md` for the two new endpoints (flagged in the spec, §7).
- Any frontend UI to actually upload PDFs through these endpoints — out of scope per spec §7.
