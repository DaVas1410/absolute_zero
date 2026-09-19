import { useState } from 'react'
import { SourceCard } from '../../ui/SourceCard'
import type { SourceIndexEntry } from '../../../utils/sourceIndex'
import './SourcesTab.css'

interface SourcesTabProps {
  sourceIndex: SourceIndexEntry[]
  selectedChunkId: string | null
  onSelectChunk: (chunkId: string) => void
}

/** Every unique chunk_id retrieved anywhere in the run, cited or not. */
export function SourcesTab({ sourceIndex, selectedChunkId, onSelectChunk }: SourcesTabProps) {
  const [search, setSearch] = useState('')
  const visible = search.trim()
    ? sourceIndex.filter(
        (entry) =>
          entry.chunkId.toLowerCase().includes(search.toLowerCase()) ||
          entry.chunk.justification.toLowerCase().includes(search.toLowerCase()),
      )
    : sourceIndex

  return (
    <div className="td-sources-tab">
      {sourceIndex.length > 6 && (
        <input
          type="search"
          className="td-sources-tab__search"
          placeholder="Buscar fuente..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      )}
      {visible.map((entry) => (
        <div key={entry.chunkId} className="td-sources-tab__row">
          <SourceCard
            number={entry.number}
            chunk={entry.chunk}
            isSelected={selectedChunkId === entry.chunkId}
            onClick={() => onSelectChunk(entry.chunkId)}
          />
          <p className="text-caption td-sources-tab__citing">
            {entry.citingReqIds.length > 0
              ? `Citado en: ${entry.citingReqIds.join(', ')}`
              : 'Recuperado, no citado en ningún borrador'}
          </p>
        </div>
      ))}
    </div>
  )
}
