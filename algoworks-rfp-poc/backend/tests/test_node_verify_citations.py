"""Tests del nodo verify_citations: skip automático por cita alucinada,
verificación NLI vía LLM, y routing de reintento (máx. 1)."""

from types import SimpleNamespace

from api.schemas import DraftSection, RetrievedChunk
from graph.nodes.verify_citations import make_verify_citations_node, should_retry
from tests.fakes import ScriptedChatModel


def _base_state(req_id: str, draft: DraftSection, hallucinated: list[str], retry_count: int = 0) -> dict:
    return {
        "drafts": {req_id: draft},
        "hallucinated_citations": {req_id: hallucinated},
        "retrieved": {req_id: [RetrievedChunk(chunk_id="chunk_001", score=0.9, justification="Relevante.")]},
        "pending_req_ids": [req_id],
        "verification": {},
        "retry_counts": {req_id: retry_count},
        "trace_log": [],
    }


def test_hallucinated_citation_is_marked_unsupported_without_calling_llm():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_099]].", cited_chunks=[])
    node = make_verify_citations_node(ScriptedChatModel())

    result = node(_base_state("req_001", draft, hallucinated=["chunk_099"]))

    verification = result["verification"]["req_001"]
    assert verification.supported is False
    assert "chunk_099" in verification.issues[0]
    assert "no se llamó al llm" in verification.reasoning.lower()
    assert verification.retries_used == 0
    assert result["pending_req_ids"] == ["req_001"]
    assert result["retry_counts"]["req_001"] == 1


def test_supported_verdict_from_llm_clears_pending():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])
    verdict = SimpleNamespace(supported=True, issues=[], confidence=0.95, reasoning="El chunk respalda la afirmación.")
    node = make_verify_citations_node(ScriptedChatModel(structured_responses=[verdict]))

    result = node(_base_state("req_001", draft, hallucinated=[]))

    verification = result["verification"]["req_001"]
    assert verification.supported is True
    assert verification.reasoning == "El chunk respalda la afirmación."
    assert verification.retries_used == 0
    assert result["pending_req_ids"] == []
    assert result["retry_counts"]["req_001"] == 0


def test_unsupported_verdict_exhausts_retry_budget():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])
    verdict = SimpleNamespace(supported=False, issues=["no respalda la afirmación"], confidence=0.2, reasoning="No hay respaldo.")
    node = make_verify_citations_node(ScriptedChatModel(structured_responses=[verdict]), max_retries=1)

    result = node(_base_state("req_001", draft, hallucinated=[], retry_count=1))

    verification = result["verification"]["req_001"]
    assert verification.supported is False
    assert verification.retries_used == 1
    assert result["pending_req_ids"] == []


class _RecordingChatModel:
    """Envuelve un ScriptedChatModel y guarda los prompts que recibió, para
    poder inspeccionar qué texto de chunk terminó realmente en el prompt."""

    def __init__(self, inner: ScriptedChatModel):
        self._inner = inner
        self.prompts: list[str] = []

    def with_structured_output(self, schema, include_raw: bool = False):
        inner_runnable = self._inner.with_structured_output(schema, include_raw=include_raw)

        class _Wrapped:
            def invoke(_self, prompt: str):
                self.prompts.append(prompt)
                return inner_runnable.invoke(prompt)

        return _Wrapped()


def test_verify_citations_uses_real_chunk_text_when_provided():
    draft = DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])
    verdict = SimpleNamespace(supported=True, issues=[], confidence=0.9, reasoning="El chunk respalda la afirmación.")
    llm = _RecordingChatModel(ScriptedChatModel(structured_responses=[verdict]))
    chunk_texts_by_id = {"chunk_001": "Texto real y específico del chunk, no la justificación."}
    node = make_verify_citations_node(llm, chunk_texts_by_id=chunk_texts_by_id)

    node(_base_state("req_001", draft, hallucinated=[]))

    assert len(llm.prompts) == 1
    assert "Texto real y específico del chunk" in llm.prompts[0]
    assert "Relevante." not in llm.prompts[0]


def test_should_retry_routes_to_generate_draft_when_pending():
    assert should_retry({"pending_req_ids": ["req_001"]}) == "generate_draft"


def test_should_retry_routes_to_compute_traceability_metrics_when_empty():
    assert should_retry({"pending_req_ids": []}) == "compute_traceability_metrics"
