"""Tests de extracción de texto PDF y chunking (rag/pdf_ingest.py)."""

import pytest

from rag.pdf_ingest import chunk_pdf_text, extract_pdf_text
from tests.fakes import make_empty_pdf_bytes, make_pdf_bytes


def test_extract_pdf_text_returns_page_text():
    pdf_bytes = make_pdf_bytes("Algoworks entrego 12 proyectos de integracion de datos en 2023.")

    text = extract_pdf_text(pdf_bytes)

    assert "Algoworks" in text
    assert "2023" in text


def test_extract_pdf_text_raises_on_empty_pdf():
    empty_pdf_bytes = make_empty_pdf_bytes()

    with pytest.raises(ValueError):
        extract_pdf_text(empty_pdf_bytes)


def test_extract_pdf_text_raises_value_error_on_non_pdf_bytes():
    with pytest.raises(ValueError):
        extract_pdf_text(b"this is not a pdf")


def test_chunk_pdf_text_generates_sequential_chunk_ids():
    long_text = "Algoworks entrego proyectos de datos. " * 60

    chunks = chunk_pdf_text(long_text, source="Propuesta_Demo.pdf", section_type="experiencia_previa")

    assert len(chunks) > 1
    assert chunks[0].chunk_id == "propuesta_demo_001"
    assert chunks[1].chunk_id == "propuesta_demo_002"
    assert all(chunk.section_type == "experiencia_previa" for chunk in chunks)
    assert all(chunk.source == "Propuesta_Demo.pdf" for chunk in chunks)
