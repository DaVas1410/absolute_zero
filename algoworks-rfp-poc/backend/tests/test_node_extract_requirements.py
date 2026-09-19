"""Tests del nodo extract_requirements: caso feliz (structured output) y
caso de fallback (split por líneas numeradas cuando el LLM falla)."""

from types import SimpleNamespace

from graph.nodes.extract_requirements import make_extract_requirements_node
from tests.fakes import ScriptedChatModel


def _base_state(rfp_text: str) -> dict:
    return {"rfp_id": "rfp_001", "rfp_text": rfp_text, "trace_log": []}


def test_extract_requirements_uses_structured_output_when_it_succeeds():
    extracted = SimpleNamespace(
        requirements=[
            SimpleNamespace(req_id="req_001", text="Debe tener experiencia previa.", section_target="experiencia_previa"),
            SimpleNamespace(req_id="req_002", text="Debe describir su arquitectura.", section_target="capacidades_tecnicas"),
        ]
    )
    llm = ScriptedChatModel(structured_responses=[extracted])
    node = make_extract_requirements_node(llm)

    result = node(_base_state("1. Debe tener experiencia previa.\n2. Debe describir su arquitectura."))

    assert [r.req_id for r in result["requirements"]] == ["req_001", "req_002"]
    assert result["requirements"][0].section_target == "experiencia_previa"
    assert result["pending_req_ids"] == ["req_001", "req_002"]
    assert result["retry_counts"] == {"req_001": 0, "req_002": 0}
    assert len(result["trace_log"]) == 1
    assert result["trace_log"][0].node == "extract_requirements"
    assert result["trace_log"][0].duration_ms >= 0.0
    assert result["trace_log"][0].tokens is not None


def test_extract_requirements_falls_back_to_numbered_line_split_on_llm_failure():
    class RaisingLLM:
        def with_structured_output(self, schema, include_raw: bool = False):
            raise RuntimeError("structured output no soportado / conectividad caída")

    node = make_extract_requirements_node(RaisingLLM())

    rfp_text = "1. Debe tener experiencia previa.\n2. Debe describir su arquitectura.\nTexto suelto sin numerar."
    result = node(_base_state(rfp_text))

    assert len(result["requirements"]) == 2
    assert result["requirements"][0].text == "Debe tener experiencia previa."
    assert result["requirements"][1].text == "Debe describir su arquitectura."
    assert "fallback" in result["trace_log"][0].reasoning.lower()
    assert result["trace_log"][0].tokens.total_tokens == 0
