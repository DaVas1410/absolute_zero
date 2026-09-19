"""Fixtures compartidas por toda la suite de tests del backend."""

import pytest
from chromadb.api.shared_system_client import SharedSystemClient


@pytest.fixture(autouse=True)
def _reset_chromadb_system_cache():
    """Limpia el cache de sistemas de Chroma entre tests.

    Chroma comparte un unico "system" en memoria (identificador "ephemeral")
    para todos los clientes no persistentes de un mismo proceso
    (ver chromadb.api.shared_system_client.SharedSystemClient). Sin este
    reset, dos tests que construyan un vectorstore con FakeEmbeddings de
    distinto tamano de vocabulario (distinta dimension de embedding) chocan
    entre si con "Collection expecting embedding with dimension of X, got Y",
    dependiendo del orden de ejecucion de los archivos de test.
    """
    yield
    SharedSystemClient.clear_system_cache()
