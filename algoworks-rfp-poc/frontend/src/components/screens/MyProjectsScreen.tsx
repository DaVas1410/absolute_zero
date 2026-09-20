import { useRef, useState } from 'react'
import { FileStack, FolderKanban, Loader2, UploadCloud } from 'lucide-react'
import { ApiError, ingestCorpusDocument } from '../../api/client'
import type { CorpusIngestResult, IngestSectionType } from '../../api/types'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Callout } from '../ui/Callout'
import './MyProjectsScreen.css'

const SECTION_TYPE_OPTIONS: { id: IngestSectionType; label: string }[] = [
  { id: 'experiencia_previa', label: 'Experiencia previa' },
  { id: 'capacidades_tecnicas', label: 'Capacidades técnicas' },
  { id: 'equipo', label: 'Equipo' },
]

function sectionTypeLabel(id: string): string {
  return SECTION_TYPE_OPTIONS.find((option) => option.id === id)?.label ?? id
}

interface IngestLogEntry extends CorpusIngestResult {
  id: string
}

/**
 * The corpus-ingest admin screen behind the sidebar's "Mis proyectos" item -
 * upload a past proposal as a PDF, it's chunked and embedded server-side via
 * POST /corpus/ingest, and becomes citable immediately for new RFP runs. No
 * GET endpoint lists what's already in the corpus, so the log below is only
 * this session's activity, not the full corpus - the copy says so plainly.
 */
export function MyProjectsScreen() {
  const [file, setFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [sectionType, setSectionType] = useState<IngestSectionType>('experiencia_previa')
  const [source, setSource] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [log, setLog] = useState<IngestLogEntry[]>([])

  async function handleSubmit() {
    if (!file) return
    setIsSubmitting(true)
    setError(null)
    try {
      const result = await ingestCorpusDocument(file, sectionType, source)
      setLog((current) => [{ ...result, id: `${result.source}-${Date.now()}` }, ...current])
      setFile(null)
      setSource('')
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudo agregar el documento al corpus.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="td-my-projects">
      <div className="td-my-projects__hero">
        <h1 className="text-display">Amplía la base de conocimiento citable.</h1>
        <p className="text-body td-my-projects__hero-sub">
          Sube una propuesta anterior en PDF. Trace Desk la divide en fragmentos y los deja
          disponibles de inmediato como fuentes citables para nuevas respuestas a RFP.
        </p>
      </div>

      <div className="td-my-projects__card">
        <div className="td-my-projects__field">
          <label className="text-label td-my-projects__label" htmlFor="my-projects-file">
            Documento (PDF)
          </label>
          <div className="td-my-projects__file-picker">
            <Button weight="secondary" type="button" onClick={() => fileInputRef.current?.click()}>
              Elegir archivo
            </Button>
            <span className="text-body-sm td-my-projects__file-name">
              {file ? <span className="text-mono">{file.name}</span> : 'Ningún archivo seleccionado'}
            </span>
          </div>
          <input
            id="my-projects-file"
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="visually-hidden"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>

        <div className="td-my-projects__row">
          <div className="td-my-projects__field">
            <label className="text-label td-my-projects__label" htmlFor="my-projects-section">
              Tipo de sección
            </label>
            <select
              id="my-projects-section"
              className="td-my-projects__select"
              value={sectionType}
              onChange={(event) => setSectionType(event.target.value as IngestSectionType)}
            >
              {SECTION_TYPE_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="td-my-projects__field">
            <label className="text-label td-my-projects__label" htmlFor="my-projects-source">
              Nombre de la fuente (opcional)
            </label>
            <input
              id="my-projects-source"
              type="text"
              className="td-my-projects__text-input"
              placeholder={file?.name ?? 'Propuesta_ClienteX_2024.md'}
              value={source}
              onChange={(event) => setSource(event.target.value)}
            />
          </div>
        </div>

        {error && <Badge tone="caution">{error}</Badge>}

        <div className="td-my-projects__actions">
          <Button
            icon={isSubmitting ? <Loader2 className="td-my-projects__spinner" /> : <UploadCloud />}
            disabled={!file || isSubmitting}
            onClick={handleSubmit}
          >
            {isSubmitting ? 'Procesando…' : 'Agregar al corpus'}
          </Button>
        </div>
      </div>

      {log.length === 0 ? (
        <Callout icon={<FolderKanban />} title="Todavía no agregaste documentos en esta sesión">
          Los fragmentos que agregues aquí quedan disponibles para el pipeline de inmediato — no
          hace falta reiniciar nada. Esta lista muestra solo lo agregado en tu sesión actual; el
          corpus completo vive en el servidor.
        </Callout>
      ) : (
        <div className="td-my-projects__log">
          <p className="text-h3 td-my-projects__log-title">Agregado en esta sesión</p>
          {log.map((entry) => (
            <div key={entry.id} className="td-my-projects__log-entry">
              <FileStack className="td-my-projects__log-icon" />
              <div className="td-my-projects__log-body">
                <p className="text-body td-my-projects__log-source">{entry.source}</p>
                <p className="text-caption td-my-projects__log-meta">
                  {sectionTypeLabel(entry.section_type)} · {entry.chunk_count} fragmento
                  {entry.chunk_count === 1 ? '' : 's'}
                </p>
              </div>
              <Badge tone="success">Agregado</Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
