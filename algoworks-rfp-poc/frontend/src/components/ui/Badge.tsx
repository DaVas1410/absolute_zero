import type { ReactNode } from 'react'
import './Badge.css'

export type BadgeTone = 'success' | 'caution' | 'primary' | 'neutral'

interface BadgeProps {
  tone: BadgeTone
  icon?: ReactNode
  children: ReactNode
  className?: string
}

/**
 * The single Badge primitive behind all three families the design doc
 * describes (status, verification verdict, plain tag) - callers pick the
 * tone/icon/label combination that matches which family they're rendering;
 * see VerdictBadge/FeedbackBadge for the two that carry specific meaning.
 */
export function Badge({ tone, icon, children, className }: BadgeProps) {
  const classes = ['td-badge', `td-badge--${tone}`, className].filter(Boolean).join(' ')
  return (
    <span className={classes}>
      {icon}
      {children}
    </span>
  )
}
