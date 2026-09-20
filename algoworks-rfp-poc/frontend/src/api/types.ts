/**
 * TypeScript mirror of backend/api/schemas.py — see docs/CONTRATO_DATOS.md.
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
  /** Exact text of the retrieved chunk. */
  text: string
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

// --- live progress (POST /rfp/process/start + GET /rfp/{id}/progress) ---

export type RfpProgressStatus = 'running' | 'done' | 'error'

export interface RfpProgress {
  rfp_id: string
  status: RfpProgressStatus
  trace_log: TraceEvent[]
  result: PipelineResult | null
  error: string | null
}

// --- corpus ingestion (POST /corpus/ingest) ---

export type IngestSectionType = 'experiencia_previa' | 'capacidades_tecnicas' | 'equipo'

export interface Chunk {
  chunk_id: string
  text: string
  source: string
  section_type: string
  metadata: Record<string, unknown>
}

export interface CorpusIngestResult {
  source: string
  section_type: string
  chunks_added: Chunk[]
  chunk_count: number
}

// --- compose_proposal pipeline (POST /rfp/{id}/compose) ---

export interface ChunkCitation {
  chunk_id: string
  /** Exact text of the cited chunk, resolved from the corpus. */
  text: string
  source: string
  section_type: string
}

export interface ProposalSection {
  heading: string
  /** Contains inline `[[chunk_id]]` markers. */
  body: string
  cited_chunks: string[]
  source_req_ids: string[]
  citations: ChunkCitation[]
}

export interface ProposalSectionVerification {
  heading: string
  supported: boolean
  issues: string[]
  confidence: number
  reasoning: string
  retries_used: number
}

export interface ComposeMetrics {
  total_duration_ms: number
  total_tokens: TokenUsage
  retries_used: number
  sections_supported: number
  sections_needing_review: number
  hallucinated_citations_caught: number
  hallucinated_citations_removed: number
  fully_cited_count: number
  partially_cited_count: number
  uncited_count: number
  traceability_rate: number
  partial_rate: number
  uncited_rate: number
}

export interface ProposalDocument {
  rfp_id: string
  sections: ProposalSection[]
  verification: ProposalSectionVerification[]
  trace_log: TraceEvent[]
  metrics: ComposeMetrics
}

// --- traceability report (GET /rfp/{id}/traceability-report) ---

export interface TraceabilityReport {
  rfp_id: string
  total_responses: number
  fully_cited: number
  partially_cited: number
  uncited: number
  traceability_rate: number
  partial_rate: number
  uncited_rate: number
  verified_count: number
  verification_rate: number
}
