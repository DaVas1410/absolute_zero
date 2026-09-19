"""Funciones puras de transformación para mostrar datos del PipelineResult.
Sin dependencias de Streamlit: son testeables sin un harness de UI."""

import re

_CITATION_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


def highlight_citations(draft_text: str) -> str:
    return _CITATION_PATTERN.sub(lambda match: f"**[{match.group(1)}]**", draft_text)
