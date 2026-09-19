import './ExampleChips.css'

export interface Chip {
  id: string
  label: string
}

interface ExampleChipsProps {
  chips: Chip[]
  onSelect: (id: string) => void
}

export function ExampleChips({ chips, onSelect }: ExampleChipsProps) {
  return (
    <div className="td-chips">
      {chips.map((chip) => (
        <button key={chip.id} type="button" className="td-chips__chip" onClick={() => onSelect(chip.id)}>
          {chip.label}
        </button>
      ))}
    </div>
  )
}
