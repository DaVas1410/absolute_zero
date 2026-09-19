"""Nodo verify_proposal: verifica cada sección compuesta contra sus
fragmentos citados, y decide si se recompone el documento completo
(máx. 1 reintento, análogo a verify_citations pero a nivel de documento)."""

import time
from datetime import datetime, timezone

from pydantic import BaseModel

from api.schemas import ProposalSectionVerification, TraceEvent
from graph.llm_tracking import TokenAccumulator, invoke_structured_tracked
from graph.prompts import load_prompt
from graph.state import MAX_COMPOSE_RETRIES, ComposeState

_NO_LLM_CALL_REASONING = (
    "No se llamó al LLM de verificación: se detectaron citas a chunk_id "
    "inexistentes antes de esta etapa."
)
_NO_CITATIONS_REASONING = (
    "Sección de encuadre, plantilla comercial o de cierre sin citas; no hace "
    "afirmaciones factuales verificables sobre Algoworks y por lo tanto no "
    "requiere verificación NLI."
)


class _NliVerdict(BaseModel):
    supported: bool
    issues: list[str]
    confidence: float
    reasoning: str


def _build_chunks_block(cited_chunks: list[str], chunk_texts_by_id: dict[str, str]) -> str:
    return "\n".join(
        f"- {chunk_id}: {chunk_texts_by_id[chunk_id]}"
        for chunk_id in cited_chunks
        if chunk_id in chunk_texts_by_id
    )


def make_verify_proposal_node(
    llm, chunk_texts_by_id: dict[str, str], max_retries: int = MAX_COMPOSE_RETRIES
):
    prompt_template = load_prompt("verify_proposal_section.txt")

    def verify_proposal(state: ComposeState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()
        section_verification: list[ProposalSectionVerification] = []
        any_unsupported = False
        retries_used_so_far = state["retry_count"]

        for index, section in enumerate(state["sections"]):
            hallucinated = state["hallucinated_section_citations"].get(index, [])

            if hallucinated:
                result = ProposalSectionVerification(
                    heading=section.heading,
                    supported=False,
                    issues=[
                        f"El chunk_id '{chunk_id}' citado no existe entre las citas originales."
                        for chunk_id in hallucinated
                    ],
                    confidence=0.0,
                    reasoning=_NO_LLM_CALL_REASONING,
                    retries_used=retries_used_so_far,
                )
            elif not section.cited_chunks:
                result = ProposalSectionVerification(
                    heading=section.heading,
                    supported=True,
                    issues=[],
                    confidence=1.0,
                    reasoning=_NO_CITATIONS_REASONING,
                    retries_used=retries_used_so_far,
                )
            else:
                prompt = prompt_template.format(
                    section_body=section.body,
                    chunks_block=_build_chunks_block(section.cited_chunks, chunk_texts_by_id),
                )
                verdict = invoke_structured_tracked(llm, _NliVerdict, prompt, accumulator)
                result = ProposalSectionVerification(
                    heading=section.heading,
                    supported=verdict.supported,
                    issues=verdict.issues,
                    confidence=verdict.confidence,
                    reasoning=verdict.reasoning,
                    retries_used=retries_used_so_far,
                )

            section_verification.append(result)
            if not result.supported:
                any_unsupported = True

        will_retry = any_unsupported and retries_used_so_far < max_retries

        trace_event = TraceEvent(
            node="verify_proposal",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(state['sections'])} secciones verificadas",
            output_summary=(
                f"{sum(1 for r in section_verification if r.supported)}/{len(section_verification)} soportadas, "
                f"{'documento enviado a reintento' if will_retry else 'documento finalizado'}"
            ),
            reasoning=(
                "Las secciones con citas alucinadas se marcan automáticamente "
                "como no soportadas sin llamar al LLM; las secciones sin citas "
                "(carta de presentación, cierre, plantillas comerciales como "
                "equipo/SLA/precio) se consideran soportadas por defecto al no "
                "hacer afirmaciones factuales; el resto se verifica con un "
                "prompt tipo NLI. Si alguna sección no está soportada y quedan "
                "reintentos disponibles, se recompone el documento completo "
                f"(máx. {max_retries} reintento(s))."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "section_verification": section_verification,
            "retry_count": retries_used_so_far + 1 if will_retry else retries_used_so_far,
            "pending": will_retry,
            "trace_log": [*state["trace_log"], trace_event],
        }

    return verify_proposal


def should_retry_compose(state: ComposeState) -> str:
    return "compose_proposal" if state["pending"] else "finalize_compose"
