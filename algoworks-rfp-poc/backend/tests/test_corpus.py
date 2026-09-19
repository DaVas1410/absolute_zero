"""Tests del loader de la corpus dummy de conocimiento."""

import json

from api.schemas import Chunk
from rag.corpus import load_dummy_chunks, load_ingested_chunks, append_ingested_chunks
from rag.store import build_vectorstore
from tests.fakes import FakeEmbeddings


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


def test_append_ingested_chunks_dedupes_by_chunk_id_newest_wins(tmp_path):
    # Simula un PDF re-ingestado con el mismo source (y por lo tanto el mismo
    # chunk_id, derivado por slugify(source)): sin dedupe, el JSON en disco
    # acumula ids duplicados y Chroma.from_documents revienta con
    # DuplicateIDError en el proximo arranque del servidor (finding #1).
    path = tmp_path / "ingested_chunks.json"
    stale = _sample_ingested_chunk("demo_001")
    fresh = Chunk(
        chunk_id="demo_001",
        text="Texto actualizado tras re-ingestar el mismo PDF.",
        source="Propuesta_Demo.pdf",
        section_type="experiencia_previa",
    )

    append_ingested_chunks([stale], path)
    append_ingested_chunks([fresh], path)

    chunks = load_ingested_chunks(path)
    assert [chunk.chunk_id for chunk in chunks] == ["demo_001"]
    assert chunks[0].text == fresh.text
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert len(raw) == 1


def test_ingested_chunks_with_reingested_source_do_not_break_vectorstore_rebuild(tmp_path):
    # Test de la costura completa (finding #4): append_ingested_chunks +
    # build_vectorstore alimentado por el merge que hace
    # api/main.py._get_corpus_resources en cada arranque. Cada pieza estaba
    # probada por separado en su propia tarea; esto prueba que el restart
    # real (dummy_chunks + ingested_chunks -> build_vectorstore) no revienta
    # cuando un PDF fue re-ingestado (mismo chunk_id en dos batches).
    path = tmp_path / "ingested_chunks.json"
    append_ingested_chunks([_sample_ingested_chunk("demo_001")], path)
    append_ingested_chunks([_sample_ingested_chunk("demo_001")], path)

    all_chunks = load_dummy_chunks() + load_ingested_chunks(path)
    vocabulary = ["texto", "prueba", "ingerido"]

    # No debe lanzar Chroma DuplicateIDError.
    vectorstore = build_vectorstore(all_chunks, FakeEmbeddings(vocabulary), persist_directory=None)

    assert vectorstore is not None
