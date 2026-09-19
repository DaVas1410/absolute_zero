"""Tests del loader de prompts versionados como archivos de texto."""

import pytest

from graph.prompts import load_prompt


def test_load_prompt_returns_file_contents():
    prompt = load_prompt("extract_requirements.txt")

    assert "{rfp_text}" in prompt


def test_load_prompt_raises_for_missing_file():
    with pytest.raises(FileNotFoundError):
        load_prompt("no_existe.txt")
