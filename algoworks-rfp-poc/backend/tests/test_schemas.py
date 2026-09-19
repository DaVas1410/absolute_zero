"""Smoke test del contrato de datos: valida que el contrato completo
(incluyendo los campos de trazabilidad de sub-project A) importa e
instancia correctamente. No cubre logica de negocio (aun no implementada).
"""

from datetime import datetime

from api.schemas import (
    Chunk,
    CitationSimilarity,
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


def _sample_trace_event(node: str = "retrieve_chunks") -> TraceEvent:
    return TraceEvent(
        node=node,
        timestamp=datetime(2026, 9, 18, 12, 0, 0),
        input_summary="requirement=req_001",
        output_summary="1 chunk recuperado",
        reasoning="El chunk_001 tiene la mayor similitud coseno con el requisito.",
    )


def test_trace_event_defaults_have_no_duration_or_tokens():
    trace_event = _sample_trace_event()

    assert trace_event.duration_ms == 0.0
    assert trace_event.tokens is None


def test_trace_event_accepts_duration_and_token_usage():
    trace_event = TraceEvent(
        node="generate_draft",
        timestamp=datetime(2026, 9, 18, 12, 0, 0),
        input_summary="...",
        output_summary="...",
        reasoning="...",
        duration_ms=123.4,
        tokens=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost_usd=0.001),
    )

    assert trace_event.duration_ms == 123.4
    assert trace_event.tokens.total_tokens == 150


def test_draft_section_defaults_have_no_reasoning_or_similarity():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])

    assert draft.reasoning == ""
    assert draft.citation_similarities == []
    assert draft.overall_similarity == 0.0


def test_draft_section_accepts_citation_similarities():
    draft = DraftSection(
        req_id="req_001",
        text="Texto [[chunk_001]].",
        cited_chunks=["chunk_001"],
        reasoning="Se citó chunk_001 porque describe experiencia previa relevante.",
        citation_similarities=[CitationSimilarity(chunk_id="chunk_001", similarity=0.87)],
        overall_similarity=0.87,
    )

    assert draft.citation_similarities[0].chunk_id == "chunk_001"
    assert draft.overall_similarity == 0.87


def test_verification_result_defaults_have_no_reasoning_or_retries():
    verification = VerificationResult(req_id="req_001", supported=True, issues=[], confidence=0.9)

    assert verification.reasoning == ""
    assert verification.retries_used == 0


def test_pipeline_result_round_trip_with_metrics_and_audit():
    chunk = Chunk(
        chunk_id="chunk_001",
        text="Algoworks entrego 12 proyectos de integracion de datos en 2023.",
        source="Propuesta_ClienteX_2023.md",
        section_type="experiencia_previa",
    )
    requirement = Requirement(
        req_id="req_001",
        text="El proveedor debe demostrar experiencia previa en proyectos similares.",
        section_target="experiencia_previa",
    )
    retrieved = RetrievedChunk(
        chunk_id=chunk.chunk_id,
        score=0.87,
        justification="El chunk describe experiencia previa relevante en integracion de datos.",
    )
    draft = DraftSection(
        req_id=requirement.req_id,
        text="Algoworks cuenta con experiencia comprobada [[chunk_001]].",
        cited_chunks=[chunk.chunk_id],
        reasoning="Se citó chunk_001 por ser el más relevante.",
        citation_similarities=[CitationSimilarity(chunk_id="chunk_001", similarity=0.9)],
        overall_similarity=0.9,
    )
    verification = VerificationResult(
        req_id=requirement.req_id,
        supported=True,
        issues=[],
        confidence=0.92,
        reasoning="El chunk_001 respalda completamente la afirmación.",
        retries_used=0,
    )
    metrics = PipelineMetrics(
        total_duration_ms=842.5,
        total_tokens=TokenUsage(input_tokens=500, output_tokens=200, total_tokens=700, estimated_cost_usd=0.002),
        retries_used=0,
        requirements_supported=1,
        requirements_needing_review=0,
        hallucinated_citations_caught=0,
    )
    reasoning_path_audit = ReasoningPathAudit(
        is_consistent=True,
        node_sequence=["extract_requirements", "retrieve_chunks", "generate_draft", "verify_citations"],
        issues=[],
    )

    result = PipelineResult(
        rfp_id="rfp_001",
        requirements=[requirement],
        retrieved={requirement.req_id: [retrieved]},
        drafts={requirement.req_id: draft},
        verification={requirement.req_id: verification},
        trace_log=[_sample_trace_event()],
        metrics=metrics,
        reasoning_path_audit=reasoning_path_audit,
    )

    assert result.rfp_id == "rfp_001"
    assert result.drafts[requirement.req_id].cited_chunks == [chunk.chunk_id]
    assert result.metrics.requirements_supported == 1
    assert result.reasoning_path_audit.is_consistent is True
