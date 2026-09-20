import { useRef, useState } from 'react'
import { FileCheck2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { ExampleChips } from '../ui/ExampleChips'
import { InputPanel } from '../ui/InputPanel'
import { SegmentedTabs, type TabOption } from '../ui/SegmentedTabs'
import { SAMPLE_RFPS } from '../../data/sampleRfps'
import './HomeScreen.css'

const MAX_LENGTH = 20000

const METHOD_TABS: TabOption[] = [
  { id: 'paste', label: 'Pegar texto' },
  { id: 'upload', label: 'Subir documento' },
]

interface HomeScreenProps {
  onSubmit: (rfpText: string) => void
  onSubmitFile: (file: File) => void
}

export function HomeScreen({ onSubmit, onSubmitFile }: HomeScreenProps) {
  const [activeTab, setActiveTab] = useState('paste')
  const [rfpText, setRfpText] = useState('')
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  async function handleFileChange(file: File | null) {
    if (!file) return
    if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
      setPdfFile(file)
      setRfpText('')
      return
    }
    setPdfFile(null)
    const text = await file.text()
    setRfpText(text.slice(0, MAX_LENGTH))
    setActiveTab('paste')
  }

  function handleTextChange(value: string) {
    setPdfFile(null)
    setRfpText(value)
  }

  function handleSelectSample(id: string) {
    const sample = SAMPLE_RFPS.find((rfp) => rfp.id === id)
    if (!sample) return
    setPdfFile(null)
    setRfpText(sample.text.slice(0, MAX_LENGTH))
  }

  return (
    <div className="td-home">
      <div className="td-home__hero">
        <div className="td-home__seal" aria-hidden="true">TD</div>
        <div className="td-home__hero-text">
          <h1 className="text-display">Redacta una respuesta a RFP citada y verificada.</h1>
          <p className="text-body td-home__hero-sub">
            Pega la solicitud del cliente y Trace Desk extrae los requisitos, recupera fuentes de
            respaldo y redacta una respuesta que puedes rastrear hasta cada afirmación.
          </p>
        </div>
      </div>

      <div className="td-home__card">
        <SegmentedTabs options={METHOD_TABS} activeId={activeTab} onChange={setActiveTab} />

        <div className="td-home__field">
          {activeTab === 'upload' ? (
            <div className="td-home__upload">
              <p className="text-body-sm td-home__upload-hint">
                Sube un PDF (extraído por el backend) o un archivo de texto plano (.txt, .md) con el RFP.
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
                accept=".txt,.md,.pdf,application/pdf"
                className="visually-hidden"
                onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
              />
              {pdfFile && (
                <p className="text-caption td-home__upload-loaded">
                  PDF listo: <span className="text-mono">{pdfFile.name}</span>
                </p>
              )}
              {rfpText && (
                <p className="text-caption td-home__upload-loaded">
                  Archivo cargado (<span className="text-mono">{rfpText.length}</span> caracteres).
                </p>
              )}
            </div>
          ) : (
            <>
              <InputPanel
                value={rfpText}
                onChange={handleTextChange}
                placeholder="Pega aqui el texto del RFP o requerimiento del cliente..."
                maxLength={MAX_LENGTH}
              />
              <div className="td-home__examples">
                <p className="text-label td-home__examples-label">Probar con un ejemplo</p>
                <ExampleChips
                  chips={SAMPLE_RFPS.map((rfp) => ({ id: rfp.id, label: rfp.label }))}
                  onSelect={handleSelectSample}
                />
              </div>
            </>
          )}
        </div>

        <div className="td-home__actions">
          <Button
            icon={<FileCheck2 />}
            disabled={!rfpText.trim() && !pdfFile}
            onClick={() => (pdfFile ? onSubmitFile(pdfFile) : onSubmit(rfpText))}
          >
            Generar respuesta
          </Button>
        </div>
      </div>
    </div>
  )
}
