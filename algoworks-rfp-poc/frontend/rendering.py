"""Funciones puras de transformación para mostrar datos del PipelineResult.
Sin dependencias de Streamlit: son testeables sin un harness de UI."""

import html
import re

_CITATION_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


def highlight_citations(
    draft_text: str,
    cited_sources: dict[str, str] | None = None,
    supported: bool | None = None,
) -> str:
    """Resalta marcadores [[chunk_id]] en draft_text.

    Sin cited_sources: negrita Markdown simple ("**[chunk_id]**"), para usar
    con st.markdown sin unsafe_allow_html.

    Con cited_sources (chunk_id -> nombre de archivo fuente): produce un
    <span> con clase CSS `rfp-cite` (más `rfp-cite--verified`/`--flagged`/
    `--neutral` según `supported`) y el archivo fuente como tooltip (title),
    para usar con st.markdown(..., unsafe_allow_html=True). Esto es lo que
    convierte cada cita en la propuesta en un rastro verificable hacia su
    documento de origen, no solo hacia un chunk_id opaco.
    """
    if cited_sources is None:
        return _CITATION_PATTERN.sub(lambda match: f"**[{match.group(1)}]**", draft_text)

    if supported is True:
        status = "verified"
    elif supported is False:
        status = "flagged"
    else:
        status = "neutral"

    def _replace(match: re.Match) -> str:
        chunk_id = match.group(1)
        source = cited_sources.get(chunk_id, "")
        tooltip = f"{chunk_id} · {source}" if source else chunk_id
        return (
            f'<span class="rfp-cite rfp-cite--{status}" title="{html.escape(tooltip)}">'
            f"{html.escape(chunk_id)}</span>"
        )

    return _CITATION_PATTERN.sub(_replace, draft_text)
