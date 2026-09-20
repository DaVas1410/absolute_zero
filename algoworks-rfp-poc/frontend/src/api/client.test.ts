import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  checkHealth,
  composeProposal,
  getTrace,
  getTraceabilityReport,
  ingestCorpusDocument,
  processRfp,
  processRfpPdf,
  submitFeedback,
} from './client'

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

describe('processRfpPdf', () => {
  it('posts a multipart body without an explicit Content-Type header', async () => {
    const payload = { rfp_id: 'rfp_1', requirements: [] }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, payload))
    vi.stubGlobal('fetch', fetchMock)

    const file = new File(['contenido'], 'rfp.pdf', { type: 'application/pdf' })
    const result = await processRfpPdf('rfp_1', file)

    expect(result).toEqual(payload)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/rfp/process/pdf')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect(init.headers).toBeUndefined()
    expect((init.body as FormData).get('rfp_id')).toBe('rfp_1')
  })
})

describe('composeProposal', () => {
  it('posts to /rfp/{id}/compose and returns the ProposalDocument', async () => {
    const payload = { rfp_id: 'rfp_1', sections: [] }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, payload)))

    await expect(composeProposal('rfp_1')).resolves.toEqual(payload)
  })

  it('throws ApiError on a 404 (no prior pipeline run)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(404, { error: 'Not Found', detail: 'no hay resultados' })),
    )

    await expect(composeProposal('rfp_1')).rejects.toMatchObject({ status: 404 })
  })
})

describe('getTraceabilityReport', () => {
  it('returns the parsed report on 200', async () => {
    const report = { rfp_id: 'rfp_1', traceability_rate: 0.5 }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, report)))

    await expect(getTraceabilityReport('rfp_1')).resolves.toEqual(report)
  })
})

describe('ingestCorpusDocument', () => {
  it('posts a multipart body with file + section_type, omitting an empty source', async () => {
    const payload = {
      source: 'propuesta.pdf',
      section_type: 'experiencia_previa',
      chunks_added: [],
      chunk_count: 0,
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, payload))
    vi.stubGlobal('fetch', fetchMock)

    const file = new File(['contenido'], 'propuesta.pdf', { type: 'application/pdf' })
    const result = await ingestCorpusDocument(file, 'experiencia_previa')

    expect(result).toEqual(payload)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/corpus/ingest')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    const body = init.body as FormData
    expect(body.get('section_type')).toBe('experiencia_previa')
    expect(body.get('source')).toBeNull()
  })

  it('includes a trimmed source field when provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, { source: 'x', section_type: 'equipo', chunks_added: [], chunk_count: 0 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const file = new File(['contenido'], 'equipo.pdf', { type: 'application/pdf' })
    await ingestCorpusDocument(file, 'equipo', '  Equipo_Algoworks_2026.md  ')

    const body = fetchMock.mock.calls[0][1].body as FormData
    expect(body.get('source')).toBe('Equipo_Algoworks_2026.md')
  })

  it('throws ApiError on a 422 (invalid PDF)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(422, { error: 'Unprocessable Entity', detail: 'El PDF no contiene texto extraíble.' }),
      ),
    )
    const file = new File(['x'], 'vacio.pdf', { type: 'application/pdf' })

    await expect(ingestCorpusDocument(file, 'capacidades_tecnicas')).rejects.toMatchObject({ status: 422 })
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
