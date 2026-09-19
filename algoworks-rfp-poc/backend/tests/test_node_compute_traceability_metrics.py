"""Tests del nodo compute_traceability_metrics: similitud coseno
borrador<->chunks citados, auditoría determinista del camino de ejecución
del grafo (incluyendo un estado deliberadamente roto), y agregación de
métricas de todo el pipeline."""

from datetime import datetime, timezone

from api.schemas import DraftSection, Requirement, RetrievedChunk, TokenUsage, TraceEvent, VerificationResult
from graph.nodes.compute_traceability_metrics import (
    audit_reasoning_path,
    cosine_similarity,
    make_compute_traceability_metrics_node,
)
from tests.fakes import FakeEmbeddings

VOCABULARY = ["kafka", "retail", "manufactura"]


def test_cosine_similarity_of_identical_vectors_is_one():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_of_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_of_zero_vector_is_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def _trace_event(node: str, duration_ms: float = 10.0, tokens=None) -> TraceEvent:
    return TraceEvent(
        node=node,
        timestamp=datetime.now(timezone.utc),
        input_summary="...",
        output_summary="...",
        reasoning="...",
        duration_ms=duration_ms,
        tokens=tokens,
    )


def _valid_state() -> dict:
    requirement = Requirement(req_id="req_001", text="experiencia en kafka", section_target="capacidades_tecnicas")
    retrieved_chunk = RetrievedChunk(chunk_id="chunk_001", score=0.9, justification="Relevante para kafka.")
    draft = DraftSection(req_id="req_001", text="Usamos kafka en el proyecto [[chunk_001]].", cited_chunks=["chunk_001"])
    verification = VerificationResult(req_id="req_001", supported=True, issues=[], confidence=0.9)

    return {
        "requirements": [requirement],
        "retrieved": {"req_001": [retrieved_chunk]},
        "drafts": {"req_001": draft},
        "verification": {"req_001": verification},
        "retry_counts": {"req_001": 0},
        "hallucination_catches": 0,
        "trace_log": [
            _trace_event("extract_requirements"),
            _trace_event("retrieve_chunks"),
            _trace_event("generate_draft", tokens=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)),
            _trace_event("verify_citations"),
        ],
    }


def test_audit_reasoning_path_returns_consistent_for_valid_single_pass_sequence():
    audit = audit_reasoning_path(_valid_state())

    assert audit.is_consistent is True
    assert audit.issues == []
    assert audit.node_sequence == [
        "extract_requirements", "retrieve_chunks", "generate_draft", "verify_citations",
    ]


def test_audit_reasoning_path_returns_consistent_for_a_valid_retry_sequence():
    state = _valid_state()
    state["trace_log"] = [
        _trace_event("extract_requirements"),
        _trace_event("retrieve_chunks"),
        _trace_event("generate_draft"),
        _trace_event("verify_citations"),
        _trace_event("generate_draft"),
        _trace_event("verify_citations"),
    ]

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is True


def test_audit_reasoning_path_flags_broken_node_sequence():
    state = _valid_state()
    state["trace_log"] = [_trace_event("extract_requirements"), _trace_event("generate_draft")]

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is False
    assert len(audit.issues) == 1


def test_audit_reasoning_path_flags_retries_beyond_the_configured_maximum():
    state = _valid_state()
    state["retry_counts"] = {"req_001": 5}

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is False
    assert any("req_001" in issue for issue in audit.issues)


def test_audit_reasoning_path_flags_hallucinated_citation_slipping_through():
    state = _valid_state()
    state["drafts"]["req_001"] = state["drafts"]["req_001"].model_copy(update={"cited_chunks": ["chunk_099"]})

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is False
    assert any("chunk_099" in issue for issue in audit.issues)


def test_audit_reasoning_path_flags_orphaned_verification_result():
    state = _valid_state()
    state["verification"]["req_999"] = VerificationResult(req_id="req_999", supported=True, issues=[], confidence=0.5)

    audit = audit_reasoning_path(state)

    assert audit.is_consistent is False
    assert any("req_999" in issue for issue in audit.issues)


def test_compute_traceability_metrics_node_aggregates_metrics_and_attaches_similarities():
    embeddings = FakeEmbeddings(VOCABULARY)
    chunk_texts_by_id = {"chunk_001": "Arquitectura basada en kafka."}
    node = make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id)

    result = node(_valid_state())

    draft = result["drafts"]["req_001"]
    assert draft.citation_similarities[0].chunk_id == "chunk_001"
    assert draft.citation_similarities[0].similarity == 1.0
    assert draft.overall_similarity == 1.0

    metrics = result["metrics"]
    assert metrics.requirements_supported == 1
    assert metrics.requirements_needing_review == 0
    assert metrics.total_tokens.total_tokens == 15
    assert metrics.hallucinated_citations_caught == 0
    assert metrics.retries_used == 0
    assert metrics.fully_cited_count == 1
    assert metrics.uncited_count == 0
    assert metrics.traceability_rate == 1.0

    assert result["reasoning_path_audit"].is_consistent is True
    assert result["trace_log"][-1].node == "compute_traceability_metrics"
    assert result["trace_log"][-1].tokens is None


def test_compute_traceability_metrics_node_counts_uncited_requirement():
    embeddings = FakeEmbeddings(VOCABULARY)
    state = _valid_state()
    state["drafts"]["req_001"] = state["drafts"]["req_001"].model_copy(update={"cited_chunks": []})
    node = make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id={})

    result = node(state)

    metrics = result["metrics"]
    assert metrics.uncited_count == 1
    assert metrics.fully_cited_count == 0
    assert metrics.uncited_rate == 1.0


def test_compute_traceability_metrics_node_skips_similarity_when_no_valid_citations():
    embeddings = FakeEmbeddings(VOCABULARY)
    node = make_compute_traceability_metrics_node(embeddings, chunk_texts_by_id={})

    result = node(_valid_state())

    draft = result["drafts"]["req_001"]
    assert draft.citation_similarities == []
    assert draft.overall_similarity == 0.0
