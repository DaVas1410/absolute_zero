import './MetricTile.css'

interface MetricTileProps {
  label: string
  value: string
}

export function MetricTile({ label, value }: MetricTileProps) {
  return (
    <div className="td-metric-tile">
      <p className="text-label td-metric-tile__label">{label}</p>
      <p className="text-h1 td-metric-tile__value">{value}</p>
    </div>
  )
}
