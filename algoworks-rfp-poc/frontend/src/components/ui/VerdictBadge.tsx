import { AlertTriangle, Check } from 'lucide-react'
import { formatPercent } from '../../utils/format'
import { Badge } from './Badge'

interface VerdictBadgeProps {
  supported: boolean
  confidence: number
}

/**
 * The direct surface for VerificationResult.supported + .confidence - word
 * and glyph together (never color alone), confidence % always inline, and
 * never hidden when `supported` is false.
 */
export function VerdictBadge({ supported, confidence }: VerdictBadgeProps) {
  if (supported) {
    return (
      <Badge tone="success" icon={<Check />}>
        Supported · {formatPercent(confidence)}
      </Badge>
    )
  }
  return (
    <Badge tone="caution" icon={<AlertTriangle />}>
      Needs review · {formatPercent(confidence)}
    </Badge>
  )
}
