import type { ReactNode } from 'react'
import './TopBar.css'

interface TopBarProps {
  title: string
  meta?: string
  right?: ReactNode
}

/** Page title (h1) + either a meta line or subtitle, with a badge/buttons on the right - never both. */
export function TopBar({ title, meta, right }: TopBarProps) {
  return (
    <div className="td-topbar">
      <div>
        <h1 className="text-h1 td-topbar__title">{title}</h1>
        {meta && <p className="text-body-sm td-topbar__meta">{meta}</p>}
      </div>
      {right && <div className="td-topbar__right">{right}</div>}
    </div>
  )
}
