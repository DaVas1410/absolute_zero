"""Nodo finalize_compose: corre una sola vez, cuando el ciclo de
verificación/reintento de compose_proposal termina. Garantía final en
código: cualquier chunk_id citado que el reintento no haya corregido se
elimina del texto, para que el documento entregado nunca contenga una cita
rota. También agrega las métricas de toda la composición."""

import re
import time
from datetime import datetime, timezone

from api.schemas import Chunk, ChunkCitation, ComposeMetrics, TokenUsage, TraceEvent
from graph.citation_coverage import classify_citation_coverage, summarize_citation_coverage
from graph.state import ComposeState

_CITATION_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


def _resolve_citations(cited_chunks: list[str], chunk_by_id: dict[str, Chunk]) -> list[ChunkCitation]:
    """Resuelve cada chunk_id citado (ya limpio de alucinaciones) al texto
    exacto y la fuente del corpus, para que el documento final traiga el
    chunk completo listo para mostrar junto a la cita, sin otro round-trip."""
    citations = []
    for chunk_id in cited_chunks:
        chunk = chunk_by_id.get(chunk_id)
        if chunk is None:
            continue
        citations.append(
            ChunkCitation(chunk_id=chunk.chunk_id, text=chunk.text, source=chunk.source, section_type=chunk.section_type)
        )
    return citations


def make_finalize_compose_node(chunk_by_id: dict[str, Chunk]):
    def finalize_compose(state: ComposeState) -> dict:
        started_at = time.perf_counter()

        valid_chunk_ids = state["valid_chunk_ids"]
        sections = list(state["sections"])
        removed = 0

        for index, section in enumerate(sections):
            cited_ids = _CITATION_PATTERN.findall(section.body)
            still_hallucinated = [chunk_id for chunk_id in cited_ids if chunk_id not in valid_chunk_ids]
            if still_hallucinated:
                body = section.body
                for chunk_id in still_hallucinated:
                    body = body.replace(f"[[{chunk_id}]]", "")
                    removed += 1
                cited_chunks = [chunk_id for chunk_id in section.cited_chunks if chunk_id in valid_chunk_ids]
                section = section.model_copy(update={"body": body, "cited_chunks": cited_chunks})

            sections[index] = section.model_copy(
                update={"citations": _resolve_citations(section.cited_chunks, chunk_by_id)}
            )

        coverages = [
            classify_citation_coverage(section.cited_chunks, verification.supported, verification.issues)
            for section, verification in zip(sections, state["section_verification"])
        ]

        total_tokens = TokenUsage(
            input_tokens=sum(event.tokens.input_tokens for event in state["trace_log"] if event.tokens),
            output_tokens=sum(event.tokens.output_tokens for event in state["trace_log"] if event.tokens),
            total_tokens=sum(event.tokens.total_tokens for event in state["trace_log"] if event.tokens),
            estimated_cost_usd=sum(event.tokens.estimated_cost_usd for event in state["trace_log"] if event.tokens),
        )
        metrics = ComposeMetrics(
            total_duration_ms=sum(event.duration_ms for event in state["trace_log"]),
            total_tokens=total_tokens,
            retries_used=state["retry_count"],
            sections_supported=sum(1 for v in state["section_verification"] if v.supported),
            sections_needing_review=sum(1 for v in state["section_verification"] if not v.supported),
            hallucinated_citations_caught=state["hallucination_catches"],
            hallucinated_citations_removed=removed,
            **summarize_citation_coverage(coverages),
        )

        trace_event = TraceEvent(
            node="finalize_compose",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(sections)} secciones tras el ciclo de verificación/reintento",
            output_summary=(
                f"{metrics.sections_supported}/{len(sections)} secciones soportadas, "
                f"{removed} citas alucinadas eliminadas del texto final"
            ),
            reasoning=(
                "Garantía final en código: cualquier chunk_id citado que aún no "
                "exista entre las citas originales tras el ciclo de reintento se "
                "elimina del texto, para que el documento final nunca contenga "
                "una cita rota."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=None,
        )

        return {
            "sections": sections,
            "metrics": metrics,
            "trace_log": [*state["trace_log"], trace_event],
        }

    return finalize_compose
