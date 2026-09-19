"""Tests del nodo generate_draft: citación válida y detección de citas
alucinadas (chunk_id que no existe entre los chunks recuperados)."""

from types import SimpleNamespace

from api.schemas import Requirement, RetrievedChunk
from graph.nodes.generate_draft import make_generate_draft_node
from tests.fakes import ScriptedChatModel


def _state_for(req_id: str) -> dict:
    requirement = Requirement(req_id=req_id, text="Requisito de prueba.", section_target="experiencia_previa")
    retrieved_chunk = RetrievedChunk(chunk_id="chunk_001", score=0.9, justification="Relevante.")
    return {
        "requirements": [requirement],
        "retrieved": {req_id: [retrieved_chunk]},
        "pending_req_ids": [req_id],
        "drafts": {},
        "hallucinated_citations": {},
        "hallucination_catches": 0,
        "trace_log": [],
    }


def test_generate_draft_records_valid_citation():
    draft_output = SimpleNamespace(
        draft_text="Texto con cita [[chunk_001]].",
        reasoning="Se usó chunk_001 porque respalda directamente el requisito.",
    )
    llm = ScriptedChatModel(structured_responses=[draft_output])
    node = make_generate_draft_node(llm)

    result = node(_state_for("req_001"))

    draft = result["drafts"]["req_001"]
    assert draft.text == "Texto con cita [[chunk_001]]."
    assert draft.cited_chunks == ["chunk_001"]
    assert draft.reasoning == "Se usó chunk_001 porque respalda directamente el requisito."
    assert result["hallucinated_citations"]["req_001"] == []
    assert result["hallucination_catches"] == 0
    assert len(result["trace_log"]) == 1
    assert result["trace_log"][0].node == "generate_draft"
    assert result["trace_log"][0].duration_ms >= 0.0


def test_generate_draft_flags_hallucinated_citation_and_increments_running_total():
    draft_output = SimpleNamespace(
        draft_text="Texto con cita inventada [[chunk_099]].",
        reasoning="Se citó chunk_099.",
    )
    llm = ScriptedChatModel(structured_responses=[draft_output])
    node = make_generate_draft_node(llm)

    state = _state_for("req_001")
    state["hallucination_catches"] = 2  # ya venía de un pass anterior

    result = node(state)

    draft = result["drafts"]["req_001"]
    assert draft.cited_chunks == []
    assert result["hallucinated_citations"]["req_001"] == ["chunk_099"]
    assert result["hallucination_catches"] == 3
