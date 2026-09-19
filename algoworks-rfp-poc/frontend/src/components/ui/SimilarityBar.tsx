import { formatPercent } from '../../utils/format'
import './SimilarityBar.css'

interface SimilarityBarProps {
  label: string
  value: number
}

/** A small labeled progress bar for one DraftSection.citation_similarities entry. */
export function SimilarityBar({ label, value }: SimilarityBarProps) {
  return (
    <div className="td-similarity-bar">
      <div className="td-similarity-bar__labels text-caption">
        <span>{label}</span>
        <span>{formatPercent(value)}</span>
      </div>
      <div className="td-similarity-bar__track">
        <div className="td-similarity-bar__fill" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  )
}
