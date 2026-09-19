# PDF ingestion — design spec

> Sub-project D. Adds PDF support to the RAG pipeline: (D-A) ingesting PDF
> documents into the knowledge corpus used for citation, and (D-B) accepting
> a PDF as the incoming RFP. Both are purely additive — no existing endpoint,
> pipeline node, or schema field changes behavior for current callers.

## 1. Problem

The corpus (`data/knowledge_base/dummy_chunks.json`) and the RFP text are
currently both plain strings/hand-written JSON with no PDF support anywhere
in the repo (no PDF library, no text splitter). For the demo to show "an
actual RAG" — a real vector space being built from real documents, not a
hand-curated JSON file — both the knowledge corpus and the RFP input need to
accept PDFs. Per `CLAUDE.md` §1, the two things judges weight most are
trazabilidad and explicabilidad, so ingestion must make it obvious *what*
went into the vector space, not just accept a file silently.

## 2. Shared PDF utility — `backend/rag/pdf_ingest.py`

Library choice: **pypdf** for text extraction (pure Python, no system
dependencies like poppler/tesseract — safe to install mid-hackathon) +
LangChain's `RecursiveCharacterTextSplitter` for chunking (already in the
dependency tree via `langchain-core`, consistent with the rest of the
stack). Demo PDFs are synthetic/text-based, so OCR is out of scope.

```python
def extract_pdf_text(file_bytes: bytes) -> str:
    """Extrae y concatena el texto de todas las páginas. Lanza ValueError
    si el resultado es vacío/whitespace (PDF escaneado sin capa de texto)."""

def chunk_pdf_text(text: str, source: str, section_type: str) -> list[Chunk]:
    """RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=120).
    chunk_id generado como f"{slugify(source)}_{i:03d}"."""
```

`chunk_size=700`/`overlap=120` chosen to roughly match the granularity of
the existing hand-written dummy chunks (300–450 chars each, one claim per
chunk).

**Shared enum refactor:** `section_target`/`section_type` currently only
exists as a `Literal["experiencia_previa", "capacidades_tecnicas", "equipo"]`
inside `graph/nodes/extract_requirements.py`. Lift it to `api/schemas.py` as
`SECTION_TYPES = ("experiencia_previa", "capacidades_tecnicas", "equipo")`
(and a `SectionType = Literal[SECTION_TYPES]` type alias), imported by both
`extract_requirements.py` and the new ingestion code, so there's one source
of truth instead of two enums that could silently drift.

## 3. Sub-project D-A — Corpus PDF ingestion

**`POST /corpus/ingest`** (multipart/form-data):
- `file`: UploadFile (PDF)
- `section_type`: Form, validated against `SectionType`
- `source`: Form, optional, defaults to the uploaded filename

Flow:
1. Read file bytes, `extract_pdf_text` → raise 422 if empty.
2. `chunk_pdf_text(text, source, section_type)` → `list[Chunk]`.
3. Mutate the **live** vectorstore singleton (`_get_corpus_resources()` in
   `api/main.py`) via `vectorstore.add_documents(...)` — queryable
   immediately by the next `/rfp/process` call, no restart needed.
4. Append the new `Chunk` records to `data/knowledge_base/ingested_chunks.json`
   (new file, separate from the hand-curated `dummy_chunks.json`) so they
   survive a server restart. `load_dummy_chunks`-equivalent startup loading
   merges both files if `ingested_chunks.json` exists.
5. Return a new `CorpusIngestResult` schema echoing exactly what was
   embedded — this is the traceability payload:

```python
class CorpusIngestResult(BaseModel):
    source: str
    section_type: str
    chunks_added: list[Chunk]
    chunk_count: int
```

Error handling: empty-text PDF → 422 (`{"error","detail"}`, via the existing
global exception handlers); invalid `section_type` → 422 (FastAPI validates
the `Literal` automatically).

## 4. Sub-project D-B — RFP PDF input

**`POST /rfp/process/pdf`** (multipart/form-data):
- `rfp_id`: Form
- `file`: UploadFile (PDF)

Flow: `extract_pdf_text(file_bytes)` → call the **same**
`pipeline_runner(rfp_id, rfp_text)` already used by `POST /rfp/process`.
No graph/pipeline changes — `GraphState` still just takes `rfp_text: str`.
Response: same `PipelineResult` as the existing JSON endpoint.

The existing `POST /rfp/process` (JSON body) is untouched — frontend PR #3
keeps working exactly as-is.

## 5. Dependencies

Add to `backend/pyproject.toml`: `pypdf`, `python-multipart` (required by
FastAPI for file/form uploads, not currently a dependency).

## 6. Testing

Per the project's hackathon testing-scope philosophy (test high-risk logic,
skip trivial wiring — see punch-list precedent in `docs/superpowers/plans/`):

- `backend/tests/test_pdf_ingest.py` — `extract_pdf_text` / `chunk_pdf_text`
  against a small synthetic PDF generated in-memory at test time (via
  `fpdf2`, a new dev-only dependency, exposed as `tests/fakes.py::make_pdf_bytes`
  per the project's existing shared-test-double convention) rather than a
  committed binary fixture — avoids binary diffs in git; covers the
  empty-text-PDF error path.
- `backend/tests/test_api.py` additions — one happy-path test per new
  endpoint: `/corpus/ingest` asserts the returned chunks are then actually
  retrievable via `similarity_search` (proves live mutation, not just
  wiring); `/rfp/process/pdf` asserts it produces a `PipelineResult` shaped
  like the text endpoint's.
- Out of scope: exhaustive form-validation edge cases, multi-format PDF
  fuzzing, OCR/scanned-PDF support.

## 7. Explicitly out of scope

- OCR / scanned PDFs.
- Deleting/updating previously-ingested corpus chunks (append-only for now).
- Any frontend UI for these endpoints (this spec is backend-only; a
  frontend upload UI is a separate future task).
- Doc-sync pass on `docs/API_PARA_FRONTEND.md` / `docs/CONTRATO_DATOS.md` —
  flagged as a follow-up, not part of this implementation.
