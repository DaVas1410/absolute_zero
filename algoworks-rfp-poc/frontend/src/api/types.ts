/**
 * TypeScript mirror of backend/api/schemas.py, scoped to the base RFP
 * pipeline (POST /rfp/process, GET /rfp/{id}/trace, POST /rfp/{req_id}/feedback,
 * GET /health). The backend also exposes PDF ingestion and a separate
 * "compose proposal" pipeline (ProposalDocument, ComposeMetrics, etc.) -
 * intentionally out of scope for this app; see docs/CONTRATO_DATOS.md.
 */

// section_target is `str` in the Pydantic model, constrained in practice to
// this set by extract_requirements.py's SectionTarget literal - typed as a
// widened union so an unexpected value still renders instead of crashing a
// lookup table.
export type SectionTarget = 'experiencia_previa' | 'capacidades_tecnicas' | 'equipo' | (string & {})

export interface Requirement {
  req_id: string
  text: string
  section_target: SectionTarget
}

export interface RetrievedChunk {
  chunk_id: string
  score: number
  justification: string
  source: string
}

export interface CitationSimilarity {
  chunk_id: string
  similarity: number
}

export interface TokenUsage {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  /** Best-effort; 0.0 means "unknown", not "free". */
  estimated_cost_usd: number
}

export interface DraftSection {
  req_id: string
  /** Contains inline `[[chunk_id]]` markers. */
  text: string
  cited_chunks: string[]
  reasoning: string
  citation_similarities: CitationSimilarity[]
  overall_similarity: number
}

export interface VerificationResult {
  req_id: string
  supported: boolean
  issues: string[]
  confidence: number
  reasoning: string
  retries_used: number
}

export interface TraceEvent {
  node: string
  timestamp: string
  input_summary: string
  output_summary: string
  reasoning: string
  duration_ms: number
  /** null when the node made no LLM call. */
  tokens: TokenUsage | null
}

export interface PipelineMetrics {
  total_duration_ms: number
  total_tokens: TokenUsage
  retries_used: number
  requirements_supported: number
  requirements_needing_review: number
  hallucinated_citations_caught: number
}

export interface ReasoningPathAudit {
  is_consistent: boolean
  node_sequence: string[]
  issues: string[]
}

export interface PipelineResult {
  rfp_id: string
  requirements: Requirement[]
  retrieved: Record<string, RetrievedChunk[]>
  drafts: Record<string, DraftSection>
  verification: Record<string, VerificationResult>
  trace_log: TraceEvent[]
  metrics: PipelineMetrics
  reasoning_path_audit: ReasoningPathAudit
}

/** The backend's standard error shape (CLAUDE.md sec. 5): {"error", "detail"}. */
export interface ApiErrorBody {
  error: string
  detail: string
}
