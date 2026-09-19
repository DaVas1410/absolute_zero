"""Nodo compute_traceability_metrics: corre una sola vez, cuando el retry
loop se vació. Calcula similitud coseno borrador<->chunks citados, audita
de forma determinista (sin LLM) el camino de ejecución del grafo, y agrega
las métricas de todo el pipeline (latencia, tokens, reintentos)."""

import math
import time
from datetime import datetime, timezone

from api.schemas import (
    CitationSimilarity,
    DraftSection,
    PipelineMetrics,
    ReasoningPathAudit,
    TokenUsage,
    TraceEvent,
)
from graph.state import MAX_GENERATE_RETRIES, GraphState


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    length = len(vectors[0])
    return [sum(vector[i] for vector in vectors) / len(vectors) for i in range(length)]


def _compute_draft_similarities(
    draft: DraftSection,
    retrieved_chunks,
    chunk_texts_by_id: dict[str, str],
    embeddings,
) -> tuple[list[CitationSimilarity], float]:
    valid_chunk_ids = {chunk.chunk_id for chunk in retrieved_chunks}
    valid_cited = [
        chunk_id
        for chunk_id in draft.cited_chunks
        if chunk_id in valid_chunk_ids and chunk_id in chunk_texts_by_id
    ]
    if not valid_cited:
        return [], 0.0

    draft_embedding = embeddings.embed_query(draft.text)
    citation_similarities: list[CitationSimilarity] = []
    chunk_embeddings: list[list[float]] = []
    for chunk_id in valid_cited:
        chunk_embedding = embeddings.embed_query(chunk_texts_by_id[chunk_id])
        chunk_embeddings.append(chunk_embedding)
        citation_similarities.append(
            CitationSimilarity(chunk_id=chunk_id, similarity=cosine_similarity(draft_embedding, chunk_embedding))
        )

    overall_similarity = cosine_similarity(draft_embedding, _mean_vector(chunk_embeddings))
    return citation_similarities, overall_similarity


def audit_reasoning_path(state: GraphState) -> ReasoningPathAudit:
    node_sequence = [event.node for event in state["trace_log"]]
    issues: list[str] = []

    expected_prefix = ["extract_requirements", "retrieve_chunks"]
    body = node_sequence[len(expected_prefix):]
    valid_shape = (
        node_sequence[: len(expected_prefix)] == expected_prefix
        and len(body) >= 2
        and len(body) % 2 == 0
        and body[-1] == "verify_citations"
        and all(
            body[i] == "generate_draft" and body[i + 1] == "verify_citations"
            for i in range(0, len(body), 2)
        )
    )
    if not valid_shape:
        issues.append(
            f"La secuencia de nodos {node_sequence} no sigue el patrón esperado "
            "extract_requirements, retrieve_chunks, (generate_draft, verify_citations)+."
        )

    for req_id, retries in state["retry_counts"].items():
        if retries > MAX_GENERATE_RETRIES:
            issues.append(
                f"El requisito {req_id} usó {retries} reintentos, más que el "
                f"máximo permitido ({MAX_GENERATE_RETRIES})."
            )

    for req_id, draft in state["drafts"].items():
        valid_chunk_ids = {chunk.chunk_id for chunk in state["retrieved"].get(req_id, [])}
        for chunk_id in draft.cited_chunks:
            if chunk_id not in valid_chunk_ids:
                issues.append(
                    f"El draft de {req_id} cita chunk_id '{chunk_id}', que no "
                    "existe entre los chunks recuperados para ese requisito."
                )

    requirement_ids = {requirement.req_id for requirement in state["requirements"]}
    for req_id in state["verification"]:
        if req_id not in requirement_ids:
            issues.append(
                f"Hay un VerificationResult para req_id '{req_id}', que no "
                "aparece entre los requisitos extraídos."
            )

    return ReasoningPathAudit(is_consistent=len(issues) == 0, node_sequence=node_sequence, issues=issues)


def make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id: dict[str, str]):
    def compute_traceability_metrics(state: GraphState) -> dict:
        started_at = time.perf_counter()

        drafts = dict(state["drafts"])
        for req_id, draft in drafts.items():
            retrieved_chunks = state["retrieved"].get(req_id, [])
            citation_similarities, overall_similarity = _compute_draft_similarities(
                draft, retrieved_chunks, chunk_texts_by_id, embeddings
            )
            drafts[req_id] = draft.model_copy(
                update={"citation_similarities": citation_similarities, "overall_similarity": overall_similarity}
            )

        reasoning_path_audit = audit_reasoning_path(state)

        total_tokens = TokenUsage(
            input_tokens=sum(event.tokens.input_tokens for event in state["trace_log"] if event.tokens),
            output_tokens=sum(event.tokens.output_tokens for event in state["trace_log"] if event.tokens),
            total_tokens=sum(event.tokens.total_tokens for event in state["trace_log"] if event.tokens),
            estimated_cost_usd=sum(event.tokens.estimated_cost_usd for event in state["trace_log"] if event.tokens),
        )
        metrics = PipelineMetrics(
            total_duration_ms=sum(event.duration_ms for event in state["trace_log"]),
            total_tokens=total_tokens,
            retries_used=sum(state["retry_counts"].values()),
            requirements_supported=sum(1 for v in state["verification"].values() if v.supported),
            requirements_needing_review=sum(1 for v in state["verification"].values() if not v.supported),
            hallucinated_citations_caught=state["hallucination_catches"],
        )

        trace_event = TraceEvent(
            node="compute_traceability_metrics",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(drafts)} borradores finales, {len(state['trace_log'])} eventos de trace previos",
            output_summary=(
                f"{metrics.requirements_supported}/{len(state['verification'])} requisitos soportados, "
                f"{metrics.hallucinated_citations_caught} citas alucinadas detectadas en total"
            ),
            reasoning=(
                "Auditoría determinista (sin LLM) de la secuencia de nodos y las "
                "citas, más similitud coseno borrador<->chunks citados: camino "
                f"{'consistente' if reasoning_path_audit.is_consistent else 'con problemas'}."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=None,
        )

        return {
            "drafts": drafts,
            "trace_log": [*state["trace_log"], trace_event],
            "metrics": metrics,
            "reasoning_path_audit": reasoning_path_audit,
        }

    return compute_traceability_metrics
