import { FileSearch } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Callout } from '../ui/Callout'
import { ProgressStep, type StepState } from '../ui/ProgressStep'
import './ProcessingScreen.css'

const STEPS: { title: string; subtitle: string }[] = [
  { title: 'Extraer requisitos', subtitle: 'Convirtiendo el RFP en requisitos estructurados.' },
  { title: 'Recuperar fragmentos', subtitle: 'Buscando fuentes de respaldo en la base de conocimiento.' },
  { title: 'Generar borrador', subtitle: 'Redactando cada sección con citas en línea.' },
  { title: 'Verificar citas', subtitle: 'Comprobando que cada cita respalda su afirmación.' },
  { title: 'Calcular métricas de trazabilidad', subtitle: 'Auditando la corrida y midiendo el respaldo de cada cita.' },
]

const STEP_INTERVAL_MS = 3000

interface ProcessingScreenProps {
  isSettled: boolean
  hasError: boolean
}

/**
 * POST /rfp/process is a single blocking call with no incremental signal
 * (SSE streaming is out of scope), so there's no real per-node completion
 * event to bind to. Steps advance on a fixed timer using the 5 real graph
 * node names while the request is in flight - a labeled, bounded
 * simulation, not fabricated content - and resolve to done/error on settle.
 */
export function ProcessingScreen({ isSettled, hasError }: ProcessingScreenProps) {
  const [activeIndex, setActiveIndex] = useState(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setActiveIndex((current) => Math.min(current + 1, STEPS.length - 1))
    }, STEP_INTERVAL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  useEffect(() => {
    if (isSettled && intervalRef.current) {
      clearInterval(intervalRef.current)
    }
  }, [isSettled])

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
        <div className="td-processing__illustration" aria-hidden="true">
          <FileSearch />
        </div>
      </div>

      <Callout icon={<FileSearch />} title="Basado en un corpus propio">
        Se basa en un corpus ficticio de propuestas anteriores y capacidades técnicas de Algoworks -
        ningún dato real ni confidencial forma parte de esta demo.
      </Callout>
    </div>
  )
}
