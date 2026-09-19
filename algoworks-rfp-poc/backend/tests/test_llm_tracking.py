"""Tests del módulo de tracking de llamadas LLM: acumulación de tokens,
extracción defensiva de usage_metadata/response_metadata, y estimación de
costo best-effort. No depende de red ni de modelos reales."""

from types import SimpleNamespace

import pytest

from api.schemas import TokenUsage
from graph.llm_tracking import (
    TokenAccumulator,
    estimate_cost_usd,
    invoke_structured_tracked,
    invoke_tracked,
)


def test_token_accumulator_sums_multiple_usages():
    accumulator = TokenAccumulator()

    accumulator.add(TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15, estimated_cost_usd=0.001))
    accumulator.add(TokenUsage(input_tokens=20, output_tokens=8, total_tokens=28, estimated_cost_usd=0.002))

    total = accumulator.total()
    assert total.input_tokens == 30
    assert total.output_tokens == 13
    assert total.total_tokens == 43
    assert total.estimated_cost_usd == pytest.approx(0.003)


def test_token_accumulator_total_is_zero_when_empty():
    total = TokenAccumulator().total()

    assert total == TokenUsage()


class _PlainResponse:
    def __init__(self, content: str):
        self.content = content


def test_invoke_tracked_returns_content_and_accumulates_zero_for_missing_usage_metadata():
    class _NoMetadataLLM:
        def invoke(self, prompt):
            return _PlainResponse(" respuesta sin metadata ")

    accumulator = TokenAccumulator()

    content = invoke_tracked(_NoMetadataLLM(), "prompt", accumulator)

    assert content == "respuesta sin metadata"
    assert accumulator.total() == TokenUsage()


def test_invoke_tracked_accumulates_real_usage_metadata(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL_SMALL", "test-small-model")

    class _WithMetadataLLM:
        def invoke(self, prompt):
            response = _PlainResponse("respuesta")
            response.usage_metadata = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
            response.response_metadata = {"model_name": "test-small-model"}
            return response

    accumulator = TokenAccumulator()

    invoke_tracked(_WithMetadataLLM(), "prompt", accumulator)

    total = accumulator.total()
    assert total.input_tokens == 100
    assert total.total_tokens == 150
    assert total.estimated_cost_usd > 0.0


class _StructuredLLM:
    def __init__(self, raw, parsed, parsing_error=None):
        self._raw = raw
        self._parsed = parsed
        self._parsing_error = parsing_error
        self.received_include_raw = None

    def with_structured_output(self, schema, include_raw: bool = False):
        self.received_include_raw = include_raw
        outer = self

        class _Runnable:
            def invoke(self, prompt):
                return {"raw": outer._raw, "parsed": outer._parsed, "parsing_error": outer._parsing_error}

        return _Runnable()


def test_invoke_structured_tracked_returns_parsed_and_accumulates_usage():
    raw = _PlainResponse("")
    raw.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    raw.response_metadata = {}
    parsed = SimpleNamespace(field="valor")
    llm = _StructuredLLM(raw=raw, parsed=parsed)
    accumulator = TokenAccumulator()

    result = invoke_structured_tracked(llm, SimpleNamespace, "prompt", accumulator)

    assert result is parsed
    assert llm.received_include_raw is True
    assert accumulator.total().total_tokens == 15


def test_invoke_structured_tracked_reraises_parsing_error():
    raw = _PlainResponse("")
    llm = _StructuredLLM(raw=raw, parsed=None, parsing_error=ValueError("no se pudo parsear"))
    accumulator = TokenAccumulator()

    with pytest.raises(ValueError, match="no se pudo parsear"):
        invoke_structured_tracked(llm, SimpleNamespace, "prompt", accumulator)


def test_estimate_cost_usd_returns_zero_for_unknown_model():
    assert estimate_cost_usd("modelo-desconocido", TokenUsage(input_tokens=1000, output_tokens=1000)) == 0.0


def test_estimate_cost_usd_returns_positive_for_configured_groq_model(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL_LARGE", "test-large-model")

    cost = estimate_cost_usd("test-large-model", TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000))

    assert cost > 0.0
