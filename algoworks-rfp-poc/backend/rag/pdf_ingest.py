"""Ingesta de PDFs: extracción de texto y chunking, compartido por la
ingesta del corpus de conocimiento y por el RFP de entrada (sub-project D,
ver docs/superpowers/specs/2026-09-19-pdf-ingestion-design.md).
"""

import re
from io import BytesIO

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from api.schemas import Chunk

CHUNK_SIZE = 700
CHUNK_OVERLAP = 120


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text:
        raise ValueError(
            "No se pudo extraer texto legible del PDF "
            "(¿es un PDF escaneado sin capa de texto?)."
        )
    return text


def _slugify(source: str) -> str:
    stem = re.sub(r"\.[^.]+$", "", source)
    slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    return slug or "documento"


def chunk_pdf_text(text: str, source: str, section_type: str) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    slug = _slugify(source)
    return [
        Chunk(
            chunk_id=f"{slug}_{i:03d}",
            text=piece,
            source=source,
            section_type=section_type,
        )
        for i, piece in enumerate(splitter.split_text(text), start=1)
    ]
