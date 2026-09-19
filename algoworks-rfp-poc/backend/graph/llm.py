"""Provee el LLM de chat: Groq como proveedor principal, Ollama local como
fallback si falla la conectividad (CLAUDE.md, secciones 2 y 6)."""

import os
from typing import Literal

from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

_DEFAULT_GROQ_MODEL_SMALL = "openai/gpt-oss-20b"
_DEFAULT_GROQ_MODEL_LARGE = "openai/gpt-oss-120b"


class FallbackChatModel:
    """Intenta el modelo principal (Groq); si falla, reintenta con el de
    fallback (Ollama local)."""

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    def invoke(self, prompt):
        try:
            return self._primary.invoke(prompt)
        except Exception:
            return self._fallback.invoke(prompt)

    def with_structured_output(self, schema, method: str = "function_calling", include_raw: bool = False):
        try:
            primary_structured = self._primary.with_structured_output(schema, method=method, include_raw=include_raw)
        except Exception:
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
        except Exception:
            return self._fallback.invoke(prompt)


def get_chat_llm(size: Literal["small", "large"]) -> FallbackChatModel:
    groq_model = (
        os.environ.get("GROQ_MODEL_SMALL", _DEFAULT_GROQ_MODEL_SMALL)
        if size == "small"
        else os.environ.get("GROQ_MODEL_LARGE", _DEFAULT_GROQ_MODEL_LARGE)
    )
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1")
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    primary = ChatGroq(model=groq_model, api_key=os.environ.get("GROQ_API_KEY"))
    fallback = ChatOllama(model=ollama_model, base_url=ollama_base_url)
    return FallbackChatModel(primary, fallback)
