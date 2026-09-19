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
