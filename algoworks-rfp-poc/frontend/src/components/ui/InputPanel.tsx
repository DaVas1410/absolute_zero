import type { ChangeEvent } from 'react'
import './InputPanel.css'

interface InputPanelProps {
  value: string
  onChange: (value: string) => void
  placeholder: string
  maxLength: number
}

/** The request textarea with a live current/max counter. */
export function InputPanel({ value, onChange, placeholder, maxLength }: InputPanelProps) {
  function handleChange(event: ChangeEvent<HTMLTextAreaElement>) {
    onChange(event.target.value.slice(0, maxLength))
  }

  return (
    <div className="td-input-panel">
      <textarea
        className="td-input-panel__textarea"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        rows={8}
        maxLength={maxLength}
      />
      <div className="td-input-panel__counter text-caption">
        {value.length.toLocaleString('en-US')} / {maxLength.toLocaleString('en-US')}
      </div>
    </div>
  )
}
