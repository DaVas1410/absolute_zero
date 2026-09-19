const CITATION_PATTERN = /\[\[([^[\]]+)]]/g

export type DraftToken = { kind: 'text'; value: string } | { kind: 'citation'; chunkId: string }

/**
 * Splits draft text on inline `[[chunk_id]]` markers into an ordered list of
 * plain-text and citation tokens, so callers can render each citation as its
 * own component instead of raw bracket syntax.
 */
export function parseCitationMarkers(text: string): DraftToken[] {
  const tokens: DraftToken[] = []
  let lastIndex = 0

  for (const match of text.matchAll(CITATION_PATTERN)) {
    const matchIndex = match.index
    if (matchIndex > lastIndex) {
      tokens.push({ kind: 'text', value: text.slice(lastIndex, matchIndex) })
    }
    tokens.push({ kind: 'citation', chunkId: match[1] })
    lastIndex = matchIndex + match[0].length
  }

  if (lastIndex < text.length) {
    tokens.push({ kind: 'text', value: text.slice(lastIndex) })
  }

  return tokens
}
