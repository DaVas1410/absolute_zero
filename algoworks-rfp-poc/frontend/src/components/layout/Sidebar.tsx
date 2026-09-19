import { FilePlus2, FolderKanban } from 'lucide-react'
import './Sidebar.css'

interface SidebarProps {
  backendOnline: boolean
}

const NAV_ITEMS = [
  { id: 'new-request', label: 'Nueva solicitud', icon: FilePlus2, active: true },
  { id: 'my-projects', label: 'Mis proyectos', icon: FolderKanban, active: false },
]

/** Fixed 240px dark rail - identical across every screen. */
export function Sidebar({ backendOnline }: SidebarProps) {
  return (
    <aside className="td-sidebar">
      <div>
        <div className="td-sidebar__brand">
          <span className="td-sidebar__mark" aria-hidden="true" />
          <span className="text-h3 td-sidebar__wordmark">Trace Desk</span>
        </div>
        <p className="text-caption td-sidebar__tagline">Know where every answer comes from.</p>

        <nav className="td-sidebar__nav">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <div key={item.id} className={`td-sidebar__nav-item ${item.active ? 'is-active' : ''}`}>
                <Icon />
                <span className="text-body">{item.label}</span>
              </div>
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
