import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import type { ReasoningPathAudit } from '../../api/types'
import './ConsistencyBanner.css'

interface ConsistencyBannerProps {
  audit: ReasoningPathAudit
}

/**
 * ReasoningPathAudit's own deterministic, non-LLM check that the graph
 * actually executed the rules it was designed to follow - the "second
 * opinion that isn't trust-the-LLM," placed directly under the metrics row.
 */
export function ConsistencyBanner({ audit }: ConsistencyBannerProps) {
  if (audit.is_consistent) {
    return (
      <div className="td-consistency-banner td-consistency-banner--success">
        <CheckCircle2 />
        <span className="text-body">Camino de ejecución consistente</span>
      </div>
    )
  }

  return (
    <div className="td-consistency-banner td-consistency-banner--caution">
      <AlertTriangle />
      <div>
        <p className="text-body" style={{ margin: 0 }}>
          {audit.issues.length} problema(s) detectado(s) en el camino de ejecución
        </p>
        <ul className="td-consistency-banner__issues">
          {audit.issues.map((issue) => (
            <li key={issue} className="text-body-sm">
              {issue}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
