import { useEffect, useState } from 'react'
import './App.css'
import { checkHealth, processRfp } from './api/client'
import type { PipelineResult } from './api/types'
import { Shell } from './components/layout/Shell'
import { HomeScreen } from './components/screens/HomeScreen'
import { ProcessingScreen } from './components/screens/ProcessingScreen'
import { ResultsScreen } from './components/screens/results/ResultsScreen'

type AppView = 'home' | 'processing' | 'results'

export default function App() {
  const [view, setView] = useState<AppView>('home')
  const [backendOnline, setBackendOnline] = useState(true)
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null)
  const [processError, setProcessError] = useState<string | null>(null)
  const [isSettled, setIsSettled] = useState(false)

  useEffect(() => {
    checkHealth().then(setBackendOnline)
  }, [])

  async function handleSubmit(rfpText: string) {
    setView('processing')
    setIsSettled(false)
    setProcessError(null)
    const rfpId = `rfp_${crypto.randomUUID().slice(0, 8)}`
    try {
      const result = await processRfp(rfpId, rfpText)
      setPipelineResult(result)
      setIsSettled(true)
      setView('results')
    } catch (err) {
      setProcessError(err instanceof Error ? err.message : 'Ha ocurrido un error inesperado.')
      setIsSettled(true)
    }
  }

  return (
    <Shell backendOnline={backendOnline}>
      {view === 'home' && <HomeScreen onSubmit={handleSubmit} />}
      {view === 'processing' && <ProcessingScreen isSettled={isSettled} hasError={Boolean(processError)} />}
      {view === 'results' && pipelineResult && <ResultsScreen result={pipelineResult} />}
      {view === 'processing' && isSettled && processError && (
        <div className="td-app-error">
          <p className="text-body">{processError}</p>
          <button type="button" className="td-app-error__retry" onClick={() => setView('home')}>
            Volver al inicio
          </button>
        </div>
      )}
    </Shell>
  )
}
