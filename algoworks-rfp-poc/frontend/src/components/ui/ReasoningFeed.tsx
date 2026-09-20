import { Gauge, ListChecks, PenLine, RotateCcw, Search, ShieldCheck } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { ComponentType } from 'react'
import type { TraceEvent } from '../../api/types'
import './ReasoningFeed.css'

const NODE_META: Record<string, { label: string; icon: ComponentType<{ size?: number }> }> = {
  extract_requirements: { label: 'Extraer requisitos', icon: ListChecks },
  retrieve_chunks: { label: 'Recuperar fragmentos', icon: Search },
  generate_draft: { label: 'Generar borrador', icon: PenLine },
  verify_citations: { label: 'Verificar citas', icon: ShieldCheck },
  compute_traceability_metrics: { label: 'Calcular métricas', icon: Gauge },
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

interface ReasoningFeedProps {
  traceLog: TraceEvent[]
  isRunning: boolean
}

/**
 * A live log of the pipeline's actual trace events, styled like case-file
 * entries being stamped in one at a time - not a generic chat widget. Every
 * line here is a real TraceEvent the backend produced, in the order it
 * produced it; nothing is simulated.
 */
export function ReasoningFeed({ traceLog, isRunning }: ReasoningFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const occurrenceCount = new Map<string, number>()

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [traceLog.length])

  return (
    <div className="td-reasoning">
      <div className="td-reasoning__header">
        <span className="text-label td-reasoning__label">Razonamiento en vivo</span>
        {isRunning && <span className="td-reasoning__live-dot" aria-hidden="true" />}
      </div>
      <div className="td-reasoning__scroll" ref={scrollRef}>
        {traceLog.length === 0 && (
          <p className="text-body-sm td-reasoning__empty">Esperando el primer evento del pipeline…</p>
        )}
        {traceLog.map((event, index) => {
          const meta = NODE_META[event.node] ?? { label: event.node, icon: ListChecks }
          const Icon = meta.icon
          const occurrence = (occurrenceCount.get(event.node) ?? 0) + 1
          occurrenceCount.set(event.node, occurrence)
          const isRetry = occurrence > 1

          return (
            <article className="td-reasoning__entry" key={`${event.node}-${index}`}>
              <span className="td-reasoning__icon">
                <Icon size={14} />
              </span>
              <div className="td-reasoning__body">
                <div className="td-reasoning__meta">
                  <span className="text-h3 td-reasoning__node">{meta.label}</span>
                  {isRetry && (
                    <span className="td-reasoning__retry-tag">
                      <RotateCcw size={10} />
                      reintento
                    </span>
                  )}
                  <span className="text-mono td-reasoning__duration">{formatDuration(event.duration_ms)}</span>
                </div>
                <p className="text-body-sm td-reasoning__reasoning">{event.reasoning}</p>
                <p className="text-caption td-reasoning__summary">
                  {event.input_summary} → {event.output_summary}
                </p>
              </div>
            </article>
          )
        })}
        {isRunning && (
          <div className="td-reasoning__thinking" aria-live="polite">
            <span className="td-reasoning__thinking-dot" />
            <span className="td-reasoning__thinking-dot" />
            <span className="td-reasoning__thinking-dot" />
          </div>
        )}
      </div>
    </div>
  )
}
