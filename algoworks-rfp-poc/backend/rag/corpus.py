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
