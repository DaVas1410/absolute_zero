"""Nodo verify_citations: verifica si cada borrador está respaldado por
sus citas, y decide si se reintenta generate_draft (máx. 1 vez)."""

import time
from datetime import datetime, timezone

from pydantic import BaseModel

from api.schemas import RetrievedChunk, TraceEvent, VerificationResult
from graph.llm_tracking import TokenAccumulator, invoke_structured_tracked
from graph.prompts import load_prompt
from graph.state import MAX_GENERATE_RETRIES, GraphState

_NO_LLM_CALL_REASONING = (
    "No se llamó al LLM de verificación: se detectaron citas a chunk_id "
    "inexistentes antes de esta etapa."
)


class _NliVerdict(BaseModel):
    supported: bool
    issues: list[str]
    confidence: float
    reasoning: str


def _build_chunks_block(cited_chunks: list[str], retrieved_chunks: list[RetrievedChunk]) -> str:
    chunk_by_id = {chunk.chunk_id: chunk for chunk in retrieved_chunks}
    lines = [
        f"- {chunk_id}: {chunk_by_id[chunk_id].justification}"
        for chunk_id in cited_chunks
        if chunk_id in chunk_by_id
    ]
    return "\n".join(lines)


def make_verify_citations_node(llm, max_retries: int = MAX_GENERATE_RETRIES):
    prompt_template = load_prompt("verify_citations.txt")

    def verify_citations(state: GraphState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()
        verification = dict(state["verification"])
        retry_counts = dict(state["retry_counts"])
        next_pending: list[str] = []

        for req_id in state["pending_req_ids"]:
            draft = state["drafts"][req_id]
            hallucinated = state["hallucinated_citations"].get(req_id, [])
            retries_used_so_far = retry_counts.get(req_id, 0)

            if hallucinated:
                result = VerificationResult(
                    req_id=req_id,
                    supported=False,
                    issues=[
                        f"El chunk_id '{chunk_id}' citado no existe entre los chunks recuperados."
                        for chunk_id in hallucinated
                    ],
                    confidence=0.0,
                    reasoning=_NO_LLM_CALL_REASONING,
                    retries_used=retries_used_so_far,
                )
            else:
                prompt = prompt_template.format(
                    draft_text=draft.text,
                    chunks_block=_build_chunks_block(draft.cited_chunks, state["retrieved"].get(req_id, [])),
                )
                verdict = invoke_structured_tracked(llm, _NliVerdict, prompt, accumulator)
                result = VerificationResult(
                    req_id=req_id,
                    supported=verdict.supported,
                    issues=verdict.issues,
                    confidence=verdict.confidence,
                    reasoning=verdict.reasoning,
                    retries_used=retries_used_so_far,
                )

            verification[req_id] = result

            if not result.supported and retries_used_so_far < max_retries:
                retry_counts[req_id] = retries_used_so_far + 1
                next_pending.append(req_id)

        trace_event = TraceEvent(
            node="verify_citations",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(state['pending_req_ids'])} borradores verificados",
            output_summary=(
                f"{sum(1 for r in verification.values() if r.supported)} soportados, "
                f"{len(next_pending)} enviados a reintento"
            ),
            reasoning=(
                "Los requisitos con citas alucinadas se marcan automáticamente "
                "como no soportados sin llamar al LLM; el resto se verifica con "
                "un prompt tipo NLI. Los no soportados con reintentos disponibles "
                f"vuelven a generate_draft (máx. {max_retries} reintento(s)); el "
                "resto queda marcado para revisión humana."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "verification": verification,
            "retry_counts": retry_counts,
            "pending_req_ids": next_pending,
            "trace_log": [*state["trace_log"], trace_event],
        }

    return verify_citations


def should_retry(state: GraphState) -> str:
    return "generate_draft" if state["pending_req_ids"] else "compute_traceability_metrics"
