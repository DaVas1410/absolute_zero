import './UnderlineTabs.css'
import type { TabOption } from './SegmentedTabs'

interface UnderlineTabsProps {
  options: TabOption[]
  activeId: string
  onChange: (id: string) => void
}

/** Underline tab bar - for switching views of a result that already exists. */
export function UnderlineTabs({ options, activeId, onChange }: UnderlineTabsProps) {
  return (
    <div className="td-underline-tabs" role="tablist">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          role="tab"
          aria-selected={option.id === activeId}
          className={`td-underline-tabs__item ${option.id === activeId ? 'is-active' : ''}`}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
