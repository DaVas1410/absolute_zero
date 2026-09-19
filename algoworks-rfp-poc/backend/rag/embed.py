"""Wrapper de embeddings con sentence-transformers, con la interfaz
Embeddings de LangChain para poder usarse directamente con Chroma.
"""

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(list(texts), convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode([text], convert_to_numpy=True)[0].tolist()
