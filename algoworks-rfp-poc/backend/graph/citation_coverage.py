"""Clasificación código-only (sin LLM) de cobertura de citas. Se reusa entre
el pipeline principal (compute_traceability_metrics, por requisito) y
compose_proposal (finalize_compose, por sección) para no duplicar el
criterio de qué cuenta como "totalmente citado" vs "sin citar"."""

from typing import Literal

CitationCoverage = Literal["fully_cited", "partially_cited", "uncited"]


def classify_citation_coverage(cited_chunks: list[str], supported: bool, issues: list[str]) -> CitationCoverage:
    """Sin citas -> uncited. Con citas y sin problemas de verificación ->
    fully_cited. Con citas pero el verificador encontró algo -> partially_cited."""
    if not cited_chunks:
        return "uncited"
    if supported and not issues:
        return "fully_cited"
    return "partially_cited"


def summarize_citation_coverage(coverages: list[CitationCoverage]) -> dict[str, int | float]:
    total = len(coverages)
    fully_cited = sum(1 for coverage in coverages if coverage == "fully_cited")
    partially_cited = sum(1 for coverage in coverages if coverage == "partially_cited")
    uncited = sum(1 for coverage in coverages if coverage == "uncited")
    return {
        "fully_cited_count": fully_cited,
        "partially_cited_count": partially_cited,
        "uncited_count": uncited,
        "traceability_rate": fully_cited / total if total else 0.0,
        "partial_rate": partially_cited / total if total else 0.0,
        "uncited_rate": uncited / total if total else 0.0,
    }
