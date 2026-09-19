"""Tests del nodo retrieve_chunks: similitud + justificación por chunk."""

from graph.nodes.retrieve_chunks import make_retrieve_chunks_node
from api.schemas import Requirement
from tests.fakes import FakeVectorstore, ScriptedChatModel


def test_retrieve_chunks_attaches_justification_per_candidate():
    requirement = Requirement(req_id="req_001", text="experiencia en retail", section_target="experiencia_previa")
    vectorstore = FakeVectorstore(
        {
            "experiencia en retail": [
                ("chunk_002", "Proyecto de retail.", 0.9),
                ("chunk_001", "Proyecto de manufactura.", 0.5),
            ]
        }
    )
    llm = ScriptedChatModel(plain_responses=["Justificación A.", "Justificación B."])
    node = make_retrieve_chunks_node(llm, vectorstore, top_k=2)

    result = node({"requirements": [requirement], "trace_log": []})

    retrieved = result["retrieved"]["req_001"]
    assert [chunk.chunk_id for chunk in retrieved] == ["chunk_002", "chunk_001"]
    assert retrieved[0].score == 0.9
    assert retrieved[0].justification == "Justificación A."
    assert retrieved[1].justification == "Justificación B."
    assert len(result["trace_log"]) == 1
    assert result["trace_log"][0].node == "retrieve_chunks"
    assert result["trace_log"][0].duration_ms >= 0.0
    assert result["trace_log"][0].tokens.total_tokens == 0
