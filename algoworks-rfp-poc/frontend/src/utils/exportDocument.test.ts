import { describe, expect, it } from 'vitest'
import type { PipelineResult, ProposalDocument } from '../api/types'
import { buildPipelineResultMarkdown, buildProposalDocumentMarkdown } from './exportDocument'

function minimalResult(overrides: Partial<PipelineResult>): PipelineResult {
  return {
    rfp_id: 'rfp_1',
    requirements: [],
    retrieved: {},
    drafts: {},
    verification: {},
    trace_log: [],
    metrics: {
      total_duration_ms: 0,
      total_tokens: { input_tokens: 0, output_tokens: 0, total_tokens: 0, estimated_cost_usd: 0 },
      retries_used: 0,
      requirements_supported: 0,
      requirements_needing_review: 0,
      hallucinated_citations_caught: 0,
    },
    reasoning_path_audit: { is_consistent: true, node_sequence: [], issues: [] },
    ...overrides,
  }
}

describe('buildPipelineResultMarkdown', () => {
  it('replaces inline [[chunk_id]] markers with their citation number and lists sources', () => {
    const result = minimalResult({
      requirements: [{ req_id: 'req_001', text: 'Experiencia previa', section_target: 'experiencia_previa' }],
      retrieved: {
        req_001: [
          { chunk_id: 'chunk_001', score: 0.9, justification: 'Justificación.', source: 'Propuesta_ClienteX.md', text: 'Texto exacto del chunk.' },
        ],
      },
      drafts: {
        req_001: {
          req_id: 'req_001',
          text: 'Tenemos experiencia [[chunk_001]] comprobada.',
          cited_chunks: ['chunk_001'],
          reasoning: '',
          citation_similarities: [],
          overall_similarity: 0,
        },
      },
      verification: {
        req_001: { req_id: 'req_001', supported: true, issues: [], confidence: 0.95, reasoning: '', retries_used: 0 },
      },
    })

    const markdown = buildPipelineResultMarkdown(result)

    expect(markdown).toContain('# Respuesta RFP: rfp_1')
    expect(markdown).toContain('Tenemos experiencia [1] comprobada.')
    expect(markdown).toContain('Texto exacto del chunk.')
    expect(markdown).toContain('Respaldado')
  })
})

describe('buildProposalDocumentMarkdown', () => {
  it('produces a client-ready copy with no internal QA metadata (no verdict tags, no metrics, no raw chunk ids)', () => {
    const proposal: ProposalDocument = {
      rfp_id: 'rfp_1',
      sections: [
        {
          heading: 'Solución propuesta',
          body: 'Ofrecemos una arquitectura de streaming [[chunk_004]] probada.',
          cited_chunks: ['chunk_004'],
          source_req_ids: ['req_001'],
          citations: [
            { chunk_id: 'chunk_004', text: 'Texto exacto del chunk.', source: 'Capacidades_Tecnicas_Algoworks.md', section_type: 'capacidades_tecnicas' },
          ],
        },
      ],
      verification: [
        { heading: 'Solución propuesta', supported: true, issues: [], confidence: 0.97, reasoning: '', retries_used: 0 },
      ],
      trace_log: [],
      metrics: {
        total_duration_ms: 6600,
        total_tokens: { input_tokens: 0, output_tokens: 0, total_tokens: 4556, estimated_cost_usd: 0.0018 },
        retries_used: 0,
        sections_supported: 1,
        sections_needing_review: 0,
        hallucinated_citations_caught: 0,
        hallucinated_citations_removed: 0,
        fully_cited_count: 1,
        partially_cited_count: 0,
        uncited_count: 0,
        traceability_rate: 0.2,
        partial_rate: 0,
        uncited_rate: 0.8,
      },
    }

    const markdown = buildProposalDocumentMarkdown(proposal)

    expect(markdown).toContain('# Propuesta: rfp_1')
    expect(markdown).toContain('Ofrecemos una arquitectura de streaming [1] probada.')
    expect(markdown).toContain('Texto exacto del chunk.')
    expect(markdown).toContain('Capacidades Tecnicas Algoworks')
    expect(markdown).not.toContain('chunk_004')
    expect(markdown).not.toContain('Veredicto')
    expect(markdown).not.toContain('Tasa de trazabilidad')
    expect(markdown).not.toContain('Tokens')
  })
})
