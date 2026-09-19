"""Estado compartido del grafo LangGraph del pipeline de RFP."""

from typing import TypedDict

from api.schemas import (
    ComposeMetrics,
    DraftSection,
    PipelineMetrics,
    ProposalSection,
    ProposalSectionVerification,
    ReasoningPathAudit,
    Requirement,
    RetrievedChunk,
    TraceEvent,
    VerificationResult,
)

MAX_GENERATE_RETRIES = 1
MAX_COMPOSE_RETRIES = 1


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


class ComposeState(TypedDict):
    """Estado del grafo de composición de propuesta (sub-project: compose
    agents). Toma los borradores YA verificados de un PipelineResult previo
    — no vuelve a extraer requisitos ni a recuperar chunks — y sintetiza un
    documento de negocio real, reutilizando únicamente citas ya validadas."""

    rfp_id: str
    requirements: list[Requirement]
    drafts: dict[str, DraftSection]
    verification: dict[str, VerificationResult]
    valid_chunk_ids: set[str]  # unión de cited_chunks de todos los drafts de entrada
    sections: list[ProposalSection]
    section_verification: list[ProposalSectionVerification]
    hallucinated_section_citations: dict[int, list[str]]  # índice de sección -> chunk_ids inválidos
    hallucination_catches: int
    retry_count: int
    pending: bool
    trace_log: list[TraceEvent]
    metrics: ComposeMetrics | None
