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
    source: str = ""  # ej. "Propuesta_ClienteX_2023.md" (aditivo, sub-project frontend)


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
    # Cobertura de citas (código-only, ver graph/citation_coverage.py): un
    # requisito "fully_cited" tiene citas y quedó soportado sin issues; uno
    # "uncited" no citó ningún chunk; el resto ("partially_cited") citó algo
    # pero el verificador encontró un problema.
    fully_cited_count: int = 0
    partially_cited_count: int = 0
    uncited_count: int = 0
    traceability_rate: float = 0.0
    partial_rate: float = 0.0
    uncited_rate: float = 0.0


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


class ChunkCitation(BaseModel):
    chunk_id: str
    text: str  # contenido exacto del chunk citado, resuelto desde el corpus
    source: str
    section_type: str


class ProposalSection(BaseModel):
    heading: str
    body: str  # contiene marcadores [[chunk_id]] inline
    cited_chunks: list[str]
    source_req_ids: list[str]  # qué requisitos originales alimentaron esta sección
    citations: list[ChunkCitation] = []  # cited_chunks resueltos a texto+fuente exactos (finalize_compose)


class ProposalSectionVerification(BaseModel):
    heading: str
    supported: bool
    issues: list[str]
    confidence: float
    reasoning: str = ""  # motivo del veredicto (verify_proposal)
    retries_used: int = 0


class ComposeMetrics(BaseModel):
    total_duration_ms: float
    total_tokens: TokenUsage
    retries_used: int
    sections_supported: int
    sections_needing_review: int
    hallucinated_citations_caught: int
    hallucinated_citations_removed: int  # tras agotar reintentos, eliminadas en código
    # Mismo criterio de cobertura de citas que PipelineMetrics, aplicado a
    # las secciones finales (post-strip de citas alucinadas).
    fully_cited_count: int = 0
    partially_cited_count: int = 0
    uncited_count: int = 0
    traceability_rate: float = 0.0
    partial_rate: float = 0.0
    uncited_rate: float = 0.0


class ProposalDocument(BaseModel):
    rfp_id: str
    sections: list[ProposalSection]
    verification: list[ProposalSectionVerification]
    trace_log: list[TraceEvent]
    metrics: ComposeMetrics


class TraceabilityReport(BaseModel):
    """Reporte agregado de trazabilidad para un rfp_id ya procesado: cobertura
    de citas por requisito (código-only, calculado una vez en
    compute_traceability_metrics) más verificación humana en vivo (via
    POST /rfp/{req_id}/feedback, que ahora persiste en el backend)."""

    rfp_id: str
    total_responses: int
    fully_cited: int
    partially_cited: int
    uncited: int
    traceability_rate: float
    partial_rate: float
    uncited_rate: float
    verified_count: int
    verification_rate: float
