import { RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { getTrace } from '../../../api/client'
import type { TraceEvent } from '../../../api/types'
import { Button } from '../../ui/Button'
import { formatDuration, formatTokens } from '../../../utils/format'
import './TraceLogTab.css'

interface TraceLogTabProps {
  rfpId: string
  traceLog: TraceEvent[]
}

/**
 * Repurposes the design doc's "Suggested Next Steps" 4th tab, which has no
 * PipelineResult field to back it, into a real-data raw trace table -
 * matching sec 7's own instruction that TraceEvent's extended fields
 * "become a legitimate raw-data table."
 */
export function TraceLogTab({ rfpId, traceLog: initialTraceLog }: TraceLogTabProps) {
  const [traceLog, setTraceLog] = useState(initialTraceLog)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleRefresh() {
    setIsRefreshing(true)
    setError(null)
    try {
      const fresh = await getTrace(rfpId)
      setTraceLog(fresh)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo refrescar el trace.')
    } finally {
      setIsRefreshing(false)
    }
  }

  return (
    <div className="td-trace-tab">
      <div className="td-trace-tab__toolbar">
        <Button weight="secondary" icon={<RefreshCw />} onClick={handleRefresh} disabled={isRefreshing}>
          {isRefreshing ? 'Refrescando…' : 'Refresh trace'}
        </Button>
        {error && <span className="text-body-sm td-trace-tab__error">{error}</span>}
      </div>

      <table className="td-trace-tab__table">
        <thead>
          <tr>
            <th>Node</th>
            <th>Timestamp</th>
            <th>Duration</th>
            <th>Tokens</th>
            <th>Reasoning</th>
          </tr>
        </thead>
        <tbody>
          {traceLog.map((event, index) => (
            <tr key={`${event.node}-${index}`}>
              <td>{event.node}</td>
              <td>{new Date(event.timestamp).toLocaleTimeString()}</td>
              <td>{formatDuration(event.duration_ms)}</td>
              <td>{event.tokens ? formatTokens(event.tokens.total_tokens) : '—'}</td>
              <td className="td-trace-tab__reasoning">{event.reasoning}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
