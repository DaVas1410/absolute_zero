"""Construye y compila el grafo de composición de propuesta:
compose_proposal -> verify_proposal -> (reintento a compose_proposal |
finalize_compose), con reintento condicional del documento completo
(máx. 1). Corre por separado de run_pipeline, sobre un PipelineResult ya
calculado — nunca vuelve a extraer requisitos ni a recuperar del corpus."""

from langgraph.graph import END, StateGraph

from api.schemas import Chunk, DraftSection, ProposalDocument, Requirement, VerificationResult
from graph.nodes.compose_proposal import make_compose_proposal_node
from graph.nodes.finalize_compose import make_finalize_compose_node
from graph.nodes.verify_proposal import make_verify_proposal_node, should_retry_compose
from graph.state import ComposeState


def build_compose_graph(llm, chunk_by_id: dict[str, Chunk]):
    chunk_texts_by_id = {chunk_id: chunk.text for chunk_id, chunk in chunk_by_id.items()}

    graph = StateGraph(ComposeState)
    graph.add_node("compose_proposal", make_compose_proposal_node(llm))
    graph.add_node("verify_proposal", make_verify_proposal_node(llm, chunk_texts_by_id))
    graph.add_node("finalize_compose", make_finalize_compose_node(chunk_by_id))

    graph.set_entry_point("compose_proposal")
    graph.add_edge("compose_proposal", "verify_proposal")
    graph.add_conditional_edges(
        "verify_proposal",
        should_retry_compose,
        {"compose_proposal": "compose_proposal", "finalize_compose": "finalize_compose"},
    )
    graph.add_edge("finalize_compose", END)
    return graph.compile()


def run_compose(
    rfp_id: str,
    requirements: list[Requirement],
    drafts: dict[str, DraftSection],
    verification: dict[str, VerificationResult],
    llm,
    chunk_by_id: dict[str, Chunk],
) -> ProposalDocument:
    valid_chunk_ids: set[str] = set()
    for draft in drafts.values():
        valid_chunk_ids.update(draft.cited_chunks)

    compiled_graph = build_compose_graph(llm, chunk_by_id)
    initial_state: ComposeState = {
        "rfp_id": rfp_id,
        "requirements": requirements,
        "drafts": drafts,
        "verification": verification,
        "valid_chunk_ids": valid_chunk_ids,
        "sections": [],
        "section_verification": [],
        "hallucinated_section_citations": {},
        "hallucination_catches": 0,
        "retry_count": 0,
        "pending": False,
        "trace_log": [],
        "metrics": None,
    }
    final_state = compiled_graph.invoke(initial_state)
    return ProposalDocument(
        rfp_id=rfp_id,
        sections=final_state["sections"],
        verification=final_state["section_verification"],
        trace_log=final_state["trace_log"],
        metrics=final_state["metrics"],
    )
