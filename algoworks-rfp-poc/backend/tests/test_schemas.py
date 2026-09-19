"""Smoke test del entorno: valida que el contrato de datos importa e
instancia correctamente. No cubre logica de negocio (aun no implementada).
"""

from datetime import datetime

from api.schemas import (
    Chunk,
    DraftSection,
    PipelineResult,
    Requirement,
    RetrievedChunk,
    TraceEvent,
    VerificationResult,
)


def test_pipeline_result_round_trip():
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
    )
    verification = VerificationResult(
        req_id=requirement.req_id,
        supported=True,
        issues=[],
        confidence=0.92,
    )
    trace_event = TraceEvent(
        node="retrieve_chunks",
        timestamp=datetime(2026, 9, 18, 12, 0, 0),
        input_summary="requirement=req_001",
        output_summary="1 chunk recuperado",
        reasoning="El chunk_001 tiene la mayor similitud coseno con el requisito.",
    )

    result = PipelineResult(
        rfp_id="rfp_001",
        requirements=[requirement],
        retrieved={requirement.req_id: [retrieved]},
        drafts={requirement.req_id: draft},
        verification={requirement.req_id: verification},
        trace_log=[trace_event],
    )

    assert result.rfp_id == "rfp_001"
    assert result.drafts[requirement.req_id].cited_chunks == [chunk.chunk_id]
