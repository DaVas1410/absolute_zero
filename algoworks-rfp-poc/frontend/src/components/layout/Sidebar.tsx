import { FilePlus2, FolderKanban } from 'lucide-react'
import type { AppView } from '../../App'
import './Sidebar.css'

interface SidebarProps {
  backendOnline: boolean
  activeView: AppView
  onNavigate: (view: 'home' | 'my-projects') => void
}

const NAV_ITEMS: { id: 'home' | 'my-projects'; label: string; icon: typeof FilePlus2; isActive: (view: AppView) => boolean }[] = [
  { id: 'home', label: 'Nueva solicitud', icon: FilePlus2, isActive: (view) => view !== 'my-projects' },
  { id: 'my-projects', label: 'Mis proyectos', icon: FolderKanban, isActive: (view) => view === 'my-projects' },
]

/** Fixed 240px dark rail - identical across every screen. */
export function Sidebar({ backendOnline, activeView, onNavigate }: SidebarProps) {
  return (
    <aside className="td-sidebar">
      <div>
        <div className="td-sidebar__brand">
          <span className="td-sidebar__mark" aria-hidden="true">
            TD
          </span>
          <span className="td-sidebar__wordmark">Trace Desk</span>
        </div>
        <p className="text-caption td-sidebar__tagline">Know where every answer comes from.</p>

        <nav className="td-sidebar__nav">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const isActive = item.isActive(activeView)
            return (
              <button
                key={item.id}
                type="button"
                className={`td-sidebar__nav-item ${isActive ? 'is-active' : ''}`}
                aria-current={isActive ? 'page' : undefined}
                onClick={() => onNavigate(item.id)}
              >
                <Icon />
                <span className="text-body">{item.label}</span>
              </button>
            )
          })}
        </nav>
      </div>

      <div className="td-sidebar__account">
        <span className={`td-sidebar__status-dot ${backendOnline ? 'is-online' : 'is-offline'}`} />
        <div>
          <p className="text-body-sm td-sidebar__account-name">Algoworks RFP PoC</p>
          <p className="text-caption td-sidebar__account-email">
            {backendOnline ? 'Backend conectado' : 'Backend no disponible'}
          </p>
        </div>
      </div>
    </aside>
  )
}
