import type { PipelineResult } from '../../../api/types'
import { Badge } from '../../ui/Badge'
import { VerdictBadge } from '../../ui/VerdictBadge'
import './RequirementsTab.css'

interface RequirementsTabProps {
  result: PipelineResult
}

/** One row per extracted Requirement - section_target, full text, and its verdict. */
export function RequirementsTab({ result }: RequirementsTabProps) {
  return (
    <div className="td-requirements-tab">
      {result.requirements.map((requirement) => {
        const verification = result.verification[requirement.req_id]
        return (
          <div key={requirement.req_id} className="td-requirements-tab__row">
            <Badge tone="neutral">{requirement.section_target}</Badge>
            <p className="text-body td-requirements-tab__text">{requirement.text}</p>
            {verification && (
              <VerdictBadge supported={verification.supported} confidence={verification.confidence} />
            )}
          </div>
        )
      })}
    </div>
  )
}
