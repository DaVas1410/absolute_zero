"""One-off script: adds low-risk real-world Algoworks context to the corpus.

Based on public research on the real company (algoworks.com) - see project
memory for the full research summary. Deliberately additive and narrow:

- Geographic footprint and delivery-methodology *naming* ("Everyday AI",
  "define, build and run") and publicly-stated industries served are added
  as plain facts - low risk, not case-evidence claims.
- Real certifications (Salesforce Summit Partner, CMMI Level 3, ISO 27001)
  are added ONLY inside a specialist-conversation entry that explicitly
  hedges them as "requiere validación", extending the exact pattern the
  corpus already uses in Conversaciones_Especialistas.pdf / Politicas_
  Simuladas.pdf to avoid asserting unverified certifications as fact.

Does NOT touch any existing chunk (chunk_004/006, cap_*, exp_*, kb_*,
perfil_algoworks_simulado_00{1,2}, conversaciones_especialistas_00{1,2}) -
those are already live-tested by the two original sample RFPs.
"""

import json
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base" / "dummy_chunks.json"

NEW_CHUNKS = [
    {
        "chunk_id": "perfil_algoworks_simulado_003",
        "text": (
            "Contexto adicional (basado en información pública real de la empresa homónima, "
            "solo para dar color de marca al ejercicio simulado - no reemplaza las restricciones "
            "del dataset): Algoworks tiene presencia en Estados Unidos, Reino Unido, Irlanda, "
            "Canadá, Ecuador, India y Rumania, con más de 20 años de trayectoria en servicios de "
            "ingeniería de software para clientes de gran tamaño."
        ),
        "source": "Perfil_Algoworks_Simulado.pdf",
        "section_type": "capacidades_tecnicas",
        "metadata": {"tipo": "contexto_publico_real", "confianza": "media"},
    },
    {
        "chunk_id": "perfil_algoworks_simulado_004",
        "text": (
            "Algoworks describe su enfoque de adopción de IA como 'Everyday AI': incorporar "
            "funcionalidad de IA pragmática dentro de flujos de trabajo ya existentes del cliente "
            "para lograr resultados rápidos, dentro de un modelo de entrega que la empresa llama "
            "'define, build and run' (definir, construir y operar)."
        ),
        "source": "Perfil_Algoworks_Simulado.pdf",
        "section_type": "capacidades_tecnicas",
        "metadata": {"tipo": "contexto_publico_real", "confianza": "media"},
    },
    {
        "chunk_id": "perfil_algoworks_simulado_005",
        "text": (
            "Públicamente, Algoworks declara experiencia sectorial en aeroespacial, automotriz, "
            "consumo/retail, educación, energía, servicios financieros, gobierno, salud, "
            "manufactura, medios/telecomunicaciones, tecnología, transporte/logística y viajes. "
            "El detalle de un caso concreto en un sector específico debe respaldarse igualmente "
            "con evidencia puntual del dataset disponible, no solo con esta declaración general."
        ),
        "source": "Perfil_Algoworks_Simulado.pdf",
        "section_type": "capacidades_tecnicas",
        "metadata": {"tipo": "contexto_publico_real", "confianza": "media"},
    },
    {
        "chunk_id": "conversaciones_especialistas_003",
        "text": (
            "Especialista comercial (certificaciones)\n"
            "Pregunta: ¿Podemos mencionar certificaciones como CMMI Nivel 3, ISO 27001, o el "
            "estatus de Salesforce Summit Partner en una propuesta?\n"
            "Respuesta: Son credenciales que la empresa real declara públicamente en su sitio "
            "corporativo, pero este dataset simulado no incluye el certificado ni la evidencia de "
            "auditoría correspondiente. Deben citarse solo si el equipo comercial confirma la "
            "vigencia y el alcance exacto de cada una antes de enviar la propuesta; de lo "
            "contrario, marcar como 'requiere validación', igual que con cualquier otra "
            "certificación (ISO, SOC, PCI-DSS)."
        ),
        "source": "Conversaciones_Especialistas.pdf",
        "section_type": "capacidades_tecnicas",
        "metadata": {"tipo": "contexto_publico_real", "confianza": "baja"},
    },
]


def main() -> None:
    existing = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    existing_ids = {chunk["chunk_id"] for chunk in existing}
    duplicates = [chunk["chunk_id"] for chunk in NEW_CHUNKS if chunk["chunk_id"] in existing_ids]
    if duplicates:
        raise SystemExit(f"chunk_id ya existe, abortando (correr una sola vez): {duplicates}")

    combined = existing + NEW_CHUNKS
    CORPUS_PATH.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Corpus: {len(existing)} -> {len(combined)} chunks ({len(NEW_CHUNKS)} nuevos).")


if __name__ == "__main__":
    main()
