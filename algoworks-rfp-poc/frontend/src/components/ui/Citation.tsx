import './Citation.css'

interface CitationProps {
  number: number
  isSelected: boolean
  onClick: () => void
}

/**
 * The inline, numbered marker resolving a `[[chunk_id]]` placeholder to its
 * SourceCard. Numbered by position within that section's own source list.
 * Clicking it opens/highlights the matching source - never a dead-end tooltip.
 */
export function Citation({ number, isSelected, onClick }: CitationProps) {
  return (
    <button
      type="button"
      className={`td-citation ${isSelected ? 'is-selected' : ''}`}
      onClick={onClick}
      aria-label={`Ver fuente ${number}`}
    >
      {number}
    </button>
  )
}
