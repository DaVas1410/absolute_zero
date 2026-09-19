import { useMemo, useState } from 'react'
import type { PipelineResult } from '../../../api/types'
import { SourceCard } from '../../ui/SourceCard'
import type { SourceIndexEntry } from '../../../utils/sourceIndex'
import { citationNumberMap } from '../../../utils/sourceIndex'
import { RequirementCard } from './RequirementCard'
import './ResponseTab.css'

interface ResponseTabProps {
  result: PipelineResult
  sourceIndex: SourceIndexEntry[]
  selectedChunkId: string | null
  onSelectChunk: (chunkId: string) => void
}

export function ResponseTab({ result, sourceIndex, selectedChunkId, onSelectChunk }: ResponseTabProps) {
  const [search, setSearch] = useState('')
  const numbers = useMemo(() => citationNumberMap(sourceIndex), [sourceIndex])
  const citedEntries = sourceIndex.filter((entry) => entry.citingReqIds.length > 0)
  const visibleEntries = search.trim()
    ? citedEntries.filter(
        (entry) =>
          entry.chunkId.toLowerCase().includes(search.toLowerCase()) ||
          entry.chunk.justification.toLowerCase().includes(search.toLowerCase()),
      )
    : citedEntries

  return (
    <div className="td-response-tab">
      <div className="td-response-tab__main">
        {result.requirements.map((requirement, index) => (
          <RequirementCard
            key={requirement.req_id}
            requirement={requirement}
            draft={result.drafts[requirement.req_id]}
            verification={result.verification[requirement.req_id]}
            citationNumbers={numbers}
            selectedChunkId={selectedChunkId}
            onSelectChunk={onSelectChunk}
            isLast={index === result.requirements.length - 1}
          />
        ))}
      </div>

      <div className="td-response-tab__sources">
        <p className="text-h3 td-response-tab__sources-title">Sources ({citedEntries.length})</p>
        {citedEntries.length > 6 && (
          <input
            type="search"
            className="td-response-tab__search"
            placeholder="Buscar fuente..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        )}
        {visibleEntries.map((entry) => (
          <SourceCard
            key={entry.chunkId}
            number={entry.number}
            chunk={entry.chunk}
            isSelected={selectedChunkId === entry.chunkId}
            onClick={() => onSelectChunk(entry.chunkId)}
          />
        ))}
      </div>
    </div>
  )
}
