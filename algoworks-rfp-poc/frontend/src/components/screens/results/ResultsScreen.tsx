import { useMemo, useState } from 'react'
import type { PipelineResult } from '../../../api/types'
import { Badge } from '../../ui/Badge'
import { Button } from '../../ui/Button'
import { ConsistencyBanner } from '../../ui/ConsistencyBanner'
import { DetailPanel } from '../../ui/DetailPanel'
import { MetricTile } from '../../ui/MetricTile'
import { UnderlineTabs } from '../../ui/UnderlineTabs'
import type { TabOption } from '../../ui/SegmentedTabs'
import { TopBar } from '../../layout/TopBar'
import { formatCost, formatDuration, formatTokens } from '../../../utils/format'
import { buildSourceIndex } from '../../../utils/sourceIndex'
import { ResponseTab } from './ResponseTab'
import { SourcesTab } from './SourcesTab'
import { RequirementsTab } from './RequirementsTab'
import { TraceLogTab } from './TraceLogTab'
import './ResultsScreen.css'

interface ResultsScreenProps {
  result: PipelineResult
}

export function ResultsScreen({ result }: ResultsScreenProps) {
  const [activeTab, setActiveTab] = useState('response')
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)

  const sourceIndex = useMemo(() => buildSourceIndex(result), [result])

  const tabs: TabOption[] = [
    { id: 'response', label: 'Response' },
    { id: 'sources', label: `Sources (${sourceIndex.length})` },
    { id: 'requirements', label: 'Key Requirements' },
    { id: 'trace', label: 'Trace Log' },
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
        title={`RFP Response: ${result.rfp_id}`}
        meta={meta}
        right={
          <>
            <Badge tone="success">Completed</Badge>
            <Button weight="secondary" disabled title="No hay endpoint de exportación en la API">
              Download
            </Button>
            <Button weight="primary" disabled title="No hay endpoint de compartir en la API">
              Share
            </Button>
          </>
        }
      />

      <div className="td-results__metrics">
        <MetricTile label="Duration" value={formatDuration(result.metrics.total_duration_ms)} />
        <MetricTile label="Total tokens" value={formatTokens(result.metrics.total_tokens.total_tokens)} />
        <MetricTile label="Estimated cost" value={formatCost(result.metrics.total_tokens.estimated_cost_usd)} />
        <MetricTile label="Retries used" value={String(result.metrics.retries_used)} />
        <MetricTile
          label="Hallucinated citations caught"
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
