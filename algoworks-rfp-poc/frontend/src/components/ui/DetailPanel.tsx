import { X } from 'lucide-react'
import { useEffect } from 'react'
import type { RetrievedChunk } from '../../api/types'
import { formatChunkLabel, formatPercent } from '../../utils/format'
import './DetailPanel.css'

interface DetailPanelProps {
  chunk: RetrievedChunk
  citationSimilarity: number | null
  isCited: boolean
  onClose: () => void
}

/** The drawer a citation or SourceCard opens. Fixed field order per the design doc. */
export function DetailPanel({ chunk, citationSimilarity, isCited, onClose }: DetailPanelProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <>
      <div className="td-detail-panel__scrim" onClick={onClose} />
      <aside className="td-detail-panel" role="dialog" aria-modal="true" aria-label="Detalle de la fuente">
        <header className="td-detail-panel__header">
          <h2 className="text-h1 td-detail-panel__title">{formatChunkLabel(chunk.chunk_id, chunk.source)}</h2>
          <button type="button" className="td-detail-panel__close" onClick={onClose} aria-label="Cerrar">
            <X />
          </button>
        </header>

        <section className="td-detail-panel__section">
          <p className="td-detail-panel__label">Fuente</p>
          <p className="text-body">
            {chunk.source || '—'}{' '}
            <span className="text-caption text-mono">(ID: {chunk.chunk_id})</span>
          </p>
        </section>

        <section className="td-detail-panel__section">
          <p className="td-detail-panel__label">Extracto citado</p>
          <div className="td-detail-panel__excerpt text-doc-quote">{chunk.text || '— (sin texto disponible)'}</div>
        </section>

        <section className="td-detail-panel__section">
          <p className="td-detail-panel__label">Por qué se recuperó</p>
          <p className="text-body-sm">{chunk.justification}</p>
        </section>

        <footer className="td-detail-panel__tags">
          <span className="td-detail-panel__tag">{formatPercent(chunk.score)} relevancia</span>
          {citationSimilarity !== null && (
            <span className="td-detail-panel__tag">{formatPercent(citationSimilarity)} similitud con el borrador</span>
          )}
          <span className="td-detail-panel__tag">{isCited ? 'Citado en el borrador' : 'No citado'}</span>
        </footer>
      </aside>
    </>
  )
}
