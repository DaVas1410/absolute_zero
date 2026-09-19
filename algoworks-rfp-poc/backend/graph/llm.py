"""Provee el LLM de chat: Groq como proveedor principal, Ollama local como
fallback si falla la conectividad (CLAUDE.md, secciones 2 y 6)."""

import logging
import os
from typing import Literal

from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

_DEFAULT_GROQ_MODEL_SMALL = "openai/gpt-oss-20b"
_DEFAULT_GROQ_MODEL_LARGE = "openai/gpt-oss-120b"

logger = logging.getLogger(__name__)


def _fallback_or_raise(primary_error: Exception, fallback_call):
    """Loguea la falla del primario (nunca la trague en silencio) e intenta
    el fallback. Si el fallback tambien falla, levanta un error que expone
    AMBAS causas — sin esto, un fallo de Groq quedaba enmascarado por un
    ConnectError de Ollama que no dice nada sobre la causa real."""
    logger.warning("LLM primario (Groq) fallo, intentando fallback (Ollama): %s", primary_error, exc_info=True)
    try:
        return fallback_call()
    except Exception as fallback_error:
        raise RuntimeError(
            f"Fallaron tanto el LLM primario (Groq) como el fallback (Ollama). "
            f"Error primario: {primary_error!r}. Error de fallback: {fallback_error!r}."
        ) from primary_error


class FallbackChatModel:
    """Intenta el modelo principal (Groq); si falla, reintenta con el de
    fallback (Ollama local)."""

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    def invoke(self, prompt):
        try:
            return self._primary.invoke(prompt)
        except Exception as primary_error:
            return _fallback_or_raise(primary_error, lambda: self._fallback.invoke(prompt))

    def with_structured_output(self, schema, method: str = "function_calling", include_raw: bool = False):
        try:
            primary_structured = self._primary.with_structured_output(schema, method=method, include_raw=include_raw)
        except Exception as primary_error:
            logger.warning(
                "No se pudo preparar structured output en el LLM primario (Groq), se usara solo el fallback: %s",
                primary_error,
                exc_info=True,
            )
            primary_structured = None

        fallback_structured = self._fallback.with_structured_output(schema, method=method, include_raw=include_raw)

        return _FallbackStructuredRunnable(primary_structured, fallback_structured)


class _FallbackStructuredRunnable:
    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    def invoke(self, prompt):
        if self._primary is None:
            return self._fallback.invoke(prompt)
        try:
            return self._primary.invoke(prompt)
        except Exception as primary_error:
            return _fallback_or_raise(primary_error, lambda: self._fallback.invoke(prompt))


_MAX_TOKENS_BY_SIZE: dict[str, int] = {
    # "large" backs compose_proposal, which now generates a full ~12-section
    # business document in one structured-output call - left at the
    # provider's own default (unset), a long document was silently
    # truncated to the first few sections (the JSON schema decoder still
    # closes valid JSON at the token budget, so no error was ever raised).
    "large": 8000,
}


def get_chat_llm(size: Literal["small", "large"]) -> FallbackChatModel:
    groq_model = (
        os.environ.get("GROQ_MODEL_SMALL", _DEFAULT_GROQ_MODEL_SMALL)
        if size == "small"
        else os.environ.get("GROQ_MODEL_LARGE", _DEFAULT_GROQ_MODEL_LARGE)
    )
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1")
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    max_tokens = _MAX_TOKENS_BY_SIZE.get(size)

    primary = ChatGroq(model=groq_model, api_key=os.environ.get("GROQ_API_KEY"), max_tokens=max_tokens)
    fallback = ChatOllama(model=ollama_model, base_url=ollama_base_url, num_predict=max_tokens)
    return FallbackChatModel(primary, fallback)
