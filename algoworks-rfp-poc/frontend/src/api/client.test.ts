import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, checkHealth, getTrace, processRfp, submitFeedback } from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('processRfp', () => {
  it('returns the parsed PipelineResult on 200', async () => {
    const payload = { rfp_id: 'rfp_1', requirements: [] }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, payload))
    vi.stubGlobal('fetch', fetchMock)

    const result = await processRfp('rfp_1', 'texto del RFP')

    expect(result).toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/rfp/process',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ rfp_id: 'rfp_1', rfp_text: 'texto del RFP' }),
      }),
    )
  })

  it('throws ApiError with the standard {error, detail} shape on a 422', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(422, { error: 'Unprocessable Entity', detail: 'campo requerido faltante' }),
      ),
    )

    await expect(processRfp('rfp_1', '')).rejects.toMatchObject({
      status: 422,
      error: 'Unprocessable Entity',
      detail: 'campo requerido faltante',
    })
  })
})

describe('getTrace', () => {
  it('returns the parsed trace log on 200', async () => {
    const trace = [{ node: 'extract_requirements' }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, trace)))

    await expect(getTrace('rfp_1')).resolves.toEqual(trace)
  })

  it('throws ApiError on a 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(404, { error: 'Not Found', detail: "No hay trace disponible para rfp_id='rfp_1'." }),
      ),
    )

    await expect(getTrace('rfp_1')).rejects.toBeInstanceOf(ApiError)
    await expect(getTrace('rfp_1')).rejects.toMatchObject({ status: 404 })
  })
})

describe('submitFeedback', () => {
  it('returns the parsed status on 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, { status: 'received' })))

    await expect(submitFeedback('req_001', true)).resolves.toEqual({ status: 'received' })
  })

  it('throws ApiError on a 500', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(500, { error: 'Internal Server Error', detail: 'Ha ocurrido un error inesperado.' }),
      ),
    )

    await expect(submitFeedback('req_001', true)).rejects.toMatchObject({ status: 500 })
  })
})

describe('checkHealth', () => {
  it('returns true when the backend responds 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, { status: 'ok' })))

    await expect(checkHealth()).resolves.toBe(true)
  })

  it('returns false on a network error instead of throwing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(checkHealth()).resolves.toBe(false)
  })

  it('returns false on a non-2xx response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(500, { error: 'x', detail: 'y' })))

    await expect(checkHealth()).resolves.toBe(false)
  })
})
