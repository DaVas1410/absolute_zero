import type { PipelineResult, ProposalDocument } from '../api/types'
import { parseCitationMarkers } from './citations'
import { formatChunkLabel, formatCost, formatDuration, formatPercent, formatSourceName, formatTokens } from './format'
import { buildSourceIndex, citationNumberMap } from './sourceIndex'

/** Replaces inline `[[chunk_id]]` markers with their plain-text "[N]" citation number. */
function renderDraftAsPlainText(text: string, numbers: Map<string, number>): string {
  return parseCitationMarkers(text)
    .map((token) => (token.kind === 'text' ? token.value : `[${numbers.get(token.chunkId) ?? token.chunkId}]`))
    .join('')
}

/**
 * There is no export endpoint in the API (see docs/CONTRATO_DATOS.md) - this
 * builds a self-contained Markdown document client-side from data the UI
 * already has, so "Download" produces the same requirements/citations/
 * verdicts the screen shows, not a fabricated summary.
 */
export function buildPipelineResultMarkdown(result: PipelineResult): string {
  const sourceIndex = buildSourceIndex(result)
  const numbers = citationNumberMap(sourceIndex)
  const lines: string[] = []

  lines.push(`# Respuesta RFP: ${result.rfp_id}`, '', `Generado el ${new Date().toLocaleString()}`, '')

  lines.push(
    '## Métricas',
    '',
    `- Duración: ${formatDuration(result.metrics.total_duration_ms)}`,
    `- Tokens totales: ${formatTokens(result.metrics.total_tokens.total_tokens)}`,
    `- Costo estimado: ${formatCost(result.metrics.total_tokens.estimated_cost_usd)}`,
    `- Reintentos usados: ${result.metrics.retries_used}`,
    `- Citas alucinadas detectadas: ${result.metrics.hallucinated_citations_caught}`,
    '',
  )

  lines.push('## Respuesta', '')
  for (const requirement of result.requirements) {
    const draft = result.drafts[requirement.req_id]
    const verification = result.verification[requirement.req_id]
    lines.push(`### ${requirement.text}`, '')
    lines.push(draft ? renderDraftAsPlainText(draft.text, numbers) : '_Sin borrador para este requisito._', '')
    if (verification) {
      lines.push(
        `_Veredicto: ${verification.supported ? 'Respaldado' : 'Necesita revisión'} · ${formatPercent(verification.confidence)}_`,
        '',
      )
    }
  }

  lines.push('## Fuentes', '')
  for (const entry of sourceIndex) {
    lines.push(
      `${entry.number}. **${formatChunkLabel(entry.chunkId, entry.chunk.source)}** (ID: ${entry.chunkId}) — ${formatPercent(entry.chunk.score)} relevancia`,
      `   > ${entry.chunk.text || entry.chunk.justification}`,
      '',
    )
  }

  return lines.join('\n')
}

export function buildProposalDocumentMarkdown(proposal: ProposalDocument): string {
  // This is the document handed to the client - internal QA metadata (cost,
  // tokens, chunk ids, per-section verdict tags) belongs in the on-screen
  // "Vista interna" only, never in the exported file.
  const lines: string[] = []
  lines.push(`# Propuesta: ${proposal.rfp_id}`, '', `${new Date().toLocaleDateString()}`, '')

  for (const section of proposal.sections) {
    const numbers = new Map(section.citations.map((citation, index) => [citation.chunk_id, index + 1]))
    lines.push(`## ${section.heading}`, '')
    lines.push(renderDraftAsPlainText(section.body, numbers), '')
    if (section.citations.length > 0) {
      lines.push('**Fuentes:**', '')
      section.citations.forEach((citation, index) => {
        lines.push(`${index + 1}. **${formatSourceName(citation.source)}**`)
        lines.push(`   > ${citation.text}`, '')
      })
    }
  }

  return lines.join('\n')
}

/** Triggers a browser download of `content` as a file named `filename`. */
export function downloadTextFile(filename: string, content: string, mimeType = 'text/markdown'): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}
