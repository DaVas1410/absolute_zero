"""Nodo generate_draft: redacta el borrador de cada sección citando
chunk_id inline, y valida en código que las citas existan de verdad."""

import re
import time
from datetime import datetime, timezone

from pydantic import BaseModel

from api.schemas import DraftSection, RetrievedChunk, TraceEvent
from graph.llm_tracking import TokenAccumulator, invoke_structured_tracked
from graph.prompts import load_prompt
from graph.state import GraphState

_CITATION_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


class _DraftOutput(BaseModel):
    draft_text: str
    reasoning: str


def _build_chunks_block(chunks: list[RetrievedChunk]) -> str:
    return "\n".join(f"- {chunk.chunk_id}: {chunk.justification}" for chunk in chunks)


def make_generate_draft_node(llm):
    prompt_template = load_prompt("generate_draft.txt")

    def generate_draft(state: GraphState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()
        drafts = dict(state["drafts"])
        hallucinated_citations = dict(state["hallucinated_citations"])
        hallucination_catches = state["hallucination_catches"]
        requirements_by_id = {r.req_id: r for r in state["requirements"]}

        for req_id in state["pending_req_ids"]:
            requirement = requirements_by_id[req_id]
            retrieved_chunks = state["retrieved"].get(req_id, [])
            valid_chunk_ids = {chunk.chunk_id for chunk in retrieved_chunks}

            prompt = prompt_template.format(
                requirement_text=requirement.text,
                chunks_block=_build_chunks_block(retrieved_chunks),
            )
            output = invoke_structured_tracked(llm, _DraftOutput, prompt, accumulator)
            draft_text = output.draft_text.strip()

            cited_ids = list(dict.fromkeys(_CITATION_PATTERN.findall(draft_text)))
            valid_cited = [chunk_id for chunk_id in cited_ids if chunk_id in valid_chunk_ids]
            hallucinated = [chunk_id for chunk_id in cited_ids if chunk_id not in valid_chunk_ids]

            drafts[req_id] = DraftSection(
                req_id=req_id,
                text=draft_text,
                cited_chunks=valid_cited,
                reasoning=output.reasoning,
            )
            hallucinated_citations[req_id] = hallucinated
            hallucination_catches += len(hallucinated)

        trace_event = TraceEvent(
            node="generate_draft",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(state['pending_req_ids'])} requisitos a (re)generar",
            output_summary=(
                f"{len(state['pending_req_ids'])} DraftSection generados, "
                f"{sum(1 for ids in hallucinated_citations.values() if ids)} con citas alucinadas"
            ),
            reasoning=(
                "El post-procesamiento validó que cada chunk_id citado exista "
                "entre los chunks recuperados para ese requisito; los que no "
                "existen se registran como citas alucinadas para verify_citations."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "drafts": drafts,
            "hallucinated_citations": hallucinated_citations,
            "hallucination_catches": hallucination_catches,
            "trace_log": [*state["trace_log"], trace_event],
        }

    return generate_draft
