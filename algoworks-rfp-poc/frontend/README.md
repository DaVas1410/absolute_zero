# Trace Desk — frontend

React + Vite + TypeScript client for the Algoworks RFP PoC backend. Design
system: `trace-desk-design-reference.md` (see repo root / project docs).

Scoped to the base 4-endpoint pipeline (`GET /health`, `POST /rfp/process`,
`GET /rfp/{id}/trace`, `POST /rfp/{req_id}/feedback`) — PDF ingestion and the
consolidated-proposal ("compose") endpoints are a separate backend
sub-project, not yet covered here.

## Setup

```bash
npm install
cp .env.example .env.local   # override VITE_API_BASE_URL if the backend isn't on :8000
npm run dev
```

Requires the backend running (`uv run uvicorn api.main:app --reload --port 8000`
from `../backend/`) with `GROQ_API_KEY` set — without it, `POST /rfp/process`
fails when the backend tries to construct its Groq client, before it can
even fall back to a local Ollama.

## Scripts

- `npm run dev` — dev server (default port 5173)
- `npm run build` — type-check (`tsc -b`) + production build
- `npm run test` — Vitest (pure-function tests: API client, citation
  parsing, formatting, source indexing — no component/E2E tests; see
  `docs/superpowers/specs/2026-09-18-frontend-design.md` §9 for the
  reduced-scope rationale this follows)
- `npm run lint` — oxlint

## Structure

- `src/api/` — typed API client, mirrors `backend/api/schemas.py`
- `src/utils/` — pure helpers (citation-marker parsing, formatting, source
  indexing) — the only unit-tested layer
- `src/components/ui/` — design-system primitives (Button, Badge, Tabs, …)
- `src/components/layout/` — Sidebar/TopBar/Shell, shared across screens
- `src/components/screens/` — Home, Processing, Results (+ its 4 tabs)
- `src/data/sampleRfps.ts` — loads `../data/sample_rfps/*.txt` for the demo
  picker

## Known gaps (by API design, not a bug)

`RetrievedChunk` never includes the underlying chunk's full text or
`section_type` — only `chunk_id`, `score`, `justification`, `source`. The
`DetailPanel`'s "quoted excerpt" renders a placeholder rather than inventing
content; see `docs/CONTRATO_DATOS.md`.
