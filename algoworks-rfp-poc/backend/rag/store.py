"""Vectorstore local (Chroma) para el corpus de conocimiento ficticio."""

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from api.schemas import Chunk

COLLECTION_NAME = "algoworks_rfp_corpus"


def build_vectorstore(
    chunks: list[Chunk],
    embeddings: Embeddings,
    persist_directory: str | None = None,
) -> Chroma:
    documents = [
        Document(
            page_content=chunk.text,
            metadata={
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "section_type": chunk.section_type,
            },
        )
        for chunk in chunks
    ]
    ids = [chunk.chunk_id for chunk in chunks]
    return Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        ids=ids,
        collection_name=COLLECTION_NAME,
        persist_directory=persist_directory,
    )


def add_chunks(vectorstore: Chroma, chunks: list[Chunk]) -> None:
    documents = [
        Document(
            page_content=chunk.text,
            metadata={
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "section_type": chunk.section_type,
            },
        )
        for chunk in chunks
    ]
    ids = [chunk.chunk_id for chunk in chunks]
    vectorstore.add_documents(documents=documents, ids=ids)


def similarity_search(vectorstore: Chroma, query: str, k: int) -> list[tuple[str, str, float]]:
    results = vectorstore.similarity_search_with_relevance_scores(query, k=k)
    return [
        (document.metadata["chunk_id"], document.page_content, max(0.0, min(1.0, score)))
        for document, score in results
    ]
