"""Instrumentación de llamadas LLM: acumula tokens/costo por nodo y
reemplaza .invoke()/.with_structured_output().invoke() por variantes que
registran uso, sin romper el flujo cuando el modelo no reporta metadata
(p. ej. los dobles de prueba)."""

import os

from pydantic import BaseModel

from api.schemas import TokenUsage

# USD por millón de tokens (input, output). Tabla chica y aproximada, solo
# para los modelos Groq configurados via env vars; cualquier otro
# model_name (Ollama, vacío, desconocido) cotiza en 0.0.
_DEFAULT_GROQ_MODEL_SMALL = "llama-3.1-8b-instant"
_DEFAULT_GROQ_MODEL_LARGE = "llama-3.3-70b-versatile"
_PRICE_PER_MILLION_TOKENS_USD: dict[str, tuple[float, float]] = {
    _DEFAULT_GROQ_MODEL_SMALL: (0.05, 0.08),
    _DEFAULT_GROQ_MODEL_LARGE: (0.59, 0.79),
}


class TokenAccumulator:
    """Un acumulador por ejecución de nodo; se le van sumando las llamadas
    LLM que haga ese nodo, y al final se lee su total para el TraceEvent."""

    def __init__(self) -> None:
        self._usages: list[TokenUsage] = []

    def add(self, usage: TokenUsage) -> None:
        self._usages.append(usage)

    def total(self) -> TokenUsage:
        return TokenUsage(
            input_tokens=sum(usage.input_tokens for usage in self._usages),
            output_tokens=sum(usage.output_tokens for usage in self._usages),
            total_tokens=sum(usage.total_tokens for usage in self._usages),
            estimated_cost_usd=sum(usage.estimated_cost_usd for usage in self._usages),
        )


def _extract_usage_and_model(response) -> tuple[TokenUsage, str]:
    usage_metadata = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}
    model_name = response_metadata.get("model_name") or response_metadata.get("model") or ""
    usage = TokenUsage(
        input_tokens=usage_metadata.get("input_tokens", 0),
        output_tokens=usage_metadata.get("output_tokens", 0),
        total_tokens=usage_metadata.get("total_tokens", 0),
    )
    return usage, model_name


def _tracked_usage(response) -> TokenUsage:
    usage, model_name = _extract_usage_and_model(response)
    return usage.model_copy(update={"estimated_cost_usd": estimate_cost_usd(model_name, usage)})


def invoke_tracked(llm, prompt: str, accumulator: TokenAccumulator) -> str:
    response = llm.invoke(prompt)
    accumulator.add(_tracked_usage(response))
    return response.content.strip()


def invoke_structured_tracked(llm, schema: type[BaseModel], prompt: str, accumulator: TokenAccumulator):
    response = llm.with_structured_output(schema, include_raw=True).invoke(prompt)
    accumulator.add(_tracked_usage(response["raw"]))
    if response["parsing_error"] is not None:
        raise response["parsing_error"]
    return response["parsed"]


def estimate_cost_usd(model_name: str, usage: TokenUsage) -> float:
    prices = _prices_by_configured_model_name()
    price = prices.get(model_name)
    if price is None:
        return 0.0
    input_price_per_million, output_price_per_million = price
    return (
        usage.input_tokens * input_price_per_million + usage.output_tokens * output_price_per_million
    ) / 1_000_000


def _prices_by_configured_model_name() -> dict[str, tuple[float, float]]:
    small_model = os.environ.get("GROQ_MODEL_SMALL", _DEFAULT_GROQ_MODEL_SMALL)
    large_model = os.environ.get("GROQ_MODEL_LARGE", _DEFAULT_GROQ_MODEL_LARGE)
    return {
        small_model: _PRICE_PER_MILLION_TOKENS_USD[_DEFAULT_GROQ_MODEL_SMALL],
        large_model: _PRICE_PER_MILLION_TOKENS_USD[_DEFAULT_GROQ_MODEL_LARGE],
    }
