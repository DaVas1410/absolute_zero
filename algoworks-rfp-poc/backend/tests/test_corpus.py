"""Tests del loader de la corpus dummy de conocimiento."""

from api.schemas import Chunk
from rag.corpus import load_dummy_chunks


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
