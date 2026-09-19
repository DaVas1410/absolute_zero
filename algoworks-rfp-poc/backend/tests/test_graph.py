"""Test de integración del grafo completo: camino feliz (todo soportado a
la primera) y camino adversarial (falla, 1 reintento, sigue sin soportarse
y queda marcado para revisión humana)."""

from types import SimpleNamespace

from graph.graph import run_pipeline
from tests.fakes import FakeEmbeddings, FakeVectorstore, ScriptedChatModel

VOCABULARY = ["experiencia", "kafka"]


def _vectorstore_for(requirement_text: str, chunk_id: str, chunk_text: str) -> FakeVectorstore:
    return FakeVectorstore({requirement_text: [(chunk_id, chunk_text, 0.9)]})


def test_run_pipeline_happy_path_supports_on_first_try():
    extracted = SimpleNamespace(
        requirements=[SimpleNamespace(req_id="req_001", text="experiencia previa", section_target="experiencia_previa")]
    )
    draft_output = SimpleNamespace(draft_text="Texto [[chunk_001]].", reasoning="Se citó el chunk más relevante.")
    verdict = SimpleNamespace(supported=True, issues=[], confidence=0.9, reasoning="El chunk respalda la afirmación.")

    llm_small = ScriptedChatModel(structured_responses=[extracted], plain_responses=["Justificación."])
    llm_large = ScriptedChatModel(structured_responses=[draft_output, verdict])
    vectorstore = _vectorstore_for("experiencia previa", "chunk_001", "Texto de referencia.")
    embeddings = FakeEmbeddings(VOCABULARY)
    chunk_texts_by_id = {"chunk_001": "Texto de referencia con experiencia."}

    result = run_pipeline(
        "rfp_001", "1. experiencia previa", llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id
    )

    assert result.rfp_id == "rfp_001"
    assert result.verification["req_001"].supported is True
    assert result.metrics.requirements_supported == 1
    assert result.reasoning_path_audit.is_consistent is True
    nodes = [event.node for event in result.trace_log]
    assert nodes == [
        "extract_requirements",
        "retrieve_chunks",
        "generate_draft",
        "verify_citations",
        "compute_traceability_metrics",
    ]


def test_run_pipeline_retries_once_then_gives_up():
    extracted = SimpleNamespace(
        requirements=[SimpleNamespace(req_id="req_001", text="experiencia previa", section_target="experiencia_previa")]
    )
    draft_output_1 = SimpleNamespace(draft_text="Texto [[chunk_001]].", reasoning="Primer intento.")
    draft_output_2 = SimpleNamespace(draft_text="Texto [[chunk_001]] revisado.", reasoning="Segundo intento.")
    unsupported = SimpleNamespace(
        supported=False, issues=["no respalda la afirmación"], confidence=0.1, reasoning="No hay respaldo suficiente."
    )

    llm_small = ScriptedChatModel(structured_responses=[extracted], plain_responses=["Justificación."])
    llm_large = ScriptedChatModel(structured_responses=[draft_output_1, unsupported, draft_output_2, unsupported])
    vectorstore = _vectorstore_for("experiencia previa", "chunk_001", "Texto de referencia.")
    embeddings = FakeEmbeddings(VOCABULARY)
    chunk_texts_by_id = {"chunk_001": "Texto de referencia con experiencia."}

    result = run_pipeline(
        "rfp_001", "1. experiencia previa", llm_small, llm_large, vectorstore, embeddings, chunk_texts_by_id
    )

    assert result.verification["req_001"].supported is False
    assert result.verification["req_001"].retries_used == 1
    assert result.metrics.retries_used == 1
    nodes = [event.node for event in result.trace_log]
    assert nodes == [
        "extract_requirements",
        "retrieve_chunks",
        "generate_draft",
        "verify_citations",
        "generate_draft",
        "verify_citations",
        "compute_traceability_metrics",
    ]
