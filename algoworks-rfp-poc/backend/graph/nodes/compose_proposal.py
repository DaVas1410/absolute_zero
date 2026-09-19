"""Nodo compose_proposal: sintetiza los borradores ya verificados de cada
requisito en un documento de propuesta con secciones de negocio reales
(decididas por el modelo), reutilizando únicamente citas ya validadas por
el pipeline original — nunca vuelve a recuperar del corpus ni inventa
chunk_id nuevos."""

import re
import time
from datetime import datetime, timezone

from pydantic import BaseModel

from api.schemas import ProposalSection, TraceEvent
from graph.llm_tracking import TokenAccumulator, invoke_structured_tracked
from graph.prompts import load_prompt
from graph.state import ComposeState

_CITATION_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


class _ComposedSection(BaseModel):
    heading: str
    body: str
    source_req_ids: list[str]


class _ComposedDocument(BaseModel):
    sections: list[_ComposedSection]


def _build_requirements_block(state: ComposeState) -> str:
    lines = []
    for requirement in state["requirements"]:
        draft = state["drafts"].get(requirement.req_id)
        if draft is None:
            continue
        verification = state["verification"].get(requirement.req_id)
        issues_text = "; ".join(verification.issues) if verification and verification.issues else "ninguno"
        lines.append(
            f"- {requirement.req_id} ({requirement.text}): {draft.text}\n"
            f"  problemas conocidos: {issues_text}"
        )
    return "\n".join(lines)


def _build_retry_feedback(state: ComposeState) -> str:
    if state["retry_count"] == 0:
        return ""
    problems = [
        f"- Sección #{index} citaba chunk_id inexistentes: {', '.join(chunk_ids)}."
        for index, chunk_ids in state["hallucinated_section_citations"].items()
    ]
    problems += [
        f'- Sección "{v.heading}" no estaba respaldada: {"; ".join(v.issues)}.'
        for v in state["section_verification"]
        if not v.supported
    ]
    return (
        "Esta es una segunda pasada de composición. La versión anterior tuvo "
        "estos problemas — corregilos en esta versión:\n" + "\n".join(problems)
    )


def make_compose_proposal_node(llm):
    prompt_template = load_prompt("compose_proposal.txt")

    def compose_proposal(state: ComposeState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()

        prompt = prompt_template.format(
            requirements_block=_build_requirements_block(state),
            retry_feedback=_build_retry_feedback(state),
        )
        output = invoke_structured_tracked(llm, _ComposedDocument, prompt, accumulator)

        valid_chunk_ids = state["valid_chunk_ids"]
        sections: list[ProposalSection] = []
        hallucinated_section_citations: dict[int, list[str]] = {}
        new_hallucination_catches = 0

        for index, composed in enumerate(output.sections):
            cited_ids = list(dict.fromkeys(_CITATION_PATTERN.findall(composed.body)))
            valid_cited = [chunk_id for chunk_id in cited_ids if chunk_id in valid_chunk_ids]
            hallucinated = [chunk_id for chunk_id in cited_ids if chunk_id not in valid_chunk_ids]
            if hallucinated:
                hallucinated_section_citations[index] = hallucinated
                new_hallucination_catches += len(hallucinated)

            sections.append(
                ProposalSection(
                    heading=composed.heading,
                    body=composed.body,
                    cited_chunks=valid_cited,
                    source_req_ids=composed.source_req_ids,
                )
            )

        trace_event = TraceEvent(
            node="compose_proposal",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(state['requirements'])} requisitos verificados como insumo",
            output_summary=(
                f"{len(sections)} secciones compuestas, "
                f"{len(hallucinated_section_citations)} con citas alucinadas"
            ),
            reasoning=(
                "Se sintetizaron los borradores ya verificados en secciones de "
                "negocio decididas por el modelo; el post-procesamiento validó "
                "que cada chunk_id citado ya existiera entre las citas de algún "
                "borrador original (nunca se aceptan chunk_id nuevos)."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "sections": sections,
            "hallucinated_section_citations": hallucinated_section_citations,
            "hallucination_catches": state["hallucination_catches"] + new_hallucination_catches,
            "trace_log": [*state["trace_log"], trace_event],
        }

    return compose_proposal
