"""Construye y compila el grafo LangGraph del pipeline de RFP:
extract_requirements -> retrieve_chunks -> generate_draft -> verify_citations
-> compute_traceability_metrics, con reintento condicional de
verify_citations a generate_draft (max. 1)."""

from langgraph.graph import END, StateGraph

from api.schemas import PipelineResult
from graph.nodes.compute_traceability_metrics import make_compute_traceability_metrics_node
from graph.nodes.extract_requirements import make_extract_requirements_node
from graph.nodes.generate_draft import make_generate_draft_node
from graph.nodes.retrieve_chunks import make_retrieve_chunks_node
from graph.nodes.verify_citations import make_verify_citations_node, should_retry
from graph.state import GraphState

DEFAULT_TOP_K = 3


def build_graph(
    llm_small,
    llm_large,
    vectorstore,
    embeddings,
    chunk_texts_by_id: dict[str, str],
    top_k: int = DEFAULT_TOP_K,
):
    graph = StateGraph(GraphState)
    graph.add_node("extract_requirements", make_extract_requirements_node(llm_small))
    graph.add_node("retrieve_chunks", make_retrieve_chunks_node(llm_small, vectorstore, top_k))
    graph.add_node("generate_draft", make_generate_draft_node(llm_large))
    graph.add_node("verify_citations", make_verify_citations_node(llm_large))
    graph.add_node(
        "compute_traceability_metrics",
        make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id),
    )

    graph.set_entry_point("extract_requirements")
    graph.add_edge("extract_requirements", "retrieve_chunks")
    graph.add_edge("retrieve_chunks", "generate_draft")
    graph.add_edge("generate_draft", "verify_citations")
    graph.add_conditional_edges(
        "verify_citations",
        should_retry,
        {"generate_draft": "generate_draft", "compute_traceability_metrics": "compute_traceability_metrics"},
    )
    graph.add_edge("compute_traceability_metrics", END)
    return graph.compile()


def run_pipeline(
    rfp_id: str,
    rfp_text: str,
    llm_small,
    llm_large,
    vectorstore,
    embeddings,
    chunk_texts_by_id: dict[str, str],
    top_k: int = DEFAULT_TOP_K,
) -> PipelineResult:
    compiled_graph = build_graph(llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id, top_k)
    initial_state: GraphState = {
        "rfp_id": rfp_id,
        "rfp_text": rfp_text,
        "requirements": [],
        "retrieved": {},
        "pending_req_ids": [],
        "hallucinated_citations": {},
        "hallucination_catches": 0,
        "drafts": {},
        "verification": {},
        "retry_counts": {},
        "trace_log": [],
        "metrics": None,
        "reasoning_path_audit": None,
    }
    final_state = compiled_graph.invoke(initial_state)
    return PipelineResult(
        rfp_id=rfp_id,
        requirements=final_state["requirements"],
        retrieved=final_state["retrieved"],
        drafts=final_state["drafts"],
        verification=final_state["verification"],
        trace_log=final_state["trace_log"],
        metrics=final_state["metrics"],
        reasoning_path_audit=final_state["reasoning_path_audit"],
    )
