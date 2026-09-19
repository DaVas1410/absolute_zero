"""Tests del vectorstore local (Chroma) sobre un corpus pequeño y
embeddings deterministas (FakeEmbeddings), sin red ni modelos reales.
"""

from api.schemas import Chunk
from rag.store import build_vectorstore, similarity_search, add_chunks
from tests.fakes import FakeEmbeddings

VOCABULARY = ["kafka", "retail", "manufactura", "logistica"]


def _sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id="chunk_kafka",
            text="Arquitectura basada en Kafka para streaming de datos.",
            source="doc_a.md",
            section_type="capacidades_tecnicas",
        ),
        Chunk(
            chunk_id="chunk_retail",
            text="Proyecto de sincronización de inventario para retail.",
            source="doc_b.md",
            section_type="experiencia_previa",
        ),
    ]


def test_similarity_search_returns_most_relevant_chunk_first():
    vectorstore = build_vectorstore(_sample_chunks(), FakeEmbeddings(VOCABULARY))

    results = similarity_search(vectorstore, "Necesitamos experiencia en retail", k=2)

    assert results[0][0] == "chunk_retail"
    assert len(results) == 2
    assert all(isinstance(score, float) for _, _, score, _ in results)
    assert results[0][3] == "doc_b.md"


def test_similarity_search_respects_k():
    vectorstore = build_vectorstore(_sample_chunks(), FakeEmbeddings(VOCABULARY))

    results = similarity_search(vectorstore, "kafka streaming", k=1)

    assert len(results) == 1
    assert results[0][0] == "chunk_kafka"


def test_similarity_search_clamps_negative_relevance_scores():
    # Una query cuyas palabras del vocabulario ("logistica", "manufactura")
    # no aparecen en ningun chunk produce, con este embeddings de prueba,
    # un relevance_score negativo real de Chroma (repro: ~-1.12).
    # similarity_search debe recortarlo a 0.0 para no exponer una
    # "confianza" de retrieval negativa.
    vectorstore = build_vectorstore(_sample_chunks(), FakeEmbeddings(VOCABULARY))

    results = similarity_search(vectorstore, "logistica manufactura", k=2)

    assert all(0.0 <= score <= 1.0 for _, _, score, _ in results)


def test_add_chunks_makes_new_chunk_retrievable():
    vectorstore = build_vectorstore(_sample_chunks(), FakeEmbeddings(VOCABULARY))

    add_chunks(
        vectorstore,
        [
            Chunk(
                chunk_id="chunk_manufactura",
                text="Nuevo proyecto de manufactura con Algoworks.",
                source="doc_c.md",
                section_type="experiencia_previa",
            )
        ],
    )

    results = similarity_search(vectorstore, "manufactura", k=1)

    assert results[0][0] == "chunk_manufactura"
