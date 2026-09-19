"""Tests de rendering.highlight_citations: convierte marcadores [[chunk_id]]
en texto resaltado (negrita Markdown) para mostrarse con st.markdown."""

from rendering import highlight_citations


def test_highlight_citations_bolds_single_marker():
    result = highlight_citations("Texto con cita [[chunk_001]].")

    assert result == "Texto con cita **[chunk_001]**."


def test_highlight_citations_bolds_multiple_markers():
    result = highlight_citations("Cita [[chunk_001]] y otra [[chunk_002]].")

    assert result == "Cita **[chunk_001]** y otra **[chunk_002]**."


def test_highlight_citations_passes_through_text_without_markers():
    result = highlight_citations("Texto sin ninguna cita.")

    assert result == "Texto sin ninguna cita."
