import { describe, expect, it } from 'vitest'
import type { PipelineResult } from '../api/types'
import { buildSourceIndex, citationNumberMap } from './sourceIndex'

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

describe('buildSourceIndex', () => {
  it('numbers chunks by first appearance across requirements, deduplicated', () => {
    const result = minimalResult({
      requirements: [
        { req_id: 'req_001', text: 'a', section_target: 'experiencia_previa' },
        { req_id: 'req_002', text: 'b', section_target: 'capacidades_tecnicas' },
      ],
      retrieved: {
        req_001: [
          { chunk_id: 'chunk_002', score: 0.7, justification: 'j2', source: 's2', text: 't2' },
          { chunk_id: 'chunk_001', score: 0.9, justification: 'j1', source: 's1', text: 't1' },
        ],
        // chunk_001 reappears for req_002 - must not get a second number.
        req_002: [{ chunk_id: 'chunk_001', score: 0.5, justification: 'j1-b', source: 's1', text: 't1' }],
      },
      drafts: {
        req_001: { req_id: 'req_001', text: '', cited_chunks: ['chunk_002'], reasoning: '', citation_similarities: [], overall_similarity: 0 },
        req_002: { req_id: 'req_002', text: '', cited_chunks: ['chunk_001'], reasoning: '', citation_similarities: [], overall_similarity: 0 },
      },
    })

    const entries = buildSourceIndex(result)

    expect(entries.map((e) => e.chunkId)).toEqual(['chunk_002', 'chunk_001'])
    expect(entries.map((e) => e.number)).toEqual([1, 2])
  })

  it('tracks every req_id that cites a chunk', () => {
    const result = minimalResult({
      requirements: [
        { req_id: 'req_001', text: 'a', section_target: 'experiencia_previa' },
        { req_id: 'req_002', text: 'b', section_target: 'capacidades_tecnicas' },
      ],
      retrieved: {
        req_001: [{ chunk_id: 'chunk_001', score: 0.9, justification: 'j1', source: 's1', text: 't1' }],
        req_002: [{ chunk_id: 'chunk_001', score: 0.5, justification: 'j1', source: 's1', text: 't1' }],
      },
      drafts: {
        req_001: { req_id: 'req_001', text: '', cited_chunks: ['chunk_001'], reasoning: '', citation_similarities: [], overall_similarity: 0 },
        req_002: { req_id: 'req_002', text: '', cited_chunks: ['chunk_001'], reasoning: '', citation_similarities: [], overall_similarity: 0 },
      },
    })

    const entries = buildSourceIndex(result)

    expect(entries).toHaveLength(1)
    expect(entries[0].citingReqIds).toEqual(['req_001', 'req_002'])
  })

  it('includes retrieved-but-never-cited chunks with an empty citingReqIds', () => {
    const result = minimalResult({
      requirements: [{ req_id: 'req_001', text: 'a', section_target: 'experiencia_previa' }],
      retrieved: {
        req_001: [{ chunk_id: 'chunk_001', score: 0.9, justification: 'j1', source: 's1', text: 't1' }],
      },
      drafts: {
        req_001: { req_id: 'req_001', text: '', cited_chunks: [], reasoning: '', citation_similarities: [], overall_similarity: 0 },
      },
    })

    const entries = buildSourceIndex(result)

    expect(entries[0].citingReqIds).toEqual([])
  })
})

describe('citationNumberMap', () => {
  it('maps chunk_id to its stable number', () => {
    const entries = buildSourceIndex(
      minimalResult({
        requirements: [{ req_id: 'req_001', text: 'a', section_target: 'experiencia_previa' }],
        retrieved: {
          req_001: [{ chunk_id: 'chunk_001', score: 0.9, justification: 'j1', source: 's1', text: 't1' }],
        },
      }),
    )

    expect(citationNumberMap(entries)).toEqual(new Map([['chunk_001', 1]]))
  })
})
