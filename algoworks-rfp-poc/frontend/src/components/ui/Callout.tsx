import type { ReactNode } from 'react'
import './Callout.css'

interface CalloutProps {
  icon: ReactNode
  title: string
  children: ReactNode
}

/** A fixed primary-subtle box: one icon + h3 + one body-sm sentence. */
export function Callout({ icon, title, children }: CalloutProps) {
  return (
    <div className="td-callout">
      <span className="td-callout__icon">{icon}</span>
      <div>
        <p className="td-callout__title text-h3">{title}</p>
        <p className="td-callout__body text-body-sm">{children}</p>
      </div>
    </div>
  )
}
