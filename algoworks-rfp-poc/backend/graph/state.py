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
