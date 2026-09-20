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
    """Intenta el/los modelo(s) principal(es) (Groq - una o mas API keys,
    probadas en orden para repartir la cuota diaria entre cuentas) y solo si
    TODAS fallan, reintenta con el de fallback (Ollama local). `primary`
    acepta un solo modelo (compatibilidad con el uso existente) o una lista
    de modelos Groq, uno por API key configurada."""

    def __init__(self, primary, fallback):
        self._primaries = primary if isinstance(primary, list) else [primary]
        self._fallback = fallback

    def invoke(self, prompt):
        last_error: Exception | None = None
        for candidate in self._primaries:
            try:
                return candidate.invoke(prompt)
            except Exception as error:
                logger.warning("Un LLM primario (Groq) fallo, probando la siguiente key: %s", error, exc_info=True)
                last_error = error
        return _fallback_or_raise(last_error, lambda: self._fallback.invoke(prompt))

    def with_structured_output(self, schema, method: str = "function_calling", include_raw: bool = False):
        primaries_structured = []
        prep_errors: list[Exception] = []
        for candidate in self._primaries:
            try:
                primaries_structured.append(
                    candidate.with_structured_output(schema, method=method, include_raw=include_raw)
                )
            except Exception as primary_error:
                logger.warning(
                    "No se pudo preparar structured output en una key Groq, se prueba la siguiente: %s",
                    primary_error,
                    exc_info=True,
                )
                prep_errors.append(primary_error)

        fallback_structured = self._fallback.with_structured_output(schema, method=method, include_raw=include_raw)

        return _FallbackStructuredRunnable(primaries_structured, fallback_structured, prep_errors)


class _FallbackStructuredRunnable:
    def __init__(self, primaries: list, fallback, prep_errors: list[Exception] | None = None):
        self._primaries = primaries
        self._fallback = fallback
        self._prep_errors = prep_errors or []

    def invoke(self, prompt):
        last_error: Exception | None = self._prep_errors[-1] if self._prep_errors else None
        for candidate in self._primaries:
            try:
                return candidate.invoke(prompt)
            except Exception as error:
                logger.warning("Un LLM primario (Groq) fallo, probando la siguiente key: %s", error, exc_info=True)
                last_error = error
        if last_error is None:
            return self._fallback.invoke(prompt)
        return _fallback_or_raise(last_error, lambda: self._fallback.invoke(prompt))


_MAX_TOKENS_BY_SIZE: dict[str, int] = {
    # "large" backs compose_proposal, which now generates a full ~12-section
    # business document in one structured-output call - left at the
    # provider's own default (unset), a long document was silently
    # truncated to the first few sections (the JSON schema decoder still
    # closes valid JSON at the token budget, so no error was ever raised).
    "large": 8000,
    # "small" backs extract_requirements' structured output. Left unset, an
    # RFP with many requirements (e.g. a 10-requirement enterprise RFP)
    # produces a JSON list long enough to hit Groq's default completion cap
    # mid-generation - Groq then raises json_validate_failed, and every
    # single call for the rest of the run falls back to slow local Ollama
    # instead of just this one. 4096 comfortably covers a long requirements
    # list without meaningfully raising cost for the short justifications
    # this same "small" model also generates in retrieve_chunks.
    "small": 4096,
}


def _load_groq_api_keys() -> list[str]:
    """GROQ_API_KEY, mas GROQ_API_KEY_2, GROQ_API_KEY_3, ... mientras existan
    (cuentas Groq separadas, cada una con su propia cuota diaria de tokens).
    Repartir llamadas entre varias evita quedar atado a la cuota gratuita de
    una sola cuenta y caer a Ollama local apenas esta se agota."""
    keys = []
    primary_key = os.environ.get("GROQ_API_KEY")
    if primary_key:
        keys.append(primary_key)
    index = 2
    while True:
        key = os.environ.get(f"GROQ_API_KEY_{index}")
        if not key:
            break
        keys.append(key)
        index += 1
    return keys


def get_chat_llm(size: Literal["small", "large"]) -> FallbackChatModel:
    groq_model = (
        os.environ.get("GROQ_MODEL_SMALL", _DEFAULT_GROQ_MODEL_SMALL)
        if size == "small"
        else os.environ.get("GROQ_MODEL_LARGE", _DEFAULT_GROQ_MODEL_LARGE)
    )
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1")
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    max_tokens = _MAX_TOKENS_BY_SIZE.get(size)

    primaries = [
        ChatGroq(model=groq_model, api_key=api_key, max_tokens=max_tokens) for api_key in _load_groq_api_keys()
    ]
    fallback = ChatOllama(model=ollama_model, base_url=ollama_base_url, num_predict=max_tokens)
    return FallbackChatModel(primaries, fallback)
