"""Carga prompts versionados como archivos de texto (CLAUDE.md, sección 7:
nunca hardcodeados en el código de los nodos).
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8").strip()
