import type { DashboardResponse } from '@/types/planning'

function percent(value: number) { return `${(value * 100).toFixed(1)}%` }

export function DataProvenance({ dashboard }: { dashboard: DashboardResponse }) {
  const assumptions = dashboard.assumptions
  return (
    <section className="panel provenance-panel" aria-labelledby="provenance-title">
      <div className="section-heading"><div><div className="eyebrow">Audit trail</div><h2 id="provenance-title">Assumptions &amp; sources</h2></div><span className="unit-note">Public + synthetic</span></div>
      <div className="provenance-grid"><div><h3>Planning assumptions</h3><div className="assumption-list">{Object.entries(assumptions.budget_assumptions).map(([unit, value]) => <div className="assumption-row" key={unit}><span>{unit}</span><span>{percent(value.revenue_growth_vs_fy2025)} growth · {percent(value.budget_gross_margin)} GM · {percent(value.budget_operating_margin)} OM · RMB {value.average_ticket} ticket</span></div>)}</div><p className="disclaimer">{assumptions.note}</p></div><div><h3>Official data sources</h3><div className="source-list">{dashboard.data_sources.map((source) => <a href={source.url} target="_blank" rel="noreferrer" key={source.url}><span>{source.name}</span><small>{source.source_date} · {source.scope}</small></a>)}</div></div></div>
      <div className="legend"><h3>Provenance legend</h3>{Object.entries(dashboard.provenance_legend).map(([key, value]) => <span key={key}><i className={`legend-dot ${key}`} />{key.replaceAll('_', ' ')}: {value}</span>)}</div>
    </section>
  )
}
