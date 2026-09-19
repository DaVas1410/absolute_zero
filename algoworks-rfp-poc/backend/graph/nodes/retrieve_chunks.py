"""Nodo retrieve_chunks: recupera chunks candidatos por similitud y genera
su justificación en lenguaje natural."""

import time
from datetime import datetime, timezone

from api.schemas import RetrievedChunk, TraceEvent
from graph.llm_tracking import TokenAccumulator, invoke_tracked
from graph.prompts import load_prompt
from graph.state import GraphState
from rag.store import similarity_search

DEFAULT_TOP_K = 3


def make_retrieve_chunks_node(llm, vectorstore, top_k: int = DEFAULT_TOP_K):
    prompt_template = load_prompt("retrieve_chunks_justification.txt")

    def retrieve_chunks(state: GraphState) -> dict:
        started_at = time.perf_counter()
        accumulator = TokenAccumulator()
        retrieved: dict[str, list[RetrievedChunk]] = {}

        for requirement in state["requirements"]:
            candidates = similarity_search(vectorstore, requirement.text, k=top_k)
            retrieved_for_requirement = []
            for chunk_id, chunk_text, score, source in candidates:
                justification_prompt = prompt_template.format(
                    requirement_text=requirement.text, chunk_text=chunk_text
                )
                justification = invoke_tracked(llm, justification_prompt, accumulator)
                retrieved_for_requirement.append(
                    RetrievedChunk(
                        chunk_id=chunk_id, score=score, justification=justification, source=source
                    )
                )
            retrieved[requirement.req_id] = retrieved_for_requirement

        trace_event = TraceEvent(
            node="retrieve_chunks",
            timestamp=datetime.now(timezone.utc),
            input_summary=f"{len(state['requirements'])} requisitos",
            output_summary=", ".join(
                f"{req_id}: {len(chunks)} chunks" for req_id, chunks in retrieved.items()
            ),
            reasoning=(
                f"Se recuperaron hasta {top_k} chunks por similitud coseno por "
                "requisito y se generó una justificación en lenguaje natural "
                "para cada uno."
            ),
            duration_ms=(time.perf_counter() - started_at) * 1000,
            tokens=accumulator.total(),
        )

        return {
            "retrieved": retrieved,
            "trace_log": [*state["trace_log"], trace_event],
        }

    return retrieve_chunks
