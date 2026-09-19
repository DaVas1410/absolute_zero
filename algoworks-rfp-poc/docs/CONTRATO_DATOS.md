# Contrato de datos — Algoworks RFP PoC

> Fuente de verdad: `backend/api/schemas.py`. Los modelos base son los
> descritos en `CLAUDE.md`, sección 4; las adiciones de sub-project A
> (trazabilidad/explicabilidad extendida) son todas aditivas, no rompen el
> contrato original. **Regla dura:** nadie cambia este schema sin avisar en
> el chat del equipo — frontend y backend dependen de que sea estable desde
> la hora 0.
>
> Este documento cubre el pipeline base (`POST /rfp/process`,
> `GET /rfp/{id}/trace`, `POST /rfp/{req_id}/feedback`, `GET /health`). El
> backend también expone ingestión de PDFs (`POST /corpus/ingest`,
> `POST /rfp/process/pdf`) y un segundo pipeline de composición de propuesta
> consolidada (`POST /rfp/{rfp_id}/compose`, modelos `ProposalSection`,
> `ProposalSectionVerification`, `ComposeMetrics`, `ProposalDocument`) — esos
> son un sub-project aparte, fuera del alcance de este documento.

Este documento describe cada modelo Pydantic del contrato con sus campos y un
ejemplo de instancia en JSON.

---

## Chunk

Un fragmento de conocimiento del corpus (propuestas anteriores, capacidades,
equipo, etc.) indexado en el vectorstore.

| Campo          | Tipo   | Descripción                                                        |
|----------------|--------|---------------------------------------------------------------------|
| `chunk_id`     | `str`  | Identificador único del chunk.                                     |
| `text`         | `str`  | Texto del fragmento.                                                |
| `source`       | `str`  | Documento de origen, ej. `"Propuesta_ClienteX_2023.md"`.            |
| `section_type` | `str`  | `"experiencia_previa"` \| `"capacidades_tecnicas"` \| `"equipo"` \| ... |
| `metadata`     | `dict` | Metadata libre. Default `{}`.                                       |

```json
{
  "chunk_id": "chunk_001",
  "text": "Algoworks entregó 12 proyectos de integración de datos en 2023.",
  "source": "Propuesta_ClienteX_2023.md",
  "section_type": "experiencia_previa",
  "metadata": {}
}
```

**Nota (actualizada):** `RetrievedChunk.text` ahora expone el texto exacto
del `Chunk` recuperado (mismo criterio que `ChunkCitation.text` en el pipeline
de `compose_proposal`), para que el frontend pueda mostrar "el extracto
citado literal" sin inventar contenido.

---

## Requirement

Un requisito estructurado extraído del RFP de entrada.

| Campo            | Tipo  | Descripción                                    |
|-------------------|-------|-------------------------------------------------|
| `req_id`          | `str` | Identificador único del requisito.              |
| `text`            | `str` | Texto del requisito tal como aparece en el RFP. |
| `section_target`  | `str` | Sección destino (enum cerrado en la práctica: `SectionType` — `"experiencia_previa"` \| `"capacidades_tecnicas"` \| `"equipo"`). |

```json
{
  "req_id": "req_001",
  "text": "El proveedor debe demostrar experiencia previa en proyectos similares.",
  "section_target": "experiencia_previa"
}
```

---

## RetrievedChunk

Resultado de la etapa de retrieval: un chunk candidato con su score de
similitud y una justificación en lenguaje natural de por qué fue recuperado.

| Campo           | Tipo    | Descripción                                          |
|------------------|---------|--------------------------------------------------------|
| `chunk_id`       | `str`   | Referencia al `Chunk` recuperado.                      |
| `score`          | `float` | Score de similitud coseno, acotado a `[0, 1]`.         |
| `justification`  | `str`   | Explicación en lenguaje natural de la relevancia.      |
| `source`         | `str`   | Documento de origen del `Chunk` (aditivo). Default `""`. |
| `text`           | `str`   | Texto exacto del `Chunk` recuperado (aditivo). Default `""`. |

```json
{
  "chunk_id": "chunk_001",
  "score": 0.87,
  "justification": "El chunk describe experiencia previa relevante en integración de datos.",
  "source": "Propuesta_ClienteX_2023.md",
  "text": "Algoworks entregó 12 proyectos de integración de datos en 2023."
}
```

---

## CitationSimilarity

Similitud coseno entre el texto del borrador y el texto de un chunk citado,
calculada por `compute_traceability_metrics` — independiente de si el
verificador dice que la cita está soportada.

| Campo        | Tipo    | Descripción                                     |
|--------------|---------|--------------------------------------------------|
| `chunk_id`   | `str`   | Chunk citado.                                    |
| `similarity` | `float` | Similitud coseno embedding(borrador) <-> embedding(chunk). |

```json
{ "chunk_id": "chunk_001", "similarity": 0.81 }
```

---

## TokenUsage

Consumo de tokens/costo estimado de las llamadas a LLM de un nodo (o del
pipeline completo, agregado).

| Campo                 | Tipo    | Descripción                                                    |
|------------------------|---------|-------------------------------------------------------------------|
| `input_tokens`         | `int`   | Tokens de entrada. Default `0`.                                    |
| `output_tokens`        | `int`   | Tokens de salida. Default `0`.                                     |
| `total_tokens`         | `int`   | Suma de entrada + salida. Default `0`.                             |
| `estimated_cost_usd`   | `float` | Costo estimado en USD, best-effort. `0.0` significa "desconocido", no "gratis". Default `0.0`. |

```json
{ "input_tokens": 512, "output_tokens": 128, "total_tokens": 640, "estimated_cost_usd": 0.0021 }
```

---

## DraftSection

Borrador de una sección de la propuesta, generado citando chunks inline.

| Campo                    | Tipo                       | Descripción                                                  |
|---------------------------|-----------------------------|-----------------------------------------------------------------|
| `req_id`                  | `str`                       | Requisito al que responde este borrador.                        |
| `text`                    | `str`                       | Texto redactado, contiene marcadores `[[chunk_id]]` inline.      |
| `cited_chunks`            | `list[str]`                 | Lista de `chunk_id` citados en `text` (solo ids que existen realmente entre los chunks recuperados — las citas alucinadas se filtran en código). |
| `reasoning`               | `str`                       | Explicación del LLM de qué chunks usó y por qué. Default `""`.  |
| `citation_similarities`   | `list[CitationSimilarity]`  | Similitud coseno borrador↔cada chunk citado. Calculado por `compute_traceability_metrics`. Default `[]`. |
| `overall_similarity`      | `float`                     | Similitud coseno borrador↔promedio de los chunks citados. Default `0.0`. |

```json
{
  "req_id": "req_001",
  "text": "Algoworks cuenta con experiencia comprobada [[chunk_001]].",
  "cited_chunks": ["chunk_001"],
  "reasoning": "Se citó chunk_001 porque describe un proyecto de integración de datos comparable.",
  "citation_similarities": [{ "chunk_id": "chunk_001", "similarity": 0.81 }],
  "overall_similarity": 0.81
}
```

---

## VerificationResult

Resultado de verificar si las afirmaciones citadas en un `DraftSection` están
realmente respaldadas por los chunks fuente (tipo NLI).

| Campo          | Tipo         | Descripción                                            |
|-----------------|--------------|-----------------------------------------------------------|
| `req_id`        | `str`        | Requisito verificado.                                     |
| `supported`     | `bool`       | `true` si las citas están respaldadas.                    |
| `issues`        | `list[str]`  | Lista de problemas detectados (vacía si `supported=true`).|
| `confidence`    | `float`      | Confianza del verificador.                                |
| `reasoning`     | `str`        | Motivo del veredicto. Default `""`.                        |
| `retries_used`  | `int`        | Reintentos de `generate_draft` ya consumidos antes de este veredicto (máx. 1). Default `0`. |

```json
{
  "req_id": "req_001",
  "supported": true,
  "issues": [],
  "confidence": 0.92,
  "reasoning": "chunk_001 respalda directamente la afirmación de experiencia previa.",
  "retries_used": 0
}
```

---

## TraceEvent

Evento de trazabilidad que cada nodo del grafo anexa a `trace_log`: qué
recibió, qué decidió y por qué. Es la pieza central de la narrativa de
trazabilidad/explicabilidad.

| Campo             | Tipo               | Descripción                                     |
|--------------------|---------------------|----------------------------------------------------|
| `node`             | `str`               | Nombre del nodo del grafo que generó el evento.     |
| `timestamp`        | `datetime`          | Momento en que ocurrió.                             |
| `input_summary`    | `str`               | Resumen de lo que recibió el nodo.                  |
| `output_summary`   | `str`               | Resumen de lo que produjo el nodo.                  |
| `reasoning`        | `str`               | Explicación de por qué decidió lo que decidió.      |
| `duration_ms`      | `float`             | Duración del nodo en milisegundos. Default `0.0`.   |
| `tokens`           | `TokenUsage \| null`| Consumo de tokens del nodo. `null` si el nodo no hizo ninguna llamada a LLM (ej. `compute_traceability_metrics`). |

```json
{
  "node": "retrieve_chunks",
  "timestamp": "2026-09-18T12:00:00Z",
  "input_summary": "2 requisitos",
  "output_summary": "req_001: 3 chunks, req_002: 2 chunks",
  "reasoning": "Se recuperaron hasta 3 chunks por similitud coseno por requisito y se generó una justificación en lenguaje natural para cada uno.",
  "duration_ms": 842.3,
  "tokens": { "input_tokens": 300, "output_tokens": 60, "total_tokens": 360, "estimated_cost_usd": 0.0009 }
}
```

---

## PipelineMetrics

Métricas agregadas de todo el pipeline, calculadas una sola vez por
`compute_traceability_metrics` cuando el retry loop termina.

| Campo                            | Tipo         | Descripción                                                |
|------------------------------------|--------------|----------------------------------------------------------------|
| `total_duration_ms`               | `float`      | Suma de `duration_ms` de todos los `TraceEvent`.                |
| `total_tokens`                    | `TokenUsage` | Suma de tokens/costo de todos los `TraceEvent` con `tokens != null`. |
| `retries_used`                    | `int`        | Total de reintentos de `generate_draft` consumidos en la corrida. |
| `requirements_supported`          | `int`        | Cantidad de requisitos con `VerificationResult.supported == true`. |
| `requirements_needing_review`     | `int`        | Cantidad de requisitos con `supported == false` (revisión humana). |
| `hallucinated_citations_caught`   | `int`        | Total de citas a `chunk_id` inexistentes detectadas por el post-procesamiento de `generate_draft`. |

```json
{
  "total_duration_ms": 4820.5,
  "total_tokens": { "input_tokens": 3100, "output_tokens": 900, "total_tokens": 4000, "estimated_cost_usd": 0.0124 },
  "retries_used": 1,
  "requirements_supported": 1,
  "requirements_needing_review": 1,
  "hallucinated_citations_caught": 0
}
```

---

## ReasoningPathAudit

Auditoría determinista (sin LLM) de que el grafo efectivamente siguió las
reglas con las que fue diseñado: secuencia de nodos válida, límite de
reintentos respetado, y que ninguna cita en un `DraftSection` referencia un
`chunk_id` que no exista entre los chunks recuperados para ese requisito.

| Campo             | Tipo         | Descripción                                     |
|--------------------|--------------|----------------------------------------------------|
| `is_consistent`    | `bool`       | `true` si no se detectó ningún problema.            |
| `node_sequence`    | `list[str]`  | Secuencia real de nodos ejecutados, en orden.       |
| `issues`           | `list[str]`  | Problemas detectados. Vacío cuando `is_consistent` es `true`. |

```json
{
  "is_consistent": true,
  "node_sequence": ["extract_requirements", "retrieve_chunks", "generate_draft", "verify_citations", "compute_traceability_metrics"],
  "issues": []
}
```

Cuando hay un reintento, `node_sequence` repite el par
`generate_draft`/`verify_citations` antes de `compute_traceability_metrics`:
`[..., "generate_draft", "verify_citations", "generate_draft", "verify_citations", "compute_traceability_metrics"]`.

---

## PipelineResult

Resultado completo del pipeline para un RFP, devuelto por
`POST /rfp/process` (y `POST /rfp/process/pdf`) y consumido por el frontend
para el panel de explicabilidad.

| Campo                  | Tipo                                | Descripción                                            |
|-------------------------|--------------------------------------|-----------------------------------------------------------|
| `rfp_id`                | `str`                                | Identificador del RFP procesado.                          |
| `requirements`          | `list[Requirement]`                  | Requisitos extraídos.                                      |
| `retrieved`             | `dict[str, list[RetrievedChunk]]`    | Chunks recuperados por `req_id`.                           |
| `drafts`                | `dict[str, DraftSection]`            | Borrador de sección por `req_id`.                          |
| `verification`          | `dict[str, VerificationResult]`      | Resultado de verificación por `req_id`.                    |
| `trace_log`             | `list[TraceEvent]`                   | Traza completa de decisiones del pipeline, en orden.       |
| `metrics`               | `PipelineMetrics`                    | Métricas agregadas de la corrida completa.                 |
| `reasoning_path_audit`  | `ReasoningPathAudit`                 | Auditoría determinista del camino de ejecución del grafo.  |

```json
{
  "rfp_id": "rfp_001",
  "requirements": [
    {
      "req_id": "req_001",
      "text": "El proveedor debe demostrar experiencia previa en proyectos similares.",
      "section_target": "experiencia_previa"
    }
  ],
  "retrieved": {
    "req_001": [
      {
        "chunk_id": "chunk_001",
        "score": 0.87,
        "justification": "El chunk describe experiencia previa relevante en integración de datos.",
        "source": "Propuesta_ClienteX_2023.md"
      }
    ]
  },
  "drafts": {
    "req_001": {
      "req_id": "req_001",
      "text": "Algoworks cuenta con experiencia comprobada [[chunk_001]].",
      "cited_chunks": ["chunk_001"],
      "reasoning": "Se citó chunk_001 porque describe un proyecto de integración de datos comparable.",
      "citation_similarities": [{ "chunk_id": "chunk_001", "similarity": 0.81 }],
      "overall_similarity": 0.81
    }
  },
  "verification": {
    "req_001": {
      "req_id": "req_001",
      "supported": true,
      "issues": [],
      "confidence": 0.92,
      "reasoning": "chunk_001 respalda directamente la afirmación de experiencia previa.",
      "retries_used": 0
    }
  },
  "trace_log": [
    {
      "node": "extract_requirements",
      "timestamp": "2026-09-18T12:00:00Z",
      "input_summary": "rfp_id=rfp_001, 210 caracteres de RFP",
      "output_summary": "1 requisito extraído",
      "reasoning": "Se extrajeron los requisitos usando structured output del LLM.",
      "duration_ms": 610.2,
      "tokens": { "input_tokens": 200, "output_tokens": 40, "total_tokens": 240, "estimated_cost_usd": 0.0006 }
    },
    {
      "node": "retrieve_chunks",
      "timestamp": "2026-09-18T12:00:01Z",
      "input_summary": "1 requisito",
      "output_summary": "req_001: 1 chunk",
      "reasoning": "Se recuperaron hasta 3 chunks por similitud coseno por requisito.",
      "duration_ms": 842.3,
      "tokens": { "input_tokens": 300, "output_tokens": 60, "total_tokens": 360, "estimated_cost_usd": 0.0009 }
    },
    {
      "node": "generate_draft",
      "timestamp": "2026-09-18T12:00:02Z",
      "input_summary": "1 requisito a (re)generar",
      "output_summary": "1 DraftSection generado, 0 con citas alucinadas",
      "reasoning": "El post-procesamiento validó que cada chunk_id citado exista entre los chunks recuperados.",
      "duration_ms": 1530.8,
      "tokens": { "input_tokens": 1400, "output_tokens": 500, "total_tokens": 1900, "estimated_cost_usd": 0.0057 }
    },
    {
      "node": "verify_citations",
      "timestamp": "2026-09-18T12:00:04Z",
      "input_summary": "1 borrador verificado",
      "output_summary": "1 soportado, 0 enviados a reintento",
      "reasoning": "El resto se verifica con un prompt tipo NLI.",
      "duration_ms": 1200.1,
      "tokens": { "input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500, "estimated_cost_usd": 0.0045 }
    },
    {
      "node": "compute_traceability_metrics",
      "timestamp": "2026-09-18T12:00:05Z",
      "input_summary": "1 borrador final, 4 eventos de trace previos",
      "output_summary": "1/1 requisitos soportados, 0 citas alucinadas detectadas en total",
      "reasoning": "Auditoría determinista (sin LLM) de la secuencia de nodos y las citas: camino consistente.",
      "duration_ms": 637.1,
      "tokens": null
    }
  ],
  "metrics": {
    "total_duration_ms": 4820.5,
    "total_tokens": { "input_tokens": 3100, "output_tokens": 900, "total_tokens": 4000, "estimated_cost_usd": 0.0117 },
    "retries_used": 0,
    "requirements_supported": 1,
    "requirements_needing_review": 0,
    "hallucinated_citations_caught": 0
  },
  "reasoning_path_audit": {
    "is_consistent": true,
    "node_sequence": ["extract_requirements", "retrieve_chunks", "generate_draft", "verify_citations", "compute_traceability_metrics"],
    "issues": []
  }
}
```
