"""Tests del loader de la corpus dummy de conocimiento."""

import json

from api.schemas import Chunk
from rag.corpus import load_dummy_chunks, load_ingested_chunks, append_ingested_chunks


def test_load_dummy_chunks_returns_valid_unique_chunks():
    chunks = load_dummy_chunks()

    assert len(chunks) >= 3
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_load_dummy_chunks_covers_multiple_section_types():
    chunks = load_dummy_chunks()

    section_types = {chunk.section_type for chunk in chunks}
    assert len(section_types) >= 2


def _sample_ingested_chunk(chunk_id: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        text="Texto de prueba ingerido desde PDF.",
        source="Propuesta_Demo.pdf",
        section_type="experiencia_previa",
    )


def test_load_ingested_chunks_returns_empty_list_when_file_missing(tmp_path):
    missing_path = tmp_path / "ingested_chunks.json"

    assert load_ingested_chunks(missing_path) == []


def test_append_ingested_chunks_persists_and_accumulates(tmp_path):
    path = tmp_path / "ingested_chunks.json"

    append_ingested_chunks([_sample_ingested_chunk("demo_001")], path)
    append_ingested_chunks([_sample_ingested_chunk("demo_002")], path)

    chunks = load_ingested_chunks(path)
    assert [chunk.chunk_id for chunk in chunks] == ["demo_001", "demo_002"]
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert len(raw) == 2
