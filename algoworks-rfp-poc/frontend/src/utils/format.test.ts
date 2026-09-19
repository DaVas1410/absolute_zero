import { describe, expect, it } from 'vitest'
import { formatChunkLabel, formatCost, formatDuration, formatPercent, formatSourceName, formatTokens } from './format'

describe('formatDuration', () => {
  it('renders sub-second durations in whole milliseconds', () => {
    expect(formatDuration(850)).toBe('850 ms')
  })

  it('renders exactly 1000ms in seconds, not milliseconds', () => {
    expect(formatDuration(1000)).toBe('1.0 s')
  })

  it('renders multi-second durations with one decimal', () => {
    expect(formatDuration(12345)).toBe('12.3 s')
  })
})

describe('formatTokens', () => {
  it('adds thousands separators', () => {
    expect(formatTokens(1234)).toBe('1,234')
  })

  it('renders zero as-is', () => {
    expect(formatTokens(0)).toBe('0')
  })
})

describe('formatCost', () => {
  it('treats 0.0 as "unknown", not "free", per the schema docstring', () => {
    expect(formatCost(0)).toBe('costo desconocido')
  })

  it('formats a positive cost with 4 decimals', () => {
    expect(formatCost(0.0123)).toBe('$0.0123')
  })
})

describe('formatPercent', () => {
  it('converts a 0..1 fraction to a rounded percentage', () => {
    expect(formatPercent(0.873)).toBe('87%')
  })

  it('rounds up at the boundary', () => {
    expect(formatPercent(0.995)).toBe('100%')
  })
})

describe('formatSourceName', () => {
  it('strips the extension and replaces underscores/hyphens with spaces', () => {
    expect(formatSourceName('Capacidades_Tecnicas_Algoworks.md')).toBe('Capacidades Tecnicas Algoworks')
  })

  it('falls back to a placeholder for an empty source', () => {
    expect(formatSourceName('')).toBe('Fuente sin nombre')
  })
})

describe('formatChunkLabel', () => {
  it('combines the source name with a "fragmento N" suffix from the trailing chunk_id number', () => {
    expect(formatChunkLabel('chunk_006', 'Capacidades_Tecnicas_Algoworks.md')).toBe(
      'Capacidades Tecnicas Algoworks — fragmento 6',
    )
  })

  it('falls back to the raw chunk_id when there is no source', () => {
    expect(formatChunkLabel('chunk_006', '')).toBe('chunk_006')
  })
})
