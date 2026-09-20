import { useEffect, useRef, useState } from 'react'
import './App.css'
import { checkHealth, composeProposal, runRfpPipeline, startRfpProcess, startRfpProcessPdf } from './api/client'
import type { PipelineResult, ProposalDocument, TraceEvent } from './api/types'
import { Shell } from './components/layout/Shell'
import { HomeScreen } from './components/screens/HomeScreen'
import { MyProjectsScreen } from './components/screens/MyProjectsScreen'
import { ProcessingScreen } from './components/screens/ProcessingScreen'
import { ResultsScreen } from './components/screens/results/ResultsScreen'

export type AppView = 'home' | 'processing' | 'results' | 'my-projects'

export default function App() {
  const [view, setView] = useState<AppView>('home')
  const [backendOnline, setBackendOnline] = useState(true)
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null)
  const [processError, setProcessError] = useState<string | null>(null)
  const [isSettled, setIsSettled] = useState(false)
  const [liveTraceLog, setLiveTraceLog] = useState<TraceEvent[]>([])
  const [proposalDocument, setProposalDocument] = useState<ProposalDocument | null>(null)
  const [proposalError, setProposalError] = useState<string | null>(null)
  const [isComposing, setIsComposing] = useState(false)
  // Guards against a poll loop from an abandoned run (user started a new
  // request before the previous one settled) still writing into state.
  const activeRunRef = useRef(0)

  useEffect(() => {
    checkHealth().then(setBackendOnline)
  }, [])

  /**
   * The consolidated proposal is drafted automatically right after the base
   * response - one unified workflow, no separate "generate proposal" step
   * for the user. It runs after the response is already showing (rather
   * than blocking on it) so the response - the primary, faster result -
   * appears as soon as it's ready instead of waiting on a second LLM call.
   */
  async function composeInBackground(rfpId: string) {
    setIsComposing(true)
    setProposalError(null)
    try {
      const proposal = await composeProposal(rfpId)
      setProposalDocument(proposal)
    } catch (err) {
      setProposalError(err instanceof Error ? err.message : 'No se pudo generar la propuesta consolidada.')
    } finally {
      setIsComposing(false)
    }
  }

  async function runPipeline(start: (rfpId: string) => Promise<{ rfp_id: string; status: string }>) {
    const runId = ++activeRunRef.current
    setView('processing')
    setIsSettled(false)
    setProcessError(null)
    setProposalDocument(null)
    setProposalError(null)
    setLiveTraceLog([])
    const rfpId = `rfp_${crypto.randomUUID().slice(0, 8)}`
    try {
      const result = await runRfpPipeline(
        () => start(rfpId),
        rfpId,
        (traceLog) => {
          if (activeRunRef.current === runId) setLiveTraceLog(traceLog)
        },
      )
      if (activeRunRef.current !== runId) return
      setPipelineResult(result)
      setIsSettled(true)
      setView('results')
      void composeInBackground(rfpId)
    } catch (err) {
      if (activeRunRef.current !== runId) return
      setProcessError(err instanceof Error ? err.message : 'Ha ocurrido un error inesperado.')
      setIsSettled(true)
    }
  }

  function handleSubmit(rfpText: string) {
    return runPipeline((rfpId) => startRfpProcess(rfpId, rfpText))
  }

  function handleSubmitFile(file: File) {
    return runPipeline((rfpId) => startRfpProcessPdf(rfpId, file))
  }

  function handleRegenerateProposal() {
    if (!pipelineResult) return
    void composeInBackground(pipelineResult.rfp_id)
  }

  function handleNavigate(target: 'home' | 'my-projects') {
    if (target === 'my-projects') {
      setView('my-projects')
      return
    }
    // "Nueva solicitud" always starts a fresh request, even mid-pipeline.
    setPipelineResult(null)
    setProcessError(null)
    setProposalDocument(null)
    setProposalError(null)
    setView('home')
  }

  return (
    <Shell backendOnline={backendOnline} activeView={view} onNavigate={handleNavigate}>
      {view === 'home' && <HomeScreen onSubmit={handleSubmit} onSubmitFile={handleSubmitFile} />}
      {view === 'my-projects' && <MyProjectsScreen />}
      {view === 'processing' && (
        <ProcessingScreen isSettled={isSettled} hasError={Boolean(processError)} traceLog={liveTraceLog} />
      )}
      {view === 'results' && pipelineResult && (
        <ResultsScreen
          result={pipelineResult}
          proposal={proposalDocument}
          isComposingProposal={isComposing}
          proposalError={proposalError}
          onRegenerateProposal={handleRegenerateProposal}
        />
      )}
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
