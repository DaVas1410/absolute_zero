import type {
  ApiErrorBody,
  CorpusIngestResult,
  IngestSectionType,
  PipelineResult,
  ProposalDocument,
  RfpProgress,
  TraceabilityReport,
  TraceEvent,
} from './types'

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  error: string
  detail: string

  constructor(status: number, error: string, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.error = error
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  // FormData bodies (file uploads) must NOT get an explicit Content-Type -
  // the browser sets the multipart boundary itself.
  const isFormData = init?.body instanceof FormData
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: isFormData ? init?.headers : { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch (err) {
    throw new ApiError(0, 'Connection Error', err instanceof Error ? err.message : String(err))
  }

  if (!response.ok) {
    let body: Partial<ApiErrorBody> = {}
    try {
      body = (await response.json()) as Partial<ApiErrorBody>
    } catch {
      // Non-JSON error body - fall through to the generic message below.
    }
    throw new ApiError(
      response.status,
      body.error ?? response.statusText,
      body.detail ?? 'Ha ocurrido un error inesperado.',
    )
  }

  return response.json() as Promise<T>
}

export async function checkHealth(): Promise<boolean> {
  try {
    await request('/health')
    return true
  } catch {
    return false
  }
}

export function processRfp(rfpId: string, rfpText: string): Promise<PipelineResult> {
  return request<PipelineResult>('/rfp/process', {
    method: 'POST',
    body: JSON.stringify({ rfp_id: rfpId, rfp_text: rfpText }),
  })
}

export function getTrace(rfpId: string): Promise<TraceEvent[]> {
  return request<TraceEvent[]>(`/rfp/${encodeURIComponent(rfpId)}/trace`)
}

export function submitFeedback(reqId: string, accepted: boolean): Promise<{ status: string }> {
  return request<{ status: string }>(`/rfp/${encodeURIComponent(reqId)}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ accepted }),
  })
}

export function processRfpPdf(rfpId: string, file: File): Promise<PipelineResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('rfp_id', rfpId)
  return request<PipelineResult>('/rfp/process/pdf', { method: 'POST', body: form })
}

export function startRfpProcess(rfpId: string, rfpText: string): Promise<{ rfp_id: string; status: string }> {
  return request('/rfp/process/start', {
    method: 'POST',
    body: JSON.stringify({ rfp_id: rfpId, rfp_text: rfpText }),
  })
}

export function startRfpProcessPdf(rfpId: string, file: File): Promise<{ rfp_id: string; status: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('rfp_id', rfpId)
  return request('/rfp/process/pdf/start', { method: 'POST', body: form })
}

export function getRfpProgress(rfpId: string): Promise<RfpProgress> {
  return request<RfpProgress>(`/rfp/${encodeURIComponent(rfpId)}/progress`)
}

const PROGRESS_POLL_INTERVAL_MS = 700

/**
 * Starts a background run and polls GET /rfp/{id}/progress until it settles,
 * calling `onUpdate` with the growing trace_log after every poll so the UI
 * can render each node's reasoning as it actually completes on the backend -
 * no simulated timers, no fabricated content.
 */
export async function runRfpPipeline(
  start: () => Promise<{ rfp_id: string; status: string }>,
  rfpId: string,
  onUpdate: (traceLog: TraceEvent[]) => void,
): Promise<PipelineResult> {
  await start()
  for (;;) {
    const snapshot = await getRfpProgress(rfpId)
    onUpdate(snapshot.trace_log)
    if (snapshot.status === 'done' && snapshot.result) return snapshot.result
    if (snapshot.status === 'error') {
      throw new ApiError(500, 'Pipeline Error', snapshot.error ?? 'Ha ocurrido un error inesperado.')
    }
    await new Promise((resolve) => setTimeout(resolve, PROGRESS_POLL_INTERVAL_MS))
  }
}

export function composeProposal(rfpId: string): Promise<ProposalDocument> {
  return request<ProposalDocument>(`/rfp/${encodeURIComponent(rfpId)}/compose`, { method: 'POST' })
}

export function getTraceabilityReport(rfpId: string): Promise<TraceabilityReport> {
  return request<TraceabilityReport>(`/rfp/${encodeURIComponent(rfpId)}/traceability-report`)
}

export function ingestCorpusDocument(
  file: File,
  sectionType: IngestSectionType,
  source?: string,
): Promise<CorpusIngestResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('section_type', sectionType)
  if (source?.trim()) {
    form.append('source', source.trim())
  }
  return request<CorpusIngestResult>('/corpus/ingest', { method: 'POST', body: form })
}
