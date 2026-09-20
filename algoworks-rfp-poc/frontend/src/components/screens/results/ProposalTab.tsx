import { useMemo, useState } from 'react'
import { FileStack, Loader2 } from 'lucide-react'
import type { ProposalDocument, ProposalSection, ProposalSectionVerification } from '../../../api/types'
import { Badge } from '../../ui/Badge'
import { Button } from '../../ui/Button'
import { Callout } from '../../ui/Callout'
import { DraftText } from '../../ui/DraftText'
import { MetricTile } from '../../ui/MetricTile'
import { SegmentedTabs, type TabOption } from '../../ui/SegmentedTabs'
import { VerdictBadge } from '../../ui/VerdictBadge'
import { formatChunkLabel, formatCost, formatDuration, formatPercent, formatSourceName, formatTokens } from '../../../utils/format'
import { buildProposalDocumentMarkdown, downloadTextFile } from '../../../utils/exportDocument'
import './ProposalTab.css'

type ProposalViewMode = 'client' | 'internal'

const VIEW_MODE_TABS: TabOption[] = [
  { id: 'client', label: 'Vista cliente' },
  { id: 'internal', label: 'Vista interna (trazabilidad)' },
]

interface ProposalTabProps {
  proposal: ProposalDocument | null
  isLoading: boolean
  error: string | null
  onRegenerate: () => void
}

interface ProposalSectionCardProps {
  section: ProposalSection
  verification: ProposalSectionVerification | undefined
  viewMode: ProposalViewMode
  selectedChunkId: string | null
  onSelectChunk: (chunkId: string) => void
}

function ProposalSectionCard({ section, verification, viewMode, selectedChunkId, onSelectChunk }: ProposalSectionCardProps) {
  const numbers = useMemo(
    () => new Map(section.citations.map((citation, index) => [citation.chunk_id, index + 1])),
    [section.citations],
  )
  const isInternal = viewMode === 'internal'

  return (
    <div className="td-req-card td-req-card--divider">
      <div className="td-req-card__head">
        <h2 className="text-h2">{section.heading}</h2>
        {isInternal &&
          verification &&
          (section.citations.length > 0 ? (
            <VerdictBadge supported={verification.supported} confidence={verification.confidence} />
          ) : (
            <Badge tone="neutral">Declaración de valor · sin cita</Badge>
          ))}
      </div>

      <DraftText
        text={section.body}
        citationNumbers={numbers}
        selectedChunkId={selectedChunkId}
        onSelectChunk={onSelectChunk}
      />

      {isInternal && verification && !verification.supported && verification.issues.length > 0 && (
        <div className="td-req-card__verdict">
          <p className="text-body-sm">{verification.reasoning}</p>
          <ul className="td-req-card__issues">
            {verification.issues.map((issue) => (
              <li key={issue} className="text-body-sm">
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {section.citations.length > 0 && (
        <div className="td-proposal-tab__citations">
          <p className="text-h3 td-proposal-tab__citations-title">Fuentes citadas</p>
          {section.citations.map((citation, index) => (
            <button
              key={citation.chunk_id}
              type="button"
              className={`td-source-card ${selectedChunkId === citation.chunk_id ? 'is-selected' : ''}`}
              onClick={() => onSelectChunk(citation.chunk_id)}
            >
              <span className="td-source-card__index">{index + 1}</span>
              <span className="td-source-card__body">
                <span className="text-h3 td-source-card__title">
                  {isInternal ? formatChunkLabel(citation.chunk_id, citation.source) : formatSourceName(citation.source)}
                </span>
                <span className="text-body-sm td-source-card__context">{citation.text}</span>
                {isInternal && <span className="text-caption td-source-card__byline">ID {citation.chunk_id}</span>}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function ProposalCover({ proposal, showSeal }: { proposal: ProposalDocument; showSeal: boolean }) {
  const generatedAt = proposal.trace_log.at(-1)?.timestamp
  const verified = proposal.metrics.sections_supported
  const tracked = proposal.metrics.sections_supported + proposal.metrics.sections_needing_review
  const isFullyVerified = tracked > 0 && verified === tracked

  return (
    <div className="td-proposal-tab__cover">
      <div className="td-proposal-tab__cover-text">
        <h1 className="text-display">Propuesta consolidada — {proposal.rfp_id}</h1>
        {generatedAt && (
          <p className="text-body-sm td-proposal-tab__cover-date">
            Generado el <span className="text-mono">{new Date(generatedAt).toLocaleString()}</span>
          </p>
        )}
      </div>
      {showSeal && tracked > 0 && (
        <div className={`td-proposal-tab__seal ${isFullyVerified ? 'is-verified' : 'is-partial'}`}>
          <span className="text-mono td-proposal-tab__seal-count">
            {verified}/{tracked}
          </span>
          <span className="td-proposal-tab__seal-label">verificado</span>
        </div>
      )}
    </div>
  )
}

function ProposalMetrics({ metrics }: { metrics: ProposalDocument['metrics'] }) {
  return (
    <div className="td-results__metrics">
      <MetricTile label="Duración" value={formatDuration(metrics.total_duration_ms)} />
      <MetricTile label="Tokens totales" value={formatTokens(metrics.total_tokens.total_tokens)} />
      <MetricTile label="Costo estimado" value={formatCost(metrics.total_tokens.estimated_cost_usd)} />
      <MetricTile label="Tasa de trazabilidad" value={formatPercent(metrics.traceability_rate)} />
      <MetricTile label="Citas alucinadas eliminadas" value={String(metrics.hallucinated_citations_removed)} />
    </div>
  )
}

/**
 * The consolidated proposal is now drafted automatically right after the
 * base response (see App.tsx's composeInBackground) - this component is a
 * pure view over that state plus a "Regenerar" escape hatch, it never
 * triggers the first draft itself.
 */
export function ProposalTab({ proposal, isLoading, error, onRegenerate }: ProposalTabProps) {
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ProposalViewMode>('client')

  if (!proposal) {
    if (isLoading) {
      return (
        <div className="td-proposal-tab__empty">
          <Callout icon={<Loader2 className="td-proposal-tab__spinner" />} title="Componiendo la propuesta consolidada…">
            Reorganizando los requisitos, citas y evidencia ya generados en un documento único por
            secciones - sin volver a recuperar ni inventar citas nuevas. Puede tardar un momento.
          </Callout>
        </div>
      )
    }
    return (
      <div className="td-proposal-tab__empty">
        <Callout icon={<FileStack />} title="No se pudo componer la propuesta">
          {error ?? 'Ocurrió un problema inesperado al generar el documento de propuesta.'}
        </Callout>
        <Button onClick={onRegenerate}>Reintentar</Button>
      </div>
    )
  }

  return (
    <div className="td-proposal-tab">
      <ProposalCover proposal={proposal} showSeal={viewMode === 'internal'} />

      <div className="td-proposal-tab__toolbar">
        <SegmentedTabs options={VIEW_MODE_TABS} activeId={viewMode} onChange={(id) => setViewMode(id as ProposalViewMode)} />
        <Button
          weight="secondary"
          onClick={() => downloadTextFile(`propuesta_${proposal.rfp_id}.md`, buildProposalDocumentMarkdown(proposal))}
        >
          Descargar propuesta
        </Button>
        <Button weight="ghost" onClick={onRegenerate} disabled={isLoading}>
          {isLoading ? 'Regenerando…' : 'Regenerar'}
        </Button>
      </div>

      {error && (
        <Badge tone="caution">No se pudo regenerar: {error} (se sigue mostrando la última versión generada)</Badge>
      )}

      {viewMode === 'internal' && (
        <>
          <ProposalMetrics metrics={proposal.metrics} />
          <p className="text-caption td-proposal-tab__internal-note">
            Esta vista muestra metadata interna de trazabilidad (costo, tokens, IDs de fragmento,
            veredictos de verificación) para auditar cómo se generó el documento — no está pensada
            para enviarse al cliente. Usa "Vista cliente" para la copia final.
          </p>
        </>
      )}

      <div className="td-response-tab__main td-proposal-tab__sections">
        {proposal.sections.map((section) => (
          <ProposalSectionCard
            key={section.heading}
            section={section}
            verification={proposal.verification.find((v) => v.heading === section.heading)}
            viewMode={viewMode}
            selectedChunkId={selectedChunkId}
            onSelectChunk={setSelectedChunkId}
          />
        ))}
      </div>
    </div>
  )
}
