import { Check } from 'lucide-react'
import './ProgressStep.css'

export type StepState = 'done' | 'active' | 'pending' | 'error'

interface ProgressStepProps {
  title: string
  subtitle: string
  state: StepState
  isLast: boolean
  /** Whether the step below this one is done - colors the connecting rule. */
  connectorDone: boolean
}

export function ProgressStep({ title, subtitle, state, isLast, connectorDone }: ProgressStepProps) {
  return (
    <div className="td-step">
      <div className="td-step__rail">
        <span className={`td-step__dot td-step__dot--${state}`}>{state === 'done' && <Check />}</span>
        {!isLast && (
          <span className={`td-step__connector td-step__connector--${connectorDone ? 'done' : 'pending'}`} />
        )}
      </div>
      <div className="td-step__copy">
        <p className={`text-h3 td-step__title td-step__title--${state}`}>{title}</p>
        <p className="text-body-sm td-step__subtitle">{subtitle}</p>
      </div>
    </div>
  )
}
