import { describe, expect, it } from 'vitest'
import { parseCitationMarkers } from './citations'

describe('parseCitationMarkers', () => {
  it('passes a string with no markers through as a single text token', () => {
    expect(parseCitationMarkers('Sin citas aqui.')).toEqual([{ kind: 'text', value: 'Sin citas aqui.' }])
  })

  it('splits multiple markers into alternating text/citation tokens in order', () => {
    const result = parseCitationMarkers('Algoworks tiene experiencia [[chunk_001]] en el sector [[chunk_002]].')

    expect(result).toEqual([
      { kind: 'text', value: 'Algoworks tiene experiencia ' },
      { kind: 'citation', chunkId: 'chunk_001' },
      { kind: 'text', value: ' en el sector ' },
      { kind: 'citation', chunkId: 'chunk_002' },
      { kind: 'text', value: '.' },
    ])
  })

  it('does not swallow trailing punctuation touching a marker', () => {
    const result = parseCitationMarkers('...con respaldo[[chunk_004]].')

    expect(result.at(-1)).toEqual({ kind: 'text', value: '.' })
  })

  it('handles a marker at the very start of the string', () => {
    const result = parseCitationMarkers('[[chunk_001]] al inicio.')

    expect(result[0]).toEqual({ kind: 'citation', chunkId: 'chunk_001' })
  })

  it('returns an empty array for an empty string', () => {
    expect(parseCitationMarkers('')).toEqual([])
  })
})
