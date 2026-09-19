"""Carga la corpus dummy de conocimiento (CLAUDE.md, sección 8: backend
arranca con sus propios chunks dummy, sin bloquear por datos reales).
"""

import json
from pathlib import Path

from api.schemas import Chunk

DEFAULT_CORPUS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "knowledge_base" / "dummy_chunks.json"
)


def load_dummy_chunks(path: Path = DEFAULT_CORPUS_PATH) -> list[Chunk]:
    raw_chunks = json.loads(path.read_text(encoding="utf-8"))
    return [Chunk.model_validate(item) for item in raw_chunks]


DEFAULT_INGESTED_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "knowledge_base" / "ingested_chunks.json"
)


def load_ingested_chunks(path: Path = DEFAULT_INGESTED_PATH) -> list[Chunk]:
    if not path.exists():
        return []
    raw_chunks = json.loads(path.read_text(encoding="utf-8"))
    return [Chunk.model_validate(item) for item in raw_chunks]


def append_ingested_chunks(chunks: list[Chunk], path: Path = DEFAULT_INGESTED_PATH) -> None:
    # Dedupe por chunk_id (gana el mas nuevo) para que el JSON en disco no
    # acumule ids duplicados al re-ingestar el mismo PDF: Chroma.from_documents
    # rechaza ids duplicados en un mismo batch (DuplicateIDError), lo que
    # rompe el arranque del servidor en el proximo restart si no se dedupea
    # aqui. El path de mutacion en vivo (add_chunks sobre un vectorstore ya
    # corriendo) ya hace upsert correctamente via Chroma; esto lo iguala en disco.
    by_id = {chunk.chunk_id: chunk for chunk in load_ingested_chunks(path)}
    by_id.update({chunk.chunk_id: chunk for chunk in chunks})
    combined = list(by_id.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([chunk.model_dump() for chunk in combined], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
