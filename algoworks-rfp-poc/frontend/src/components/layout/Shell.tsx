import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import './Shell.css'

interface ShellProps {
  backendOnline: boolean
  children: ReactNode
}

/** Sidebar fixed left (240px) + content area, padded, on a surface background - shared by all screens. */
export function Shell({ backendOnline, children }: ShellProps) {
  return (
    <div className="td-shell">
      <Sidebar backendOnline={backendOnline} />
      <main className="td-shell__content">{children}</main>
    </div>
  )
}
