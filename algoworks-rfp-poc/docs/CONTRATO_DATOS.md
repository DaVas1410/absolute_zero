# Contrato de datos — Algoworks RFP PoC

> Fuente de verdad: `backend/api/schemas.py`, que implementa exactamente los
> modelos descritos en `CLAUDE.md`, sección 4. **Regla dura:** nadie cambia
> este schema sin avisar en el chat del equipo — frontend y backend dependen
> de que sea estable desde la hora 0.

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

---

## Requirement

Un requisito estructurado extraído del RFP de entrada.

| Campo            | Tipo  | Descripción                                    |
|-------------------|-------|-------------------------------------------------|
| `req_id`          | `str` | Identificador único del requisito.              |
| `text`            | `str` | Texto del requisito tal como aparece en el RFP. |
| `section_target`  | `str` | Sección destino (enum cerrado en la práctica).  |

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
| `score`          | `float` | Score de similitud coseno.                             |
| `justification`  | `str`   | Explicación en lenguaje natural de la relevancia.      |

```json
{
  "chunk_id": "chunk_001",
  "score": 0.87,
  "justification": "El chunk describe experiencia previa relevante en integración de datos."
}
```

---

## DraftSection

Borrador de una sección de la propuesta, generado citando chunks inline.

| Campo           | Tipo         | Descripción                                                  |
|------------------|--------------|-----------------------------------------------------------------|
| `req_id`         | `str`        | Requisito al que responde este borrador.                        |
| `text`           | `str`        | Texto redactado, contiene marcadores `[[chunk_id]]` inline.      |
| `cited_chunks`   | `list[str]`  | Lista de `chunk_id` citados en `text`.                          |

```json
{
  "req_id": "req_001",
  "text": "Algoworks cuenta con experiencia comprobada [[chunk_001]].",
  "cited_chunks": ["chunk_001"]
}
```

---

## VerificationResult

Resultado de verificar si las afirmaciones citadas en un `DraftSection` están
realmente respaldadas por los chunks fuente (tipo NLI).

| Campo         | Tipo         | Descripción                                            |
|----------------|--------------|-----------------------------------------------------------|
| `req_id`       | `str`        | Requisito verificado.                                     |
| `supported`    | `bool`       | `true` si las citas están respaldadas.                    |
| `issues`       | `list[str]`  | Lista de problemas detectados (vacía si `supported=true`).|
| `confidence`   | `float`      | Confianza del verificador.                                |

```json
{
  "req_id": "req_001",
  "supported": true,
  "issues": [],
  "confidence": 0.92
}
```

---

## TraceEvent

Evento de trazabilidad que cada nodo del grafo anexa a `trace_log`: qué
recibió, qué decidió y por qué. Es la pieza central de la narrativa de
trazabilidad/explicabilidad.

| Campo             | Tipo        | Descripción                                     |
|--------------------|-------------|----------------------------------------------------|
| `node`             | `str`       | Nombre del nodo del grafo que generó el evento.     |
| `timestamp`        | `datetime`  | Momento en que ocurrió.                             |
| `input_summary`    | `str`       | Resumen de lo que recibió el nodo.                  |
| `output_summary`   | `str`       | Resumen de lo que produjo el nodo.                  |
| `reasoning`        | `str`       | Explicación de por qué decidió lo que decidió.      |

```json
{
  "node": "retrieve_chunks",
  "timestamp": "2026-09-18T12:00:00",
  "input_summary": "requirement=req_001",
  "output_summary": "1 chunk recuperado",
  "reasoning": "El chunk_001 tiene la mayor similitud coseno con el requisito."
}
```

---

## PipelineResult

Resultado completo del pipeline para un RFP, devuelto por
`POST /rfp/process` y consumido por el frontend para el panel de
explicabilidad.

| Campo           | Tipo                                | Descripción                                            |
|------------------|--------------------------------------|-----------------------------------------------------------|
| `rfp_id`         | `str`                                | Identificador del RFP procesado.                          |
| `requirements`   | `list[Requirement]`                  | Requisitos extraídos.                                      |
| `retrieved`      | `dict[str, list[RetrievedChunk]]`    | Chunks recuperados por `req_id`.                           |
| `drafts`         | `dict[str, DraftSection]`            | Borrador de sección por `req_id`.                          |
| `verification`   | `dict[str, VerificationResult]`      | Resultado de verificación por `req_id`.                    |
| `trace_log`      | `list[TraceEvent]`                   | Traza completa de decisiones del pipeline, en orden.       |

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
        "justification": "El chunk describe experiencia previa relevante en integración de datos."
      }
    ]
  },
  "drafts": {
    "req_001": {
      "req_id": "req_001",
      "text": "Algoworks cuenta con experiencia comprobada [[chunk_001]].",
      "cited_chunks": ["chunk_001"]
    }
  },
  "verification": {
    "req_001": {
      "req_id": "req_001",
      "supported": true,
      "issues": [],
      "confidence": 0.92
    }
  },
  "trace_log": [
    {
      "node": "retrieve_chunks",
      "timestamp": "2026-09-18T12:00:00",
      "input_summary": "requirement=req_001",
      "output_summary": "1 chunk recuperado",
      "reasoning": "El chunk_001 tiene la mayor similitud coseno con el requisito."
    }
  ]
}
```
