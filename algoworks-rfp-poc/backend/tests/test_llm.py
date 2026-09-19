"""Tests del wrapper de fallback Groq -> Ollama. No hace llamadas reales:
usa dobles locales que pueden simular una falla del proveedor principal."""

from types import SimpleNamespace

import pytest

from graph.llm import FallbackChatModel, get_chat_llm


class _FailingLLM:
    def invoke(self, prompt):
        raise RuntimeError("sin conectividad")

    def with_structured_output(self, schema, method: str = "function_calling", include_raw: bool = False):
        raise RuntimeError("sin conectividad")


class _OkLLM:
    def __init__(self, label: str):
        self._label = label
        self.calls = 0
        self.received_include_raw = None
        self.received_method = None

    def invoke(self, prompt):
        self.calls += 1
        return SimpleNamespace(content=self._label)

    def with_structured_output(self, schema, method: str = "function_calling", include_raw: bool = False):
        self.received_include_raw = include_raw
        self.received_method = method
        parent = self

        class _Structured:
            def invoke(self, prompt):
                parent.calls += 1
                return SimpleNamespace(label=parent._label)

        return _Structured()


def test_invoke_uses_primary_when_it_succeeds():
    primary = _OkLLM("primary")
    fallback = _OkLLM("fallback")
    model = FallbackChatModel(primary, fallback)

    response = model.invoke("prompt")

    assert response.content == "primary"
    assert primary.calls == 1
    assert fallback.calls == 0


def test_invoke_falls_back_when_primary_raises():
    model = FallbackChatModel(_FailingLLM(), _OkLLM("fallback"))

    response = model.invoke("prompt")

    assert response.content == "fallback"


def test_invoke_raises_combined_error_when_primary_and_fallback_both_fail():
    model = FallbackChatModel(_FailingLLM(), _FailingLLM())

    with pytest.raises(RuntimeError) as exc_info:
        model.invoke("prompt")

    message = str(exc_info.value)
    assert "primario (Groq)" in message
    assert "fallback (Ollama)" in message
    assert "sin conectividad" in message
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_with_structured_output_falls_back_when_primary_raises():
    model = FallbackChatModel(_FailingLLM(), _OkLLM("fallback"))

    response = model.with_structured_output(object).invoke("prompt")

    assert response.label == "fallback"


def test_with_structured_output_forwards_include_raw_to_both_models():
    primary = _OkLLM("primary")
    fallback = _OkLLM("fallback")
    model = FallbackChatModel(primary, fallback)

    model.with_structured_output(object, include_raw=True)

    assert primary.received_include_raw is True
    assert fallback.received_include_raw is True


def test_with_structured_output_forwards_method_to_both_models():
    primary = _OkLLM("primary")
    fallback = _OkLLM("fallback")
    model = FallbackChatModel(primary, fallback)

    model.with_structured_output(object, method="json_schema", include_raw=True)

    assert primary.received_method == "json_schema"
    assert fallback.received_method == "json_schema"


def test_get_chat_llm_builds_groq_primary_and_ollama_fallback(monkeypatch):
    captured = {}

    class _FakeChatGroq:
        def __init__(self, model, api_key=None, max_tokens=None):
            captured["groq_model"] = model
            captured["groq_max_tokens"] = max_tokens

    class _FakeChatOllama:
        def __init__(self, model, base_url=None, num_predict=None):
            captured["ollama_model"] = model

    monkeypatch.setattr("graph.llm.ChatGroq", _FakeChatGroq)
    monkeypatch.setattr("graph.llm.ChatOllama", _FakeChatOllama)
    monkeypatch.setenv("GROQ_MODEL_SMALL", "test-small-model")

    llm = get_chat_llm("small")

    assert isinstance(llm, FallbackChatModel)
    assert captured["groq_model"] == "test-small-model"
    assert "ollama_model" in captured
    # "small" has no configured max_tokens override - left at the provider default.
    assert captured["groq_max_tokens"] is None


def test_get_chat_llm_large_sets_a_higher_max_tokens_for_the_multi_section_compose_call(monkeypatch):
    captured = {}

    class _FakeChatGroq:
        def __init__(self, model, api_key=None, max_tokens=None):
            captured["groq_max_tokens"] = max_tokens

    class _FakeChatOllama:
        def __init__(self, model, base_url=None, num_predict=None):
            pass

    monkeypatch.setattr("graph.llm.ChatGroq", _FakeChatGroq)
    monkeypatch.setattr("graph.llm.ChatOllama", _FakeChatOllama)

    get_chat_llm("large")

    assert captured["groq_max_tokens"] == 8000
