import type { ApiErrorBody, PipelineResult, TraceEvent } from './types'

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
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
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
