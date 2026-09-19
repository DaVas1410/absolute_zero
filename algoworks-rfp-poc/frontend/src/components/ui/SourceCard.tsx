import { FileText } from 'lucide-react'
import type { RetrievedChunk } from '../../api/types'
import { formatPercent } from '../../utils/format'
import './SourceCard.css'

interface SourceCardProps {
  number: number
  chunk: RetrievedChunk
  isSelected: boolean
  onClick: () => void
}

/**
 * A numbered row for one retrieved chunk. `source` and `score` are real
 * fields on RetrievedChunk; the design doc's illustrative Type/Date/Industry
 * metadata has no backing data and is not shown (see DetailPanel for the
 * same gap handled explicitly with "-").
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
        <span className="text-h3 td-source-card__title">{chunk.chunk_id}</span>
        <span className="text-body-sm td-source-card__context">{chunk.justification}</span>
        <span className="text-caption td-source-card__byline">
          {chunk.source || 'Fuente sin nombre'} · {formatPercent(chunk.score)} relevancia
        </span>
      </span>
    </button>
  )
}
