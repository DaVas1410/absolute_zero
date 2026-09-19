# CLAUDE.md — Contexto del proyecto (Algoworks RFP PoC)

> Este archivo va en la raíz del repo. Cualquier integrante que abra Claude Code
> en cualquier subcarpeta (`backend/`, `frontend/`, `data/`) debe tener acceso
> a este contexto compartido. No lo edites sin avisar al equipo — es la fuente
> de verdad del contrato.

## 1. Problema (resumen del challenge brief — Algoworks / Hackathon Innovación Aplicada)

Algoworks prepara propuestas y respuestas a RFP de forma recurrente. El proceso
combina (a) el requerimiento del cliente y (b) conocimiento acumulado de
propuestas anteriores. Parte del trabajo es repetitivo y se presta a
apoyo/automatización con LLMs, pero **no basta con generar contenido**: la
solución debe permitir entender qué información usó el sistema, qué insumos
consideró, y por qué decidió incorporar ciertos elementos.

**Pregunta central:** ¿Cómo usar IA para apoyar la preparación de propuestas y
respuestas a RFP, manteniendo trazabilidad sobre los insumos utilizados y las
decisiones tomadas por el sistema?

**Los dos conceptos que más pesan en la evaluación: trazabilidad y explicabilidad.**
No es suficiente mostrar contenido generado por IA — debe poder explicarse cómo
se llegó a ese resultado.

**Fuera de alcance:** documentos legales, contratos, propuestas comerciales
reales de Algoworks. Todo el corpus y los RFPs de entrada son ficticios/sintéticos.
No se espera automatizar el proceso de punta a punta — se demuestra un
flujo/componente concreto.

## 2. Solución elegida

Sistema de agentes orquestado con **LangGraph**, con LLM servido vía **Groq**
(proveedor gratuito, alta velocidad) y **Ollama local** como fallback offline
si falla la conectividad del hackathon. Patrón RAG con trazabilidad explícita
en cada paso.

### Grafo (nodos)

```
extract_requirements → retrieve_chunks → generate_draft → verify_citations
                                                 ↑                  │
                                                 └── (si no soportado, 1 reintento máx) ──┘
```

- **extract_requirements**: parsea el RFP simulado a una lista de requisitos
  estructurados (JSON), con `section_target` restringido a un enum cerrado.
  Fallback sin LLM (split por líneas numeradas) si el structured output falla.
- **retrieve_chunks**: embeddings + similitud coseno sobre el corpus ficticio
  (vectorstore local, Chroma). Por cada chunk candidato, un segundo prompt
  corto genera una `justification` en lenguaje natural (no solo el score).
- **generate_draft**: redacta la sección citando `[[chunk_id]]` inline por
  cada afirmación factual. Post-procesamiento en código valida que cada
  chunk_id citado exista de verdad en los chunks recuperados (si el LLM
  alucina un id, se marca automáticamente como error de citación).
- **verify_citations**: por cada afirmación citada, verifica si el chunk
  fuente realmente la respalda (tipo NLI: sí/no + por qué). Si falla, dispara
  edge condicional de vuelta a `generate_draft` (máx. 1 reintento), si no
  se marca para revisión humana.

Cada nodo anexa un evento a `trace_log` (qué recibió, qué decidió, por qué) —
esta es la pieza que sostiene toda la narrativa de trazabilidad/explicabilidad
frente a los jueces.

## 3. Equipo y responsabilidades

- **Backend (LangGraph, RAG, API)** — dueño del contrato de datos, el grafo,
  el vectorstore y la API FastAPI.
- **Datos + revisión** — corpus ficticio de conocimiento (chunks), RFPs
  simulados de entrada, casos de prueba (incluido al menos un caso
  adversarial donde el verificador debe atrapar un error a propósito), QA
  cualitativa del pipeline.
- **Frontend** — UI que consume la API, muestra el panel de explicabilidad
  (chunks + score + justificación + borrador citado + veredicto del
  verificador) y permite aceptar/rechazar cada sección (human-in-the-loop).

## 4. Contrato de datos (fuente de verdad — `backend/api/schemas.py`)

```python
class Chunk(BaseModel):
    chunk_id: str
    text: str
    source: str              # ej. "Propuesta_ClienteX_2023.md"
    section_type: str        # "experiencia_previa" | "capacidades_tecnicas" | "equipo" | ...
    metadata: dict = {}

class Requirement(BaseModel):
    req_id: str
    text: str
    section_target: str

class RetrievedChunk(BaseModel):
    chunk_id: str
    score: float
    justification: str

class DraftSection(BaseModel):
    req_id: str
    text: str                 # contiene marcadores [[chunk_id]] inline
    cited_chunks: list[str]

class VerificationResult(BaseModel):
    req_id: str
    supported: bool
    issues: list[str]
    confidence: float

class TraceEvent(BaseModel):
    node: str
    timestamp: datetime
    input_summary: str
    output_summary: str
    reasoning: str

class PipelineResult(BaseModel):
    rfp_id: str
    requirements: list[Requirement]
    retrieved: dict[str, list[RetrievedChunk]]
    drafts: dict[str, DraftSection]
    verification: dict[str, VerificationResult]
    trace_log: list[TraceEvent]
```

**Regla dura:** nadie cambia este schema sin avisar en el chat del equipo —
frontend y backend dependen de que sea estable desde la hora 0.

## 5. API (contrato backend ↔ frontend)

```
POST /rfp/process              → dispara el grafo completo, devuelve PipelineResult
GET  /rfp/{id}/trace           → devuelve trace_log completo
POST /rfp/{req_id}/feedback    → {accepted: bool} — human-in-the-loop
GET  /health                   → chequeo simple, usar para validar conexión temprano
```

CORS abierto para desarrollo. Formato de error estándar:
`{"error": str, "detail": str}`.

## 6. Stack

- Backend: Python, FastAPI, LangGraph, langchain-groq (+ langchain-ollama de
  fallback), Chroma (vectorstore), sentence-transformers para embeddings.
- Frontend: Streamlit (o React/Next si alcanza el tiempo).
- LLM: Groq (Llama 3.3 70B para generación/verificación, modelo más chico
  para extracción/retrieval si conviene por velocidad). Fallback Ollama local.

## 7. Convenciones de código

- Prompts versionados como archivos de texto en `backend/graph/prompts/`, no
  hardcodeados en el código de los nodos.
- Todo output de LLM que deba ser estructurado usa structured output
  (`.with_structured_output(schema)` o `format="json"` en Ollama) — nunca
  parsear texto libre a mano si se puede evitar.
- Cada nodo del grafo debe anexar su propio `TraceEvent` — no dejarlo para el
  final.
- Nombres de variables y funciones en inglés; comentarios y docstrings en
  español está bien si el equipo lo prefiere así.

## 8. Qué NO hacer (para no perder tiempo de hackathon)

- No automatizar el flujo de punta a punta — un componente/tramo concreto
  basta y es lo que pide el brief.
- No usar documentos reales, legales o contratos — todo el corpus es ficticio.
- No separar gramática/estilo en un agente independiente salvo que sobre
  tiempo — va dentro del prompt del generador.
- No bloquear el desarrollo en paralelo esperando datos reales — backend
  arranca con 3-4 chunks dummy propios; frontend arranca con un
  `PipelineResult` mockeado.
