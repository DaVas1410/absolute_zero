"""Tests del clasificador código-only de cobertura de citas, compartido
entre compute_traceability_metrics (pipeline principal) y finalize_compose
(compose_proposal)."""

from graph.citation_coverage import classify_citation_coverage, summarize_citation_coverage


def test_classify_no_citations_is_uncited():
    assert classify_citation_coverage([], supported=True, issues=[]) == "uncited"


def test_classify_cited_and_supported_without_issues_is_fully_cited():
    assert classify_citation_coverage(["chunk_001"], supported=True, issues=[]) == "fully_cited"


def test_classify_cited_but_unsupported_is_partially_cited():
    assert classify_citation_coverage(["chunk_001"], supported=False, issues=["cita rota"]) == "partially_cited"


def test_classify_cited_and_supported_but_with_issues_is_partially_cited():
    assert classify_citation_coverage(["chunk_001"], supported=True, issues=["revisar tono"]) == "partially_cited"


def test_summarize_computes_counts_and_rates():
    coverages = ["fully_cited", "fully_cited", "partially_cited", "uncited"]

    summary = summarize_citation_coverage(coverages)

    assert summary == {
        "fully_cited_count": 2,
        "partially_cited_count": 1,
        "uncited_count": 1,
        "traceability_rate": 0.5,
        "partial_rate": 0.25,
        "uncited_rate": 0.25,
    }


def test_summarize_empty_list_does_not_divide_by_zero():
    summary = summarize_citation_coverage([])

    assert summary["traceability_rate"] == 0.0
    assert summary["partial_rate"] == 0.0
    assert summary["uncited_rate"] == 0.0
