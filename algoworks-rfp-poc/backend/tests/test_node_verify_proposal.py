"""Tests del nodo verify_proposal: skip automático por cita alucinada,
skip automático para secciones sin citas (carta/cierre), verificación NLI
vía LLM, y routing de reintento a nivel de documento completo (máx. 1)."""

from types import SimpleNamespace

from api.schemas import ProposalSection
from graph.nodes.verify_proposal import make_verify_proposal_node, should_retry_compose
from tests.fakes import ScriptedChatModel


def _base_state(sections: list[ProposalSection], hallucinated: dict, retry_count: int = 0) -> dict:
    return {
        "sections": sections,
        "hallucinated_section_citations": hallucinated,
        "retry_count": retry_count,
        "section_verification": [],
        "trace_log": [],
    }


def test_hallucinated_citation_is_marked_unsupported_without_calling_llm():
    section = ProposalSection(heading="Solución", body="Texto [[chunk_099]].", cited_chunks=[], source_req_ids=[])
    node = make_verify_proposal_node(ScriptedChatModel(), chunk_texts_by_id={})

    result = node(_base_state([section], hallucinated={0: ["chunk_099"]}))

    verification = result["section_verification"][0]
    assert verification.supported is False
    assert "chunk_099" in verification.issues[0]
    assert "no se llamó al llm" in verification.reasoning.lower()
    assert result["pending"] is True
    assert result["retry_count"] == 1


def test_section_without_citations_is_supported_by_default_without_calling_llm():
    section = ProposalSection(heading="Carta de presentación", body="Bienvenida sin citas.", cited_chunks=[], source_req_ids=[])
    node = make_verify_proposal_node(ScriptedChatModel(), chunk_texts_by_id={})

    result = node(_base_state([section], hallucinated={}))

    verification = result["section_verification"][0]
    assert verification.supported is True
    assert verification.confidence == 1.0
    assert result["pending"] is False


def test_supported_verdict_from_llm_clears_pending():
    section = ProposalSection(heading="Solución", body="Texto [[chunk_001]].", cited_chunks=["chunk_001"], source_req_ids=["req_001"])
    verdict = SimpleNamespace(supported=True, issues=[], confidence=0.95, reasoning="El chunk respalda la afirmación.")
    node = make_verify_proposal_node(
        ScriptedChatModel(structured_responses=[verdict]), chunk_texts_by_id={"chunk_001": "Texto real."}
    )

    result = node(_base_state([section], hallucinated={}))

    verification = result["section_verification"][0]
    assert verification.supported is True
    assert verification.reasoning == "El chunk respalda la afirmación."
    assert result["pending"] is False
    assert result["retry_count"] == 0


def test_unsupported_verdict_exhausts_retry_budget():
    section = ProposalSection(heading="Solución", body="Texto [[chunk_001]].", cited_chunks=["chunk_001"], source_req_ids=["req_001"])
    verdict = SimpleNamespace(supported=False, issues=["no respalda la afirmación"], confidence=0.2, reasoning="No hay respaldo.")
    node = make_verify_proposal_node(
        ScriptedChatModel(structured_responses=[verdict]),
        chunk_texts_by_id={"chunk_001": "Texto real."},
        max_retries=1,
    )

    result = node(_base_state([section], hallucinated={}, retry_count=1))

    verification = result["section_verification"][0]
    assert verification.supported is False
    assert verification.retries_used == 1
    assert result["pending"] is False
    assert result["retry_count"] == 1


def test_should_retry_compose_routes_to_compose_proposal_when_pending():
    assert should_retry_compose({"pending": True}) == "compose_proposal"


def test_should_retry_compose_routes_to_finalize_when_not_pending():
    assert should_retry_compose({"pending": False}) == "finalize_compose"
