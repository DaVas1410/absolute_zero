# API backend — guía para frontend

> Estado actual: los 4 endpoints existen y responden con datos **mockeados**
> pero válidos según el contrato de datos (`docs/CONTRATO_DATOS.md`). No hay
> grafo real corriendo todavía — ver `# TODO: reemplazar por invocación real
> del grafo LangGraph` en `backend/api/main.py`. El shape de las respuestas
> ya es el definitivo, así que frontend puede construirse contra esto sin
> esperar al backend real.

## Cómo levantar el servidor

Desde `algoworks-rfp-poc/backend/`:

```bash
uv run uvicorn api.main:app --reload --port 8000
```

- **Base URL:** `http://localhost:8000`
- **Docs interactivas (Swagger):** `http://localhost:8000/docs`
- **CORS:** abierto (`allow_origins=["*"]`) — se puede pegar desde cualquier origen sin configuración adicional.

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

Dispara el pipeline (mockeado por ahora) y devuelve un `PipelineResult` completo.

**Body:**
```json
{
  "rfp_id": "rfp_demo",
  "rfp_text": "texto del RFP simulado"
}
```

**Respuesta 200** (`PipelineResult`, ver `docs/CONTRATO_DATOS.md` para el detalle de cada tipo anidado):

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
      { "chunk_id": "chunk_002", "score": 0.76, "justification": "Menciona experiencia previa con el mismo tipo de cliente (sector retail), relevante para el requisito de experiencia.", "source": "Propuesta_ClienteRetail_2022.md" },
      { "chunk_id": "chunk_003", "score": 0.61, "justification": "Relacionado tangencialmente: describe un proyecto de migración de datos, no de integración, pero comparte stack.", "source": "Propuesta_ClienteLogistica_2021.md" }
    ],
    "req_002": [
      { "chunk_id": "chunk_004", "score": 0.83, "justification": "Describe la arquitectura de referencia de Algoworks para pipelines de datos en tiempo real (Kafka + Spark Streaming).", "source": "Capacidades_Tecnicas_Algoworks.md" },
      { "chunk_id": "chunk_005", "score": 0.70, "justification": "Detalla las certificaciones técnicas del equipo en plataformas de streaming de datos.", "source": "Equipo_Algoworks.md" }
    ]
  },
  "drafts": {
    "req_001": {
      "req_id": "req_001",
      "text": "Algoworks cuenta con experiencia comprobada en proyectos de integración de datos de alcance similar [[chunk_001]], incluyendo trabajo previo con clientes del sector retail [[chunk_002]].",
      "cited_chunks": ["chunk_001", "chunk_002"]
    },
    "req_002": {
      "req_id": "req_002",
      "text": "Proponemos una arquitectura basada en Kafka y Spark Streaming para la integración de datos en tiempo real [[chunk_004]], con una latencia end-to-end de 50ms garantizada por el SLA del proveedor cloud [[chunk_004]].",
      "cited_chunks": ["chunk_004"]
    }
  },
  "verification": {
    "req_001": { "req_id": "req_001", "supported": true, "issues": [], "confidence": 0.91 },
    "req_002": {
      "req_id": "req_002",
      "supported": false,
      "issues": [
        "chunk_004 describe la arquitectura de streaming pero no menciona ningún SLA de latencia de 50ms; esa afirmación parece inventada por el generador."
      ],
      "confidence": 0.38
    }
  },
  "trace_log": [
    { "node": "extract_requirements", "timestamp": "2026-09-19T00:32:35.356527Z", "input_summary": "...", "output_summary": "2 requisitos extraídos", "reasoning": "..." },
    { "node": "retrieve_chunks", "timestamp": "2026-09-19T00:32:35.356527Z", "input_summary": "...", "output_summary": "3 chunks para req_001, 2 chunks para req_002", "reasoning": "..." },
    { "node": "generate_draft", "timestamp": "2026-09-19T00:32:35.356527Z", "input_summary": "...", "output_summary": "2 DraftSection generados, todos con citas [[chunk_id]] válidas", "reasoning": "..." },
    { "node": "verify_citations", "timestamp": "2026-09-19T00:32:35.356527Z", "input_summary": "...", "output_summary": "req_001 soportado, req_002 no soportado (1 reintento agotado)", "reasoning": "..." }
  ]
}
```

**Notas para el panel de explicabilidad:**
- `req_001` es el caso "feliz" (`supported: true`) y `req_002` es el caso que debe fallar (`supported: false`, con `issues` explicando por qué) — úsenlos para probar ambos estados visuales del veredicto del verificador.
- `drafts[req_id].text` trae marcadores `[[chunk_id]]` inline; esos IDs siempre existen en `retrieved[req_id]` (o en `cited_chunks`), así que se pueden resolver a un chunk concreto para el hover/tooltip de citas.
- El backend guarda el último resultado en memoria por `rfp_id` (no persiste en disco); si reinician el servidor, hay que volver a llamar `/rfp/process` antes de pedir el `/trace`.

---

### `GET /rfp/{rfp_id}/trace`

Devuelve solo `trace_log` (lista de `TraceEvent`) del último `PipelineResult` generado para ese `rfp_id`. Requiere haber llamado antes a `POST /rfp/process` con ese mismo `rfp_id`.

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
