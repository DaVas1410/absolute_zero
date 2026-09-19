# absolute_zero

This repository hosts **`algoworks-rfp-poc`**, a hackathon proof-of-concept for
Algoworks: a LangGraph-orchestrated, RAG-backed agent pipeline that drafts RFP
proposal sections while keeping every retrieval/generation/verification
decision traceable and explainable.

## Overview

Given a simulated RFP, the pipeline extracts structured requirements, retrieves
supporting knowledge-base chunks, drafts each section citing `[[chunk_id]]`
inline, and verifies that every citation is actually supported before handing
the result back — with a full decision trace attached. LLM calls go through
Groq (fast, free tier) with a local Ollama fallback for offline resilience.

See `algoworks-rfp-poc/CLAUDE.md` for the full project brief, architecture,
and data/API contracts — it's the source of truth for the team.

## Repository Structure

```text
.
├── README.md
└── algoworks-rfp-poc/
    ├── CLAUDE.md                  # project brief, architecture, contracts
    ├── backend/                   # FastAPI + LangGraph + RAG (Python, uv)
    │   ├── api/                   # FastAPI app, endpoints, Pydantic schemas
    │   ├── graph/                 # LangGraph nodes, prompts, graph assembly
    │   ├── rag/                   # embeddings + Chroma vectorstore
    │   └── tests/
    ├── data/                      # dummy knowledge base, sample RFPs, eval cases
    ├── frontend/                  # consumes the API (explainability panel)
    └── docs/
        ├── CONTRATO_DATOS.md      # data contract, human-readable
        ├── API_PARA_FRONTEND.md   # API guide for frontend devs
        └── superpowers/           # design specs and implementation plans
```

## Current Status

- `backend/api/schemas.py` implements the full data contract (`Chunk`,
  `Requirement`, `RetrievedChunk`, `DraftSection`, `VerificationResult`,
  `TraceEvent`, `PipelineResult`).
- `backend/api/main.py` exposes `GET /health`, `POST /rfp/process`,
  `GET /rfp/{rfp_id}/trace`, and `POST /rfp/{req_id}/feedback` — currently
  backed by a schema-valid mock so frontend can build against the real
  response shape while the LangGraph pipeline is implemented.
- The real RAG + LangGraph pipeline (plus traceability metrics, RAG grounding
  similarity, and a deterministic execution-path audit) is designed in
  `algoworks-rfp-poc/docs/superpowers/` and not yet wired in — that's the
  active work.

## Getting Started (backend)

```bash
cd algoworks-rfp-poc/backend
uv sync
uv run pytest -q
uv run uvicorn api.main:app --reload --port 8000
```

Server runs at `http://localhost:8000` (docs at `/docs`). See
`algoworks-rfp-poc/docs/API_PARA_FRONTEND.md` for the endpoint contract.

## Development Notes

- Out of scope (hackathon PoC): no real/legal Algoworks documents — the
  corpus and sample RFPs are fictitious/synthetic.
- Keep contributions small, well-scoped, and documented; the data contract in
  `backend/api/schemas.py` is frozen — don't change field names or types
  without flagging it first (see `CLAUDE.md` §4).