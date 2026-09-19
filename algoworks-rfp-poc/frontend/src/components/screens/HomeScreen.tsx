import { useRef, useState } from 'react'
import { Button } from '../ui/Button'
import { ExampleChips } from '../ui/ExampleChips'
import { InputPanel } from '../ui/InputPanel'
import { SegmentedTabs, type TabOption } from '../ui/SegmentedTabs'
import { SAMPLE_RFPS } from '../../data/sampleRfps'
import './HomeScreen.css'

const MAX_LENGTH = 20000

const METHOD_TABS: TabOption[] = [
  { id: 'paste', label: 'Paste Text' },
  { id: 'upload', label: 'Upload Document' },
  { id: 'template', label: 'Use a Template' },
]

interface HomeScreenProps {
  onSubmit: (rfpText: string) => void
}

export function HomeScreen({ onSubmit }: HomeScreenProps) {
  const [activeTab, setActiveTab] = useState('paste')
  const [rfpText, setRfpText] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  async function handleFileChange(file: File | null) {
    if (!file) return
    const text = await file.text()
    setRfpText(text.slice(0, MAX_LENGTH))
    setActiveTab('paste')
  }

  function handleChipSelect(sampleId: string) {
    const sample = SAMPLE_RFPS.find((s) => s.id === sampleId)
    if (!sample) return
    setRfpText(sample.text)
    setActiveTab('paste')
  }

  return (
    <div className="td-home">
      <div className="td-home__hero">
        <h1 className="text-display">Draft a cited, verified RFP response.</h1>
        <p className="text-body td-home__hero-sub">
          Paste a client request and Trace Desk extracts requirements, retrieves supporting sources,
          and drafts a response you can trace back to every claim.
        </p>
      </div>

      <div className="td-home__card">
        <SegmentedTabs options={METHOD_TABS} activeId={activeTab} onChange={setActiveTab} />

        <div className="td-home__field">
          {activeTab === 'upload' ? (
            <div className="td-home__upload">
              <p className="text-body-sm td-home__upload-hint">
                Sube un archivo de texto plano (.txt, .md) con el RFP.
              </p>
              <Button
                weight="secondary"
                type="button"
                onClick={() => fileInputRef.current?.click()}
              >
                Elegir archivo
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md"
                className="visually-hidden"
                onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
              />
              {rfpText && <p className="text-caption td-home__upload-loaded">Archivo cargado ({rfpText.length} caracteres).</p>}
            </div>
          ) : (
            <InputPanel
              value={rfpText}
              onChange={setRfpText}
              placeholder="Pega aqui el texto del RFP o requerimiento del cliente..."
              maxLength={MAX_LENGTH}
            />
          )}
        </div>

        {activeTab !== 'upload' && (
          <div className="td-home__examples">
            <p className="text-caption td-home__examples-label">Ejemplos</p>
            <ExampleChips
              chips={SAMPLE_RFPS.map((sample) => ({ id: sample.id, label: sample.label }))}
              onSelect={handleChipSelect}
            />
          </div>
        )}

        <div className="td-home__actions">
          <Button disabled={!rfpText.trim()} onClick={() => onSubmit(rfpText)}>
            Generate Response
          </Button>
        </div>
      </div>
    </div>
  )
}
