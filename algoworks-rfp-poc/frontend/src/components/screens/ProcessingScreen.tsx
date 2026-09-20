import { FileSearch } from 'lucide-react'
import type { TraceEvent } from '../../api/types'
import { Callout } from '../ui/Callout'
import { ProgressStep, type StepState } from '../ui/ProgressStep'
import { ReasoningFeed } from '../ui/ReasoningFeed'
import './ProcessingScreen.css'

const STEP_ORDER = [
  'extract_requirements',
  'retrieve_chunks',
  'generate_draft',
  'verify_citations',
  'compute_traceability_metrics',
] as const

const STEPS: { title: string; subtitle: string }[] = [
  { title: 'Extraer requisitos', subtitle: 'Convirtiendo el RFP en requisitos estructurados.' },
  { title: 'Recuperar fragmentos', subtitle: 'Buscando fuentes de respaldo en la base de conocimiento.' },
  { title: 'Generar borrador', subtitle: 'Redactando cada sección con citas en línea.' },
  { title: 'Verificar citas', subtitle: 'Comprobando que cada cita respalda su afirmación.' },
  { title: 'Calcular métricas de trazabilidad', subtitle: 'Auditando la corrida y midiendo el respaldo de cada cita.' },
]

interface ProcessingScreenProps {
  isSettled: boolean
  hasError: boolean
  /** Real trace_log from GET /rfp/{id}/progress, growing as the backend's
   * background pipeline thread actually completes each node - not a timer. */
  traceLog: TraceEvent[]
}

/**
 * furthestStepIndex is the highest STEP_ORDER index seen in the trace log so
 * far - not the last event's index - so a generate_draft/verify_citations
 * retry loop (the node repeating) never makes the progress rail regress.
 */
function furthestStepIndex(traceLog: TraceEvent[]): number {
  let furthest = -1
  for (const event of traceLog) {
    const index = STEP_ORDER.indexOf(event.node as (typeof STEP_ORDER)[number])
    if (index > furthest) furthest = index
  }
  return furthest
}

export function ProcessingScreen({ isSettled, hasError, traceLog }: ProcessingScreenProps) {
  const activeIndex = isSettled && !hasError ? STEPS.length - 1 : Math.max(furthestStepIndex(traceLog), 0)

  function stateFor(index: number): StepState {
    if (isSettled) {
      if (hasError) {
        if (index < activeIndex) return 'done'
        if (index === activeIndex) return 'error'
        return 'pending'
      }
      return 'done'
    }
    if (index < activeIndex) return 'done'
    if (index === activeIndex) return 'active'
    return 'pending'
  }

  return (
    <div className="td-processing">
      <h1 className="text-h1">Analizando tu solicitud…</h1>
      <p className="text-body-sm td-processing__sub">
        Puede tardar hasta un minuto - el pipeline extrae requisitos, busca fuentes y verifica cada
        afirmación antes de responder.
      </p>

      <div className="td-processing__columns">
        <div className="td-processing__steps">
          {STEPS.map((step, index) => (
            <ProgressStep
              key={step.title}
              title={step.title}
              subtitle={step.subtitle}
              state={stateFor(index)}
              isLast={index === STEPS.length - 1}
              connectorDone={stateFor(index + 1) === 'done'}
            />
          ))}
        </div>
        <ReasoningFeed traceLog={traceLog} isRunning={!isSettled} />
      </div>

      <Callout icon={<FileSearch />} title="Basado en un corpus propio">
        Se basa en un corpus ficticio de propuestas anteriores y capacidades técnicas de Algoworks -
        ningún dato real ni confidencial forma parte de esta demo.
      </Callout>
    </div>
  )
}
