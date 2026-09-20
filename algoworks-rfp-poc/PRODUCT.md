# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: hackathon judges for the Algoworks / Yachay Tech "Hackathon Innovación Aplicada" challenge, who interact with the running demo (Trace Desk) directly in a short evaluation session — picking a sample RFP, running the pipeline, and inspecting the result.

The demo simulates a secondary, real-world persona it is built to serve: an Algoworks proposal writer preparing an RFP response, who needs AI-assisted drafting they can actually trust and defend — not just fast text.

## Product Purpose

Trace Desk drafts RFP proposal sections using a LangGraph-orchestrated RAG pipeline (Groq primary LLM, local Ollama fallback), while exposing a full, inspectable trace of every retrieval, generation, and verification decision. Success is a judge (or eventual proposal writer) being able to see exactly which knowledge-base chunks informed a given claim and why the system trusted — or flagged — it.

## Positioning

Per the challenge brief, the two concepts that matter most are traceability and explainability — generating proposal text is table stakes. Trace Desk's mechanism a competitor generating plausible RFP text could not truthfully copy: every factual claim cites a real `[[chunk_id]]`, every citation is independently re-verified against its source chunk (NLI-style supported/not-supported + why), unsupported claims trigger one retry and then are flagged for human review or stripped rather than shipped silently, and every pipeline node emits a `TraceEvent` a viewer can inspect end to end.

## Operating Context

A live demo session, typically a few minutes long: pick one of the bundled sample RFPs (including a deliberately adversarial one — "SLA sin respaldo" — with an unsupported latency claim that must reliably fail verification) or upload a PDF, run the pipeline, then review the Requirements / Response / Sources / Trace Log tabs and the consolidated proposal document, including a client-facing view versus an internal traceability view.

## Capabilities and Constraints

- Full pipeline implemented and live-validated against the real Groq API: `extract_requirements → retrieve_chunks → generate_draft → verify_citations` (max 1 retry), plus a `compose_proposal → verify_proposal` sub-pipeline that assembles a consolidated document from already-cited chunks (never re-retrieves or invents citations).
- Local Ollama fallback exists for offline resilience; correct but roughly 5–10x slower than Groq (CPU inference).
- Groq's daily token quota is shared across `/rfp/process` and `/compose` — heavy same-day testing of either can exhaust both.
- Backend dev server runs without `--reload` — a backend code change needs a manual restart to take effect.
- Corpus and all sample RFPs are fictitious/synthetic by hackathon rule (no real Algoworks legal/commercial documents), not a technical limitation. The corpus has a deliberate anti-hallucination design: any real Algoworks facts (certifications, etc.) are only ever included behind an explicit "requiere validación" hedge — this pattern must be preserved, never overridden, when the corpus is extended.
- Explicitly out of scope: automating the full RFP process end-to-end. A concrete, well-executed component/flow satisfies the brief.
- `POST /corpus/ingest` (PDF-as-past-proposal ingestion) exists in the backend but has no frontend UI yet — a known, intentional gap.

## Brand Commitments

Product/demo wordmark: "Trace Desk" (used as-is in the frontend UI; do not translate). UI copy is otherwise in Spanish; LLM-generated proposal content and the wordmark are left as-is.

## Evidence on Hand

- `data/knowledge_base/dummy_chunks.json` — synthetic knowledge-base corpus (80+ chunks) spanning fictional client proposals, capability statements, and team profiles, including SaaS/AI-ML-themed content and a low-risk-hedged real-Algoworks-grounding pass.
- `data/sample_rfps/` — bundled sample RFPs, including one confirmed-reproducible adversarial case ("SLA sin respaldo") and the official hackathon dataset's AndesFin RFP (`docs/docs_algo/`, ingested into the corpus).
- No real Algoworks legal, contractual, or commercial documents exist in this repo and none should be fabricated or presented as real.

## Product Principles

1. Every generated claim must resolve to a specific, real source chunk — never presented as ungrounded text.
2. Explainability is a first-class surface, not a debug afterthought: trace and verification data get dedicated views, kept separate from the clean client-facing deliverable.
3. Catching and flagging an unsupported claim beats silently shipping a hallucinated one, even at the cost of leaving a visible gap.
4. The corpus and demo content stay strictly synthetic/fictitious; any real-world fact is included only behind an explicit validation hedge, never asserted outright.
5. A narrow slice done well beats a shallow end-to-end automation — matches the brief's explicit scope limit.
