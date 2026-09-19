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


def test_highlight_citations_with_sources_renders_pill_with_tooltip():
    result = highlight_citations(
        "Texto con cita [[chunk_001]].",
        cited_sources={"chunk_001": "Propuesta_ClienteX_2023.md"},
        supported=True,
    )

    assert 'class="rfp-cite rfp-cite--verified"' in result
    assert 'title="chunk_001 · Propuesta_ClienteX_2023.md"' in result
    assert ">chunk_001</span>" in result


def test_highlight_citations_with_sources_flags_unsupported_section():
    result = highlight_citations(
        "Cita [[chunk_002]].", cited_sources={"chunk_002": "doc.md"}, supported=False
    )

    assert "rfp-cite--flagged" in result


def test_highlight_citations_with_sources_defaults_to_neutral_status():
    result = highlight_citations("Cita [[chunk_003]].", cited_sources={})

    assert "rfp-cite--neutral" in result
    assert 'title="chunk_003"' in result


def test_highlight_citations_with_sources_escapes_html():
    result = highlight_citations(
        "Cita [[chunk_004]].", cited_sources={"chunk_004": '<script>"evil"</script>'}
    )

    assert "<script>" not in result
