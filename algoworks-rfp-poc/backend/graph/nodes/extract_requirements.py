"""Nodo extract_requirements: parsea el RFP a requisitos estructurados."""

import re
import time
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from api.schemas import Requirement, TraceEvent
from graph.llm_tracking import TokenAccumulator, invoke_structured_tracked
from graph.prompts import load_prompt
from graph.state import GraphState

SectionTarget = Literal["experiencia_previa", "capacidades_tecnicas", "equipo"]

_NUMBERED_LINE = re.compile(r"^\s*\d+[.)]\s*(.+)$")


class _ExtractedRequirement(BaseModel):
    req_id: str
    text: str
    section_target: SectionTarget


class _ExtractedRequirements(BaseModel):
    requirements: list[_ExtractedRequirement]


def _fallback_split_by_numbered_lines(rfp_text: str) -> list[Requirement]:
    requirements: list[Requirement] = []
    for line in rfp_text.splitlines():
        match = _NUMBERED_LINE.match(line)
        if not match:
            continue
        requirements.append(
            Requirement(
                req_id=f"req_{len(requirements) + 1:03d}",
                text=match.group(1).strip(),
                section_target="capacidades_tecnicas",
            )
        )
    return requirements


def make_extract_requirements_node(llm):
    prompt_template = load_prompt("extract_requirements.txt")

    def extract_requirements(state: GraphState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()
        prompt = prompt_template.format(rfp_text=state["rfp_text"])

        try:
            extracted = invoke_structured_tracked(llm, _ExtractedRequirements, prompt, accumulator)
            requirements = [
                Requirement(req_id=item.req_id, text=item.text, section_target=item.section_target)
                for item in extracted.requirements
            ]
            reasoning = (
                "Se extrajeron los requisitos usando structured output del LLM, "
                "con section_target restringido al enum cerrado."
            )
        except Exception:
            requirements = _fallback_split_by_numbered_lines(state["rfp_text"])
            reasoning = (
                "El structured output del LLM falló; se usó el fallback sin LLM "
                "de split por líneas numeradas."
            )

        trace_event = TraceEvent(
            node="extract_requirements",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"rfp_id={state['rfp_id']}, {len(state['rfp_text'])} caracteres de RFP",
            output_summary=f"{len(requirements)} requisitos extraídos",
            reasoning=reasoning,
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "requirements": requirements,
            "pending_req_ids": [r.req_id for r in requirements],
            "retry_counts": {r.req_id: 0 for r in requirements},
            "trace_log": [*state["trace_log"], trace_event],
        }

    return extract_requirements
