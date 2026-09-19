"""Dobles de prueba compartidos por los tests del backend (RAG y nodos del
grafo), para no depender de red ni de modelos reales en la suite.
"""

from types import SimpleNamespace

from fpdf import FPDF
from langchain_core.documents import Document
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


class ScriptedChatModel:
    """LLM de prueba que devuelve respuestas predefinidas, en orden, tanto
    para llamadas de texto plano (.invoke) como para salida estructurada
    (.with_structured_output(...).invoke). No hace ninguna llamada real ni
    reporta usage_metadata/response_metadata (las llamadas trackeadas
    contra este doble siempre acumulan uso cero).
    """

    def __init__(self, plain_responses=None, structured_responses=None):
        self._plain_responses = list(plain_responses or [])
        self._structured_responses = list(structured_responses or [])

    def invoke(self, prompt: str):
        text = self._plain_responses.pop(0)
        return SimpleNamespace(content=text)

    def with_structured_output(self, schema, method: str = "function_calling", include_raw: bool = False):
        outer = self

        class _StructuredRunnable:
            def invoke(self, prompt: str):
                parsed = outer._structured_responses.pop(0)
                if include_raw:
                    return {
                        "raw": SimpleNamespace(content="", usage_metadata=None, response_metadata={}),
                        "parsed": parsed,
                        "parsing_error": None,
                    }
                return parsed

        return _StructuredRunnable()


class FakeVectorstore:
    """Doble de Chroma: expone solo similarity_search_with_relevance_scores,
    devolviendo resultados preprogramados por texto de query exacto.
    """

    def __init__(self, results_by_query: dict[str, list[tuple]]):
        self._results_by_query = results_by_query

    def similarity_search_with_relevance_scores(self, query: str, k: int = 4):
        candidates = self._results_by_query.get(query, [])
        documents_with_scores = [
            (
                Document(
                    page_content=candidate[1],
                    metadata={"chunk_id": candidate[0], "source": candidate[3] if len(candidate) > 3 else ""},
                ),
                candidate[2],
            )
            for candidate in candidates
        ]
        return documents_with_scores[:k]


def make_pdf_bytes(text: str) -> bytes:
    """Genera un PDF sintético en memoria para tests (fpdf2, sin red ni
    archivos binarios versionados)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text.splitlines():
        pdf.multi_cell(0, 10, line)
    return bytes(pdf.output())


def make_empty_pdf_bytes() -> bytes:
    """Genera un PDF sintético sin texto (una página en blanco), para tests
    del caso "no se pudo extraer texto legible del PDF"."""
    pdf = FPDF()
    pdf.add_page()
    return bytes(pdf.output())
