"""Tests del nodo compose_proposal: reutilización de citas válidas y
detección de citas alucinadas (chunk_id que no existe entre las citas
originales de los borradores de entrada)."""

from types import SimpleNamespace

from api.schemas import DraftSection, Requirement, VerificationResult
from graph.nodes.compose_proposal import make_compose_proposal_node
from tests.fakes import ScriptedChatModel


def _state_for(draft: DraftSection, valid_chunk_ids: set[str]) -> dict:
    requirement = Requirement(req_id=draft.req_id, text="Requisito de prueba.", section_target="experiencia_previa")
    return {
        "requirements": [requirement],
        "drafts": {draft.req_id: draft},
        "verification": {
            draft.req_id: VerificationResult(req_id=draft.req_id, supported=True, issues=[], confidence=0.9)
        },
        "valid_chunk_ids": valid_chunk_ids,
        "hallucinated_section_citations": {},
        "hallucination_catches": 0,
        "retry_count": 0,
        "section_verification": [],
        "trace_log": [],
    }


def test_compose_proposal_reuses_valid_citation():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])
    composed = SimpleNamespace(
        sections=[
            SimpleNamespace(
                heading="Solución propuesta", body="Resumen [[chunk_001]].", source_req_ids=["req_001"]
            )
        ]
    )
    llm = ScriptedChatModel(structured_responses=[composed])
    node = make_compose_proposal_node(llm)

    result = node(_state_for(draft, valid_chunk_ids={"chunk_001"}))

    section = result["sections"][0]
    assert section.heading == "Solución propuesta"
    assert section.cited_chunks == ["chunk_001"]
    assert result["hallucinated_section_citations"] == {}
    assert result["hallucination_catches"] == 0
    assert len(result["trace_log"]) == 1
    assert result["trace_log"][0].node == "compose_proposal"


def test_compose_proposal_flags_hallucinated_citation_and_excludes_it():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])
    composed = SimpleNamespace(
        sections=[
            SimpleNamespace(
                heading="Solución propuesta", body="Resumen [[chunk_099]].", source_req_ids=["req_001"]
            )
        ]
    )
    llm = ScriptedChatModel(structured_responses=[composed])
    node = make_compose_proposal_node(llm)

    state = _state_for(draft, valid_chunk_ids={"chunk_001"})
    state["hallucination_catches"] = 2  # ya venía de un pass anterior

    result = node(state)

    section = result["sections"][0]
    assert section.cited_chunks == []
    assert result["hallucinated_section_citations"] == {0: ["chunk_099"]}
    assert result["hallucination_catches"] == 3


def test_compose_proposal_includes_retry_feedback_on_second_pass():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])
    composed = SimpleNamespace(
        sections=[SimpleNamespace(heading="Solución", body="Texto [[chunk_001]].", source_req_ids=["req_001"])]
    )

    class _RecordingChatModel:
        def __init__(self, inner):
            self._inner = inner
            self.prompts: list[str] = []

        def with_structured_output(self, schema, method: str = "function_calling", include_raw: bool = False):
            inner_runnable = self._inner.with_structured_output(schema, method=method, include_raw=include_raw)

            class _Wrapped:
                def invoke(_self, prompt: str):
                    self.prompts.append(prompt)
                    return inner_runnable.invoke(prompt)

            return _Wrapped()

    llm = _RecordingChatModel(ScriptedChatModel(structured_responses=[composed]))
    node = make_compose_proposal_node(llm)

    state = _state_for(draft, valid_chunk_ids={"chunk_001"})
    state["retry_count"] = 1
    state["hallucinated_section_citations"] = {0: ["chunk_099"]}
    state["section_verification"] = [
        SimpleNamespace(heading="Solución", supported=False, issues=["no respalda la afirmación"])
    ]

    node(state)

    assert len(llm.prompts) == 1
    assert "segunda pasada" in llm.prompts[0].lower()
    assert "chunk_099" in llm.prompts[0]
