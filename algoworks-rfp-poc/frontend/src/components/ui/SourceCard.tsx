import { FileText } from 'lucide-react'
import type { RetrievedChunk } from '../../api/types'
import { formatChunkLabel, formatPercent } from '../../utils/format'
import './SourceCard.css'

interface SourceCardProps {
  number: number
  chunk: RetrievedChunk
  isSelected: boolean
  onClick: () => void
}

/**
 * A numbered row for one retrieved chunk. The title is a human-friendly
 * label derived from `source` + the chunk's position (formatChunkLabel) -
 * the raw `chunk_id` is demoted to the byline for traceability without
 * making it the headline.
 */
export function SourceCard({ number, chunk, isSelected, onClick }: SourceCardProps) {
  return (
    <button
      type="button"
      className={`td-source-card ${isSelected ? 'is-selected' : ''}`}
      onClick={onClick}
    >
      <span className="td-source-card__index">{number}</span>
      <FileText className="td-source-card__icon" />
      <span className="td-source-card__body">
        <span className="text-h3 td-source-card__title">{formatChunkLabel(chunk.chunk_id, chunk.source)}</span>
        <span className="text-body-sm td-source-card__context">{chunk.justification}</span>
        <span className="text-caption td-source-card__byline">
          {formatPercent(chunk.score)} relevancia · ID {chunk.chunk_id}
        </span>
      </span>
    </button>
  )
}
