"""Test de integración del grafo de composición: camino feliz (documento
soportado a la primera) y camino adversarial (una sección cita un chunk_id
inventado; se reintenta 1 vez y, si sigue sin corregirse, la cita se
elimina en código para que el documento final nunca quede roto)."""

from types import SimpleNamespace

from api.schemas import Chunk, ChunkCitation, DraftSection, Requirement, VerificationResult
from graph.compose_graph import run_compose
from tests.fakes import ScriptedChatModel


def _inputs():
    requirements = [Requirement(req_id="req_001", text="Requisito de prueba.", section_target="experiencia_previa")]
    drafts = {"req_001": DraftSection(req_id="req_001", text="Texto [[chunk_001]].", cited_chunks=["chunk_001"])}
    verification = {"req_001": VerificationResult(req_id="req_001", supported=True, issues=[], confidence=0.9)}
    return requirements, drafts, verification


def _chunk_by_id():
    return {
        "chunk_001": Chunk(
            chunk_id="chunk_001", text="Texto real.", source="doc_a.md", section_type="experiencia_previa"
        )
    }


def test_run_compose_happy_path_supports_on_first_try():
    requirements, drafts, verification = _inputs()
    composed = SimpleNamespace(
        sections=[SimpleNamespace(heading="Solución propuesta", body="Resumen [[chunk_001]].", source_req_ids=["req_001"])]
    )
    verdict = SimpleNamespace(supported=True, issues=[], confidence=0.9, reasoning="El chunk respalda la afirmación.")
    llm = ScriptedChatModel(structured_responses=[composed, verdict])

    result = run_compose("rfp_001", requirements, drafts, verification, llm, chunk_by_id=_chunk_by_id())

    assert result.rfp_id == "rfp_001"
    assert len(result.sections) == 1
    assert result.sections[0].cited_chunks == ["chunk_001"]
    assert result.sections[0].citations == [
        ChunkCitation(chunk_id="chunk_001", text="Texto real.", source="doc_a.md", section_type="experiencia_previa")
    ]
    assert result.verification[0].supported is True
    assert result.metrics.sections_supported == 1
    assert result.metrics.hallucinated_citations_removed == 0
    assert result.metrics.fully_cited_count == 1
    assert result.metrics.traceability_rate == 1.0
    nodes = [event.node for event in result.trace_log]
    assert nodes == ["compose_proposal", "verify_proposal", "finalize_compose"]


def test_run_compose_retries_once_then_strips_unfixed_hallucination():
    requirements, drafts, verification = _inputs()
    composed_1 = SimpleNamespace(
        sections=[SimpleNamespace(heading="Solución propuesta", body="Texto inventado [[chunk_099]].", source_req_ids=["req_001"])]
    )
    composed_2 = SimpleNamespace(
        sections=[SimpleNamespace(heading="Solución propuesta", body="Sigue citando mal [[chunk_099]].", source_req_ids=["req_001"])]
    )
    llm = ScriptedChatModel(structured_responses=[composed_1, composed_2])

    result = run_compose("rfp_001", requirements, drafts, verification, llm, chunk_by_id=_chunk_by_id())

    assert "[[chunk_099]]" not in result.sections[0].body
    assert result.sections[0].citations == []  # el unico chunk citado (chunk_099) nunca fue valido
    assert result.metrics.retries_used == 1
    assert result.metrics.hallucinated_citations_removed == 1
    assert result.metrics.hallucinated_citations_caught == 2  # detectada en el intento 1 y de nuevo en el 2
    assert result.metrics.uncited_count == 1  # sin citas validas tras el strip -> uncited
    assert result.metrics.uncited_rate == 1.0
    nodes = [event.node for event in result.trace_log]
    assert nodes == [
        "compose_proposal",
        "verify_proposal",
        "compose_proposal",
        "verify_proposal",
        "finalize_compose",
    ]
