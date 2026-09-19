import { useMemo, useState } from 'react'
import type { PipelineResult, ProposalDocument } from '../../../api/types'
import { Badge } from '../../ui/Badge'
import { Button } from '../../ui/Button'
import { ConsistencyBanner } from '../../ui/ConsistencyBanner'
import { DetailPanel } from '../../ui/DetailPanel'
import { MetricTile } from '../../ui/MetricTile'
import { UnderlineTabs } from '../../ui/UnderlineTabs'
import type { TabOption } from '../../ui/SegmentedTabs'
import { TopBar } from '../../layout/TopBar'
import { formatCost, formatDuration, formatTokens } from '../../../utils/format'
import { buildPipelineResultMarkdown, downloadTextFile } from '../../../utils/exportDocument'
import { buildSourceIndex } from '../../../utils/sourceIndex'
import { ResponseTab } from './ResponseTab'
import { SourcesTab } from './SourcesTab'
import { RequirementsTab } from './RequirementsTab'
import { TraceLogTab } from './TraceLogTab'
import { ProposalTab } from './ProposalTab'
import './ResultsScreen.css'

interface ResultsScreenProps {
  result: PipelineResult
  proposal: ProposalDocument | null
  isComposingProposal: boolean
  proposalError: string | null
  onRegenerateProposal: () => void
}

export function ResultsScreen({
  result,
  proposal,
  isComposingProposal,
  proposalError,
  onRegenerateProposal,
}: ResultsScreenProps) {
  const [activeTab, setActiveTab] = useState('response')
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)

  const sourceIndex = useMemo(() => buildSourceIndex(result), [result])

  const tabs: TabOption[] = [
    { id: 'response', label: 'Respuesta' },
    { id: 'sources', label: `Fuentes (${sourceIndex.length})` },
    { id: 'requirements', label: 'Requisitos clave' },
    { id: 'proposal', label: isComposingProposal ? 'Propuesta consolidada (generando…)' : 'Propuesta consolidada' },
    { id: 'trace', label: 'Registro de trazabilidad' },
  ]

  const lastEvent = result.trace_log.at(-1)
  const meta = lastEvent
    ? `Generado el ${new Date(lastEvent.timestamp).toLocaleString()} · Basado en ${sourceIndex.length} fuente(s)`
    : `Basado en ${sourceIndex.length} fuente(s)`

  const selectedEntry = selectedChunkId ? sourceIndex.find((entry) => entry.chunkId === selectedChunkId) : undefined
  const selectedSimilarity = selectedChunkId
    ? Object.values(result.drafts)
        .flatMap((draft) => draft.citation_similarities)
        .find((sim) => sim.chunk_id === selectedChunkId)?.similarity ?? null
    : null

  return (
    <div className="td-results">
      <TopBar
        title={`Respuesta RFP: ${result.rfp_id}`}
        meta={meta}
        right={
          <>
            <Badge tone="success">Completado</Badge>
            <Button
              weight="secondary"
              onClick={() => downloadTextFile(`${result.rfp_id}.md`, buildPipelineResultMarkdown(result))}
            >
              Descargar
            </Button>
            <Button weight="primary" disabled title="No hay endpoint de compartir en la API">
              Compartir
            </Button>
          </>
        }
      />

      <div className="td-results__metrics">
        <MetricTile label="Duración" value={formatDuration(result.metrics.total_duration_ms)} />
        <MetricTile label="Tokens totales" value={formatTokens(result.metrics.total_tokens.total_tokens)} />
        <MetricTile label="Costo estimado" value={formatCost(result.metrics.total_tokens.estimated_cost_usd)} />
        <MetricTile label="Reintentos usados" value={String(result.metrics.retries_used)} />
        <MetricTile
          label="Citas alucinadas detectadas"
          value={String(result.metrics.hallucinated_citations_caught)}
        />
      </div>

      <div className="td-results__banner">
        <ConsistencyBanner audit={result.reasoning_path_audit} />
      </div>

      <div className="td-results__tabs">
        <UnderlineTabs options={tabs} activeId={activeTab} onChange={setActiveTab} />
      </div>

      <div className="td-results__tab-content">
        {activeTab === 'response' && (
          <ResponseTab
            result={result}
            sourceIndex={sourceIndex}
            selectedChunkId={selectedChunkId}
            onSelectChunk={setSelectedChunkId}
          />
        )}
        {activeTab === 'sources' && (
          <SourcesTab sourceIndex={sourceIndex} selectedChunkId={selectedChunkId} onSelectChunk={setSelectedChunkId} />
        )}
        {activeTab === 'requirements' && <RequirementsTab result={result} />}
        {activeTab === 'proposal' && (
          <ProposalTab
            proposal={proposal}
            isLoading={isComposingProposal}
            error={proposalError}
            onRegenerate={onRegenerateProposal}
          />
        )}
        {activeTab === 'trace' && <TraceLogTab rfpId={result.rfp_id} traceLog={result.trace_log} />}
      </div>

      {selectedEntry && (
        <DetailPanel
          chunk={selectedEntry.chunk}
          citationSimilarity={selectedSimilarity}
          isCited={selectedEntry.citingReqIds.length > 0}
          onClose={() => setSelectedChunkId(null)}
        />
      )}
    </div>
  )
}
