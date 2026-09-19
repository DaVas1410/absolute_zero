"""Contrato de datos del pipeline RFP.

Fuente de verdad: CLAUDE.md, sección 4. No cambiar nombres de campos ni
tipos sin avisar en el chat del equipo — frontend y backend dependen de
que este contrato sea estable desde la hora 0.
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


class DraftSection(BaseModel):
    req_id: str
    text: str  # contiene marcadores [[chunk_id]] inline
    cited_chunks: list[str]


class VerificationResult(BaseModel):
    req_id: str
    supported: bool
    issues: list[str]
    confidence: float


class TraceEvent(BaseModel):
    node: str
    timestamp: datetime
    input_summary: str
    output_summary: str
    reasoning: str


class PipelineResult(BaseModel):
    rfp_id: str
    requirements: list[Requirement]
    retrieved: dict[str, list[RetrievedChunk]]
    drafts: dict[str, DraftSection]
    verification: dict[str, VerificationResult]
    trace_log: list[TraceEvent]
