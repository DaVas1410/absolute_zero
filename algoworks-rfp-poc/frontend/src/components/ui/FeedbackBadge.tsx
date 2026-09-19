import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { Badge } from './Badge'

interface FeedbackBadgeProps {
  accepted: boolean
}

/**
 * The human-in-the-loop decision on a requirement card. Deliberately a
 * different color family (neutral, not success/caution) and different
 * icon set (thumbs, not check/triangle) than VerdictBadge, so the LLM's
 * own verdict and the human's decision are never visually conflated.
 */
export function FeedbackBadge({ accepted }: FeedbackBadgeProps) {
  return (
    <Badge tone="neutral" icon={accepted ? <ThumbsUp /> : <ThumbsDown />}>
      {accepted ? 'Accepted' : 'Rejected'}
    </Badge>
  )
}
