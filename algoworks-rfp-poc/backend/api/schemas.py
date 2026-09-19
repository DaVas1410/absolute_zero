"""Contrato de datos del pipeline RFP.

Fuente de verdad: CLAUDE.md, sección 4, y
docs/superpowers/specs/2026-09-18-traceability-metrics-design.md (sub-project A).
No cambiar nombres de campos ni tipos existentes sin avisar en el chat del
equipo — frontend y backend dependen de que este contrato sea estable desde
la hora 0. Las adiciones de sub-project A son todas aditivas.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Chunk(BaseModel):
    chunk_id: str
    text: str
    source: str  # ej. "Propuesta_ClienteX_2023.md"
    section_type: str  # "experiencia_previa" | "capacidades_tecnicas" | "equipo" | ...
    metadata: dict = {}


SECTION_TYPES: tuple[str, ...] = ("experiencia_previa", "capacidades_tecnicas", "equipo")
SectionType = Literal["experiencia_previa", "capacidades_tecnicas", "equipo"]


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


class CorpusIngestResult(BaseModel):
    source: str
    section_type: str
    chunks_added: list[Chunk]
    chunk_count: int
