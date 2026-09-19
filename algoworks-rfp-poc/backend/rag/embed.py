"""Wrapper de embeddings con sentence-transformers, con la interfaz
Embeddings de LangChain para poder usarse directamente con Chroma.
"""

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Antes usaba all-MiniLM-L6-v2 (entrenado principalmente en inglés); el corpus
# y los RFPs de este proyecto son en español, y el modelo multilingüe mejora
# de forma medible la recuperación (validado empíricamente: Aurora Bank pasa
# de no aparecer en el top-5 a rank 2 para "experiencia en servicios
# financieros", sin dejar que registros con negación como "no hay caso
# financiero" dominen el ranking).


class SentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(
            list(texts), convert_to_numpy=True, normalize_embeddings=True
        ).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode(
            [text], convert_to_numpy=True, normalize_embeddings=True
        )[0].tolist()
