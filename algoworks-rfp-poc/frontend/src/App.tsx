import { useEffect, useState } from 'react'
import './App.css'
import { checkHealth, composeProposal, processRfp, processRfpPdf } from './api/client'
import type { PipelineResult, ProposalDocument } from './api/types'
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
  const [proposalDocument, setProposalDocument] = useState<ProposalDocument | null>(null)
  const [proposalError, setProposalError] = useState<string | null>(null)
  const [isComposing, setIsComposing] = useState(false)

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

  async function runPipeline(run: (rfpId: string) => Promise<PipelineResult>) {
    setView('processing')
    setIsSettled(false)
    setProcessError(null)
    setProposalDocument(null)
    setProposalError(null)
    const rfpId = `rfp_${crypto.randomUUID().slice(0, 8)}`
    try {
      const result = await run(rfpId)
      setPipelineResult(result)
      setIsSettled(true)
      setView('results')
      void composeInBackground(rfpId)
    } catch (err) {
      setProcessError(err instanceof Error ? err.message : 'Ha ocurrido un error inesperado.')
      setIsSettled(true)
    }
  }

  function handleSubmit(rfpText: string) {
    return runPipeline((rfpId) => processRfp(rfpId, rfpText))
  }

  function handleSubmitFile(file: File) {
    return runPipeline((rfpId) => processRfpPdf(rfpId, file))
  }

  function handleRegenerateProposal() {
    if (!pipelineResult) return
    void composeInBackground(pipelineResult.rfp_id)
  }

  return (
    <Shell backendOnline={backendOnline}>
      {view === 'home' && <HomeScreen onSubmit={handleSubmit} onSubmitFile={handleSubmitFile} />}
      {view === 'processing' && <ProcessingScreen isSettled={isSettled} hasError={Boolean(processError)} />}
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
