/** ms >= 1000 renders as seconds ("1.2 s"); below that, whole milliseconds ("850 ms"). */
export function formatDuration(durationMs: number): string {
  if (durationMs >= 1000) {
    return `${(durationMs / 1000).toFixed(1)} s`
  }
  return `${Math.round(durationMs)} ms`
}

export function formatTokens(totalTokens: number): string {
  return totalTokens.toLocaleString('en-US')
}

/**
 * `estimated_cost_usd = 0.0` is documented in schemas.py as meaning
 * "unknown", not "free" - render that distinctly rather than "$0.0000".
 */
export function formatCost(estimatedCostUsd: number): string {
  if (estimatedCostUsd <= 0) {
    return 'costo desconocido'
  }
  return `$${estimatedCostUsd.toFixed(4)}`
}

/** `value` is a 0..1 fraction (a similarity score or verifier confidence). */
export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

/** "Capacidades_Tecnicas_Algoworks.md" -> "Capacidades Tecnicas Algoworks". */
export function formatSourceName(source: string): string {
  if (!source) return 'Fuente sin nombre'
  return source
    .replace(/\.[^./\\]+$/, '')
    .replace(/[_-]+/g, ' ')
    .trim()
}

/**
 * A human-friendly label for a retrieved/cited chunk, e.g. "Capacidades
 * Tecnicas Algoworks — fragmento 6" instead of the raw internal id
 * ("chunk_006"). The raw `chunk_id` is still shown alongside it (as a
 * secondary/caption element) wherever this is used, for traceability.
 */
export function formatChunkLabel(chunkId: string, source: string): string {
  if (!source) return chunkId
  const trailingNumber = chunkId.match(/(\d+)\s*$/)
  const fragment = trailingNumber ? `fragmento ${Number(trailingNumber[1])}` : chunkId
  return `${formatSourceName(source)} — ${fragment}`
}
