"""Tests del nodo finalize_compose: garantía en código de que ninguna cita
alucinada sobrevive al documento final (se elimina si el reintento no la
corrigió), y cálculo de ComposeMetrics."""

from api.schemas import Chunk, ChunkCitation, ProposalSection, ProposalSectionVerification, TokenUsage, TraceEvent
from graph.nodes.finalize_compose import make_finalize_compose_node
from datetime import datetime, timezone


def _trace_event(node: str, tokens: TokenUsage | None = None, duration_ms: float = 10.0) -> TraceEvent:
    return TraceEvent(
        node=node,
        timestamp=datetime.now(timezone.utc),
        input_summary="...",
        output_summary="...",
        reasoning="...",
        duration_ms=duration_ms,
        tokens=tokens,
    )


_CHUNK_BY_ID = {
    "chunk_001": Chunk(chunk_id="chunk_001", text="Texto real.", source="doc_a.md", section_type="experiencia_previa")
}


def test_finalize_compose_strips_still_hallucinated_citation():
    section = ProposalSection(
        heading="Solución",
        body="Texto respaldado [[chunk_001]] y texto roto [[chunk_099]].",
        cited_chunks=["chunk_001", "chunk_099"],
        source_req_ids=["req_001"],
    )
    node = make_finalize_compose_node(_CHUNK_BY_ID)

    state = {
        "sections": [section],
        "valid_chunk_ids": {"chunk_001"},
        "retry_count": 1,
        "section_verification": [
            ProposalSectionVerification(heading="Solución", supported=False, issues=["cita rota"], confidence=0.0)
        ],
        "hallucination_catches": 1,
        "trace_log": [_trace_event("compose_proposal", tokens=TokenUsage(total_tokens=100, estimated_cost_usd=0.001))],
    }

    result = node(state)

    final_section = result["sections"][0]
    assert "[[chunk_099]]" not in final_section.body
    assert "[[chunk_001]]" in final_section.body
    assert final_section.cited_chunks == ["chunk_001"]
    assert final_section.citations == [
        ChunkCitation(chunk_id="chunk_001", text="Texto real.", source="doc_a.md", section_type="experiencia_previa")
    ]
    assert result["metrics"].hallucinated_citations_removed == 1
    assert result["metrics"].hallucinated_citations_caught == 1
    assert result["metrics"].sections_needing_review == 1
    assert result["metrics"].sections_supported == 0
    # Aun con cita valida, el verificador marco un issue -> partially_cited, no uncited.
    assert result["metrics"].partially_cited_count == 1
    assert result["metrics"].fully_cited_count == 0


def test_finalize_compose_leaves_fully_valid_sections_untouched():
    section = ProposalSection(
        heading="Solución", body="Texto respaldado [[chunk_001]].", cited_chunks=["chunk_001"], source_req_ids=["req_001"]
    )
    node = make_finalize_compose_node(_CHUNK_BY_ID)

    state = {
        "sections": [section],
        "valid_chunk_ids": {"chunk_001"},
        "retry_count": 0,
        "section_verification": [
            ProposalSectionVerification(heading="Solución", supported=True, issues=[], confidence=0.9)
        ],
        "hallucination_catches": 0,
        "trace_log": [],
    }

    result = node(state)

    assert result["sections"][0].body == section.body
    assert result["sections"][0].citations[0].text == "Texto real."
    assert result["metrics"].hallucinated_citations_removed == 0
    assert result["metrics"].sections_supported == 1
    assert result["metrics"].fully_cited_count == 1
    assert result["metrics"].traceability_rate == 1.0
