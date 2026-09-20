import type { ReactNode } from 'react'
import type { AppView } from '../../App'
import { Sidebar } from './Sidebar'
import './Shell.css'

interface ShellProps {
  backendOnline: boolean
  activeView: AppView
  onNavigate: (view: 'home' | 'my-projects') => void
  children: ReactNode
}

/** Sidebar fixed left (240px) + content area, padded, on a surface background - shared by all screens. */
export function Shell({ backendOnline, activeView, onNavigate, children }: ShellProps) {
  return (
    <div className="td-shell">
      <Sidebar backendOnline={backendOnline} activeView={activeView} onNavigate={onNavigate} />
      <main className="td-shell__content">{children}</main>
    </div>
  )
}
