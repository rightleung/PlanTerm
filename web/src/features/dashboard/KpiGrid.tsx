import type { KpiSnapshot } from '@/types/planning'

function money(value: number | null) {
  return value === null ? '—' : `RMB ${value.toLocaleString('en-US', { maximumFractionDigits: 1 })}m`
}

function percent(value: number | null) {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

export function KpiGrid({ kpis }: { kpis: KpiSnapshot[] }) {
  return (
    <section className="kpi-grid" aria-label="Key performance indicators">
      {kpis.map((kpi) => {
        const isMargin = kpi.metric === 'operating_margin'
        const display = isMargin ? percent(kpi.actual_ytd) : money(kpi.actual_ytd)
        const variance = isMargin ? `${kpi.variance_amount === null ? '—' : `${kpi.variance_amount >= 0 ? '+' : ''}${(kpi.variance_amount * 100).toFixed(1)} pts`}` : money(kpi.variance_amount)
        return (
          <article className="kpi-card" key={kpi.metric}>
            <div className="eyebrow">{kpi.label} <span>· H1 actual</span></div>
            <div className="kpi-value">{display}</div>
            <div className={`kpi-status ${kpi.status?.toLowerCase() || ''}`}>{kpi.status || 'Not available'}</div>
            <div className="kpi-detail">vs budget <strong>{variance}</strong></div>
            <div className="kpi-detail">YoY <strong>{percent(kpi.yoy_pct)}</strong></div>
          </article>
        )
      })}
    </section>
  )
}

