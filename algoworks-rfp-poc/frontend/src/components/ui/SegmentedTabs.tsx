import './SegmentedTabs.css'

export interface TabOption {
  id: string
  label: string
}

interface SegmentedTabsProps {
  options: TabOption[]
  activeId: string
  onChange: (id: string) => void
}

/** Track + lifted active pill - for choosing an input method before a request exists. */
export function SegmentedTabs({ options, activeId, onChange }: SegmentedTabsProps) {
  return (
    <div className="td-segmented" role="tablist">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          role="tab"
          aria-selected={option.id === activeId}
          className={`td-segmented__item ${option.id === activeId ? 'is-active' : ''}`}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
