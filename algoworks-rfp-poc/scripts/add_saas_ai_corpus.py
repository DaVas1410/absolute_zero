"""One-off script: appends synthetic SaaS/AI/ML-startup chunks to the corpus.

Not part of the app - run once (`python scripts/add_saas_ai_corpus.py`) to
extend data/knowledge_base/dummy_chunks.json, then restart the backend so
build_vectorstore() re-indexes with the new chunks. All content is fictitious
per CLAUDE.md sec. 1/8 (no real client data).
"""

import json
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base" / "dummy_chunks.json"

NEW_CHUNKS = [
    # --- Propuesta_NovaMetrics_2024.md (cliente SaaS B2B: analitica de producto) ---
    {
        "chunk_id": "propuesta_novametrics_2024_001",
        "text": (
            "Para NovaMetrics (SaaS B2B de analítica de producto), Algoworks migró el data warehouse "
            "multi-tenant de PostgreSQL a Snowflake, implementando aislamiento de datos por tenant a "
            "nivel de fila (row-level security) y una capa de transformación en dbt. El tiempo de "
            "reporte de cierre de mes se redujo de 3 días a 45 minutos, procesando 40 millones de "
            "eventos diarios."
        ),
        "source": "Propuesta_NovaMetrics_2024.md",
        "section_type": "experiencia_previa",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    {
        "chunk_id": "propuesta_novametrics_2024_002",
        "text": (
            "En el mismo proyecto para NovaMetrics, se construyó un pipeline de facturación por uso "
            "(usage-based billing) integrando los eventos de metering de Stripe con el stream de "
            "eventos interno de la aplicación, reduciendo las discrepancias de facturación del 4.2% "
            "al 0.3% de las cuentas mensuales."
        ),
        "source": "Propuesta_NovaMetrics_2024.md",
        "section_type": "experiencia_previa",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    {
        "chunk_id": "propuesta_novametrics_2024_003",
        "text": (
            "Algoworks integró Segment como capa de recolección de eventos de producto y Amplitude "
            "como herramienta de analítica para el equipo de producto de NovaMetrics, reduciendo el "
            "tiempo para obtener un insight de comportamiento de usuario de 2 semanas a el mismo día."
        ),
        "source": "Propuesta_NovaMetrics_2024.md",
        "section_type": "experiencia_previa",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    {
        "chunk_id": "propuesta_novametrics_2024_004",
        "text": (
            "Se implementó CI/CD para los modelos de dbt de NovaMetrics con pruebas automatizadas de "
            "calidad de datos (Great Expectations) en cada pull request, detectando el 98% de los "
            "cambios de esquema que hubieran roto dashboards downstream, medido sobre 6 meses de "
            "operación."
        ),
        "source": "Propuesta_NovaMetrics_2024.md",
        "section_type": "experiencia_previa",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    # --- Propuesta_VisionLabs_2024.md (cliente AI/ML startup: vision por computadora) ---
    {
        "chunk_id": "propuesta_visionlabs_2024_001",
        "text": (
            "Para VisionLabs (startup de IA de visión por computadora), Algoworks diseñó un pipeline "
            "de MLOps con MLflow como registro de modelos y Airflow para orquestar el reentrenamiento "
            "periódico, reduciendo el ciclo de despliegue de un modelo nuevo de 3 semanas a 2 días."
        ),
        "source": "Propuesta_VisionLabs_2024.md",
        "section_type": "experiencia_previa",
        "metadata": {"anio": 2024, "sector": "ai_ml"},
    },
    {
        "chunk_id": "propuesta_visionlabs_2024_002",
        "text": (
            "En VisionLabs se implementó un feature store con Feast, respaldado por Redis para "
            "acceso online y S3 para el histórico offline, reduciendo en un 90% los incidentes de "
            "'training-serving skew' (features calculadas distinto en entrenamiento y en producción) "
            "durante los 4 meses posteriores al despliegue."
        ),
        "source": "Propuesta_VisionLabs_2024.md",
        "section_type": "experiencia_previa",
        "metadata": {"anio": 2024, "sector": "ai_ml"},
    },
    {
        "chunk_id": "propuesta_visionlabs_2024_003",
        "text": (
            "Algoworks construyó para VisionLabs un pipeline de RAG (retrieval-augmented generation) "
            "usando la base de datos vectorial Qdrant y embeddings de OpenAI para un copiloto de "
            "atención al cliente, alcanzando 87% de precisión en primera respuesta sobre un set de "
            "evaluación de 12,000 consultas reales."
        ),
        "source": "Propuesta_VisionLabs_2024.md",
        "section_type": "experiencia_previa",
        "metadata": {"anio": 2024, "sector": "ai_ml"},
    },
    {
        "chunk_id": "propuesta_visionlabs_2024_004",
        "text": (
            "Para el entrenamiento de modelos de VisionLabs se implementó infraestructura GPU en AWS "
            "(instancias P4d) con orquestación de trabajos vía Kubernetes, reduciendo el costo de "
            "entrenamiento en un 35% mediante el uso de instancias spot con checkpointing automático."
        ),
        "source": "Propuesta_VisionLabs_2024.md",
        "section_type": "experiencia_previa",
        "metadata": {"anio": 2024, "sector": "ai_ml"},
    },
    # --- Capacidades_Tecnicas_SaaS_IA.md (capacidades generales, no atadas a un cliente) ---
    {
        "chunk_id": "capacidades_tecnicas_saas_ia_001",
        "text": (
            "Algoworks trabaja con el stack moderno de datos ELT: Fivetran o Airbyte para ingesta, "
            "dbt para transformación en el warehouse, y Snowflake, BigQuery o Databricks como motor "
            "analítico, orquestado con Airflow o Dagster según las preferencias del cliente."
        ),
        "source": "Capacidades_Tecnicas_SaaS_IA.md",
        "section_type": "capacidades_tecnicas",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    {
        "chunk_id": "capacidades_tecnicas_saas_ia_002",
        "text": (
            "Para clientes de IA/ML, el stack de MLOps de Algoworks incluye MLflow para tracking de "
            "experimentos y registro de modelos, Airflow o Kubeflow Pipelines para orquestación, y "
            "feature stores (Feast) para mantener consistencia entre features online y offline."
        ),
        "source": "Capacidades_Tecnicas_SaaS_IA.md",
        "section_type": "capacidades_tecnicas",
        "metadata": {"anio": 2024, "sector": "ai_ml"},
    },
    {
        "chunk_id": "capacidades_tecnicas_saas_ia_003",
        "text": (
            "El stack de RAG/LLM de Algoworks combina bases de datos vectoriales (Qdrant, Pinecone o "
            "pgvector según el volumen y presupuesto del cliente), pipelines de embeddings versionados, "
            "arneses de evaluación de prompts y integración con APIs de OpenAI, Anthropic o modelos "
            "locales vía Ollama cuando se requiere procesamiento on-premise."
        ),
        "source": "Capacidades_Tecnicas_SaaS_IA.md",
        "section_type": "capacidades_tecnicas",
        "metadata": {"anio": 2024, "sector": "ai_ml"},
    },
    {
        "chunk_id": "capacidades_tecnicas_saas_ia_004",
        "text": (
            "Para arquitecturas SaaS multi-tenant, Algoworks evalúa junto al cliente el tradeoff entre "
            "aislamiento por esquema-por-tenant (mayor aislamiento, mayor costo operativo) y esquema "
            "compartido con row-level security (menor costo, requiere disciplina de queries), además "
            "de diseñar caching y rate-limiting conscientes del tenant."
        ),
        "source": "Capacidades_Tecnicas_SaaS_IA.md",
        "section_type": "capacidades_tecnicas",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    {
        "chunk_id": "capacidades_tecnicas_saas_ia_005",
        "text": (
            "Algoworks implementa pipelines de facturación por uso (usage-based billing) integrando "
            "plataformas como Stripe Billing o Chargebee con el stream de eventos interno del "
            "producto, agregando el consumo en tiempo real para exponerlo tanto a facturación como a "
            "paneles de uso para el cliente final."
        ),
        "source": "Capacidades_Tecnicas_SaaS_IA.md",
        "section_type": "capacidades_tecnicas",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    {
        "chunk_id": "capacidades_tecnicas_saas_ia_006",
        "text": (
            "El stack de observabilidad de Algoworks combina Datadog o Grafana con Prometheus para "
            "métricas de infraestructura, y OpenTelemetry para trazas distribuidas entre "
            "microservicios, permitiendo diagnosticar cuellos de botella en arquitecturas SaaS "
            "complejas."
        ),
        "source": "Capacidades_Tecnicas_SaaS_IA.md",
        "section_type": "capacidades_tecnicas",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    {
        "chunk_id": "capacidades_tecnicas_saas_ia_007",
        "text": (
            "Algoworks despliega infraestructura como código con Terraform para entornos múltiples "
            "(dev/staging/producción), cargas de trabajo containerizadas en Kubernetes (EKS o GKE), y "
            "flujos GitOps con ArgoCD para despliegues auditable y reproducibles."
        ),
        "source": "Capacidades_Tecnicas_SaaS_IA.md",
        "section_type": "capacidades_tecnicas",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    # --- Equipo_Algoworks_SaaS_IA.md (perfiles del equipo para roles SaaS/IA) ---
    {
        "chunk_id": "equipo_algoworks_saas_ia_001",
        "text": (
            "Sofía Reyes, MLOps Engineer en Algoworks, cuenta con 6 años de experiencia y la "
            "certificación AWS Machine Learning Specialty. Lideró la implementación de feature stores "
            "y registros de modelos (MLflow) en 5 proyectos de clientes de IA/ML entre 2022 y 2024."
        ),
        "source": "Equipo_Algoworks_SaaS_IA.md",
        "section_type": "equipo",
        "metadata": {"anio": 2024, "sector": "ai_ml"},
    },
    {
        "chunk_id": "equipo_algoworks_saas_ia_002",
        "text": (
            "Diego Martins, Data Platform Engineer en Algoworks, tiene certificación SnowPro Core "
            "(Snowflake) y 5 años de experiencia diseñando warehouses multi-tenant con dbt, incluyendo "
            "el proyecto de NovaMetrics."
        ),
        "source": "Equipo_Algoworks_SaaS_IA.md",
        "section_type": "equipo",
        "metadata": {"anio": 2024, "sector": "saas"},
    },
    {
        "chunk_id": "equipo_algoworks_saas_ia_003",
        "text": (
            "Laura Chen, ML/LLM Engineer en Algoworks, tiene 4 años de experiencia en NLP y visión por "
            "computadora, y ha llevado a producción 3 sistemas RAG con bases de datos vectoriales "
            "(Qdrant, Pinecone) para distintos clientes."
        ),
        "source": "Equipo_Algoworks_SaaS_IA.md",
        "section_type": "equipo",
        "metadata": {"anio": 2024, "sector": "ai_ml"},
    },
    {
        "chunk_id": "equipo_algoworks_saas_ia_004",
        "text": (
            "El equipo de datos e IA de Algoworks cuenta, a 2024, con 4 ingenieros certificados en AWS "
            "Machine Learning Specialty, 3 certificados SnowPro, y 2 certificados Kubernetes "
            "Administrator (CKA), cubriendo el ciclo completo de plataformas de datos, MLOps e "
            "infraestructura para clientes SaaS y de IA/ML."
        ),
        "source": "Equipo_Algoworks_SaaS_IA.md",
        "section_type": "equipo",
        "metadata": {"anio": 2024, "sector": "saas"},
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
    print(f"Corpus: {len(existing)} -> {len(combined)} chunks ({len(NEW_CHUNKS)} nuevos, 4 fuentes nuevas).")


if __name__ == "__main__":
    main()
