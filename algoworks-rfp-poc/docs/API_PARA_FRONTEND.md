# API backend — guía para frontend

> Estado actual: el grafo real de LangGraph está conectado — `POST
> /rfp/process` invoca el pipeline completo (`extract_requirements ->
> retrieve_chunks -> generate_draft -> verify_citations ->
> compute_traceability_metrics`, con hasta 1 reintento de
> `generate_draft`/`verify_citations`), no datos mockeados. El shape de las
> respuestas es el descrito en `docs/CONTRATO_DATOS.md`.
>
> El backend también expone ingestión de PDFs (`POST /corpus/ingest`,
> `POST /rfp/process/pdf`) y un segundo pipeline de composición de propuesta
> consolidada (`POST /rfp/{rfp_id}/compose`) — sub-project aparte, no
> cubierto en detalle por esta guía (ver `backend/api/schemas.py` para sus
> modelos: `CorpusIngestResult`, `ProposalDocument`, etc.).

## Cómo levantar el servidor

Desde `algoworks-rfp-poc/backend/`:

```bash
uv sync   # instala/actualiza dependencias si pyproject.toml/uv.lock cambiaron
uv run uvicorn api.main:app --reload --port 8000
```

- **Base URL:** `http://localhost:8000`
- **Docs interactivas (Swagger):** `http://localhost:8000/docs`
- **CORS:** abierto (`allow_origins=["*"]`) — se puede pegar desde cualquier origen sin configuración adicional.
- **LLM:** requiere `GROQ_API_KEY` en el entorno (o un `.env` en `backend/`,
  ver `graph/llm.py`). Sin esa variable, `get_chat_llm` falla al construir el
  cliente de Groq **antes** de poder caer al fallback de Ollama — es decir,
  sin `GROQ_API_KEY` el pipeline no corre en absoluto, ni siquiera con Ollama
  local levantado. Si Groq falla en tiempo de invocación (no al construir el
  cliente), ahí sí cae a Ollama local (`OLLAMA_BASE_URL`, default
  `http://localhost:11434`).
- **Arranque:** el primer request paga el costo de descargar/cargar el
  modelo de embeddings y construir el vectorstore — `main.py` lo precalienta
  en el evento de `startup` para no pagarlo en el primer `POST
  /rfp/process` de una demo.

## Formato de error estándar

Cualquier error (404, 422, 500) responde con este shape:

```json
{
  "error": "Not Found",
  "detail": "No hay trace disponible para rfp_id='nope'. Ejecuta POST /rfp/process primero."
}
```

## Endpoints

### `GET /health`

Chequeo simple de conexión.

**Respuesta 200:**
```json
{ "status": "ok" }
```

---

### `POST /rfp/process`

Dispara el pipeline real de LangGraph y devuelve un `PipelineResult` completo.

**Body:**
```json
{
  "rfp_id": "rfp_demo",
  "rfp_text": "texto del RFP simulado"
}
```

**Respuesta 200** (`PipelineResult`, ver `docs/CONTRATO_DATOS.md` para el detalle de cada tipo anidado, incluyendo `metrics` y `reasoning_path_audit`):

```json
{
  "rfp_id": "rfp_demo",
  "requirements": [
    {
      "req_id": "req_001",
      "text": "El proveedor debe demostrar experiencia previa en proyectos de integración de datos de tamaño y complejidad similares.",
      "section_target": "experiencia_previa"
    },
    {
      "req_id": "req_002",
      "text": "El proveedor debe describir las capacidades técnicas y la arquitectura propuesta para la integración de datos en tiempo real.",
      "section_target": "capacidades_tecnicas"
    }
  ],
  "retrieved": {
    "req_001": [
      { "chunk_id": "chunk_001", "score": 0.89, "justification": "El chunk describe un proyecto de integración de datos de alcance comparable, incluyendo volumen de datos y timeline.", "source": "Propuesta_ClienteManufactura_2023.md" },
      { "chunk_id": "chunk_002", "score": 0.76, "justification": "Menciona experiencia previa con el mismo tipo de cliente (sector retail), relevante para el requisito de experiencia.", "source": "Propuesta_ClienteRetail_2022.md" }
    ],
    "req_002": [
      { "chunk_id": "chunk_004", "score": 0.83, "justification": "Describe la arquitectura de referencia de Algoworks para pipelines de datos en tiempo real (Kafka + Spark Streaming).", "source": "Capacidades_Tecnicas_Algoworks.md" }
    ]
  },
  "drafts": {
    "req_001": {
      "req_id": "req_001",
      "text": "Algoworks cuenta con experiencia comprobada en proyectos de integración de datos de alcance similar [[chunk_001]], incluyendo trabajo previo con clientes del sector retail [[chunk_002]].",
      "cited_chunks": ["chunk_001", "chunk_002"],
      "reasoning": "Se citaron chunk_001 y chunk_002 porque describen proyectos de integración/retail comparables.",
      "citation_similarities": [
        { "chunk_id": "chunk_001", "similarity": 0.84 },
        { "chunk_id": "chunk_002", "similarity": 0.77 }
      ],
      "overall_similarity": 0.80
    },
    "req_002": {
      "req_id": "req_002",
      "text": "Proponemos una arquitectura basada en Kafka y Spark Streaming para la integración de datos en tiempo real [[chunk_004]], con una latencia end-to-end de 50ms garantizada por el SLA del proveedor cloud [[chunk_004]].",
      "cited_chunks": ["chunk_004"],
      "reasoning": "Se citó chunk_004 por describir la arquitectura de streaming de referencia.",
      "citation_similarities": [{ "chunk_id": "chunk_004", "similarity": 0.55 }],
      "overall_similarity": 0.55
    }
  },
  "verification": {
    "req_001": { "req_id": "req_001", "supported": true, "issues": [], "confidence": 0.91, "reasoning": "chunk_001 y chunk_002 respaldan directamente la afirmación.", "retries_used": 0 },
    "req_002": {
      "req_id": "req_002",
      "supported": false,
      "issues": [
        "chunk_004 describe la arquitectura de streaming pero no menciona ningún SLA de latencia de 50ms; esa afirmación parece inventada por el generador."
      ],
      "confidence": 0.38,
      "reasoning": "La cifra de 50ms no aparece en ningún chunk recuperado.",
      "retries_used": 1
    }
  },
  "trace_log": [
    { "node": "extract_requirements", "timestamp": "2026-09-19T00:32:35Z", "input_summary": "...", "output_summary": "2 requisitos extraídos", "reasoning": "...", "duration_ms": 610.2, "tokens": { "input_tokens": 200, "output_tokens": 40, "total_tokens": 240, "estimated_cost_usd": 0.0006 } },
    { "node": "retrieve_chunks", "timestamp": "2026-09-19T00:32:36Z", "input_summary": "...", "output_summary": "req_001: 2 chunks, req_002: 1 chunk", "reasoning": "...", "duration_ms": 842.3, "tokens": { "input_tokens": 300, "output_tokens": 60, "total_tokens": 360, "estimated_cost_usd": 0.0009 } },
    { "node": "generate_draft", "timestamp": "2026-09-19T00:32:37Z", "input_summary": "...", "output_summary": "2 DraftSection generados, 0 con citas alucinadas", "reasoning": "...", "duration_ms": 1530.8, "tokens": { "input_tokens": 1400, "output_tokens": 500, "total_tokens": 1900, "estimated_cost_usd": 0.0057 } },
    { "node": "verify_citations", "timestamp": "2026-09-19T00:32:39Z", "input_summary": "...", "output_summary": "1 soportado, 1 enviado a reintento", "reasoning": "...", "duration_ms": 1200.1, "tokens": { "input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500, "estimated_cost_usd": 0.0045 } },
    { "node": "generate_draft", "timestamp": "2026-09-19T00:32:40Z", "input_summary": "...", "output_summary": "1 DraftSection regenerado", "reasoning": "...", "duration_ms": 980.4, "tokens": { "input_tokens": 700, "output_tokens": 250, "total_tokens": 950, "estimated_cost_usd": 0.0029 } },
    { "node": "verify_citations", "timestamp": "2026-09-19T00:32:41Z", "input_summary": "...", "output_summary": "req_002 sigue sin soportarse tras el reintento", "reasoning": "...", "duration_ms": 640.7, "tokens": { "input_tokens": 600, "output_tokens": 150, "total_tokens": 750, "estimated_cost_usd": 0.0023 } },
    { "node": "compute_traceability_metrics", "timestamp": "2026-09-19T00:32:42Z", "input_summary": "2 borradores finales, 6 eventos de trace previos", "output_summary": "1/2 requisitos soportados, 0 citas alucinadas detectadas en total", "reasoning": "Camino consistente.", "duration_ms": 512.0, "tokens": null }
  ],
  "metrics": {
    "total_duration_ms": 6316.5,
    "total_tokens": { "input_tokens": 4400, "output_tokens": 1300, "total_tokens": 5700, "estimated_cost_usd": 0.0169 },
    "retries_used": 1,
    "requirements_supported": 1,
    "requirements_needing_review": 1,
    "hallucinated_citations_caught": 0
  },
  "reasoning_path_audit": {
    "is_consistent": true,
    "node_sequence": ["extract_requirements", "retrieve_chunks", "generate_draft", "verify_citations", "generate_draft", "verify_citations", "compute_traceability_metrics"],
    "issues": []
  }
}
```

**Notas para el panel de explicabilidad:**
- `req_001` es el caso "feliz" (`supported: true`) y `req_002` es el caso que
  debe fallar (`supported: false`, con `issues` explicando por qué, y
  `retries_used: 1` mostrando que ya agotó su reintento) — los dos sample
  RFPs en `data/sample_rfps/` están pensados para producir, respectivamente,
  cada uno de estos casos.
- `drafts[req_id].text` trae marcadores `[[chunk_id]]` inline; esos IDs
  siempre existen en `retrieved[req_id]` (o en `cited_chunks`) — las citas a
  ids inexistentes se filtran en código y no llegan a `cited_chunks`.
- `drafts[req_id].reasoning`, `.citation_similarities` y
  `.overall_similarity`, y `verification[req_id].reasoning`/`.retries_used`
  son campos de trazabilidad adicionales (sub-project A) — mostrarlos, no
  solo el veredicto base.
- `metrics` y `reasoning_path_audit` son top-level en `PipelineResult`, no
  van por `req_id` — son de toda la corrida.
- `RetrievedChunk` ahora incluye `text` (texto exacto del chunk recuperado),
  además de `chunk_id`/`score`/`justification`/`source`. Un panel de "ver
  fuente completa" puede mostrar `text` directamente.
- El backend guarda el último resultado en memoria por `rfp_id` (no persiste
  en disco); si reinician el servidor, hay que volver a llamar
  `/rfp/process` antes de pedir el `/trace`.

---

### `GET /rfp/{rfp_id}/trace`

Devuelve solo `trace_log` (lista de `TraceEvent`, con `duration_ms` y
`tokens` incluidos) del último `PipelineResult` generado para ese `rfp_id`.
Requiere haber llamado antes a `POST /rfp/process` (o `POST
/rfp/process/pdf`) con ese mismo `rfp_id`.

**Respuesta 200:** array de `TraceEvent` (ver arriba, campo `trace_log`).

**Respuesta 404** si no se ha procesado ese `rfp_id` todavía (formato de error estándar).

---

### `POST /rfp/{req_id}/feedback`

Human-in-the-loop: aceptar o rechazar una sección generada.

**Body:**
```json
{ "accepted": true }
```

**Respuesta 200:**
```json
{ "status": "received" }
```

Por ahora solo queda logueado en el servidor (no se persiste ni cambia el `PipelineResult`).

## Referencias

- Contrato de datos completo (todos los modelos Pydantic): `docs/CONTRATO_DATOS.md`
- Contexto general del proyecto y del grafo: `CLAUDE.md` (raíz del monorepo)
