"""Dobles de prueba compartidos por los tests del backend (RAG y nodos del
grafo), para no depender de red ni de modelos reales en la suite.
"""

from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    """Embeddings deterministas basados en presencia de palabras clave:
    dos textos son 'similares' si comparten más palabras del vocabulario.
    """

    def __init__(self, vocabulary: list[str]):
        self._vocabulary = vocabulary

    def _vectorize(self, text: str) -> list[float]:
        lowered = text.lower()
        return [float(word in lowered) for word in self._vocabulary]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectorize(text)
