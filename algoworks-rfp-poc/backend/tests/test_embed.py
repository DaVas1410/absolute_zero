"""Test de integración liviano del wrapper de embeddings. Descarga el
modelo sentence-transformers la primera vez que corre (requiere red o
caché local de HuggingFace); las demás pruebas de RAG usan FakeEmbeddings
para no depender de esto.
"""

from rag.embed import SentenceTransformerEmbeddings


def test_embed_documents_and_query_return_same_dimensionality():
    embeddings = SentenceTransformerEmbeddings()

    doc_vectors = embeddings.embed_documents(["hola mundo", "otro texto de prueba"])
    query_vector = embeddings.embed_query("hola mundo")

    assert len(doc_vectors) == 2
    assert len(doc_vectors[0]) > 0
    assert len(doc_vectors[0]) == len(doc_vectors[1]) == len(query_vector)
