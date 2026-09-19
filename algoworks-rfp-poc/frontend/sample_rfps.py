"""Carga las RFP de ejemplo desde data/sample_rfps/ para el selector del
frontend (spec: docs/superpowers/specs/2026-09-18-frontend-design.md, §7)."""

from pathlib import Path

SAMPLE_RFPS_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_rfps"

_DISPLAY_NAMES = {
    "rfp_experiencia_arquitectura.txt": "Experiencia previa + arquitectura (caso feliz)",
    "rfp_sla_no_respaldado.txt": "SLA de latencia sin respaldo (caso adversarial)",
}


def list_samples() -> dict[str, str]:
    samples: dict[str, str] = {}
    for path in sorted(SAMPLE_RFPS_DIR.glob("*.txt")):
        display_name = _DISPLAY_NAMES.get(path.name, path.stem)
        samples[display_name] = path.read_text(encoding="utf-8")
    return samples
