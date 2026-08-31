import type { VarianceRow } from '@/types/planning'

function money(value: number | null) { return value === null ? '—' : value.toLocaleString('en-US', { maximumFractionDigits: 1 }) }
function pct(value: number | null) { return value === null ? '—' : `${(value * 100).toFixed(1)}%` }

export function VarianceTable({ rows }: { rows: VarianceRow[] }) {
  return (
    <section className="panel table-panel" aria-labelledby="variance-title">
      <div className="section-heading"><div><div className="eyebrow">Portfolio roll-up</div><h2 id="variance-title">Business-unit variance</h2></div><span className="unit-note">YTD actual vs budget</span></div>
      {rows.length === 0 ? <div className="empty-state">No business unit matches the selected filters.</div> : <div className="table-scroll"><table><thead><tr><th>Business unit</th><th>Revenue actual</th><th>Budget</th><th>Variance</th><th>Var. %</th><th>Gross margin</th><th>Operating profit variance</th><th>FY forecast gap</th><th>Revenue driver</th><th>Profit driver</th><th>Status</th></tr></thead><tbody>{rows.map((row) => <tr key={row.business_unit}><td className="table-primary">{row.business_unit}</td><td>{money(row.revenue_actual)}</td><td>{money(row.revenue_budget)}</td><td className={row.revenue_variance !== null && row.revenue_variance < 0 ? 'negative' : 'positive'}>{money(row.revenue_variance)}</td><td>{pct(row.revenue_variance_pct)}</td><td>{pct(row.gross_margin_actual)} <span className="muted">/ {pct(row.gross_margin_budget)}</span></td><td className={row.operating_profit_variance !== null && row.operating_profit_variance < 0 ? 'negative' : 'positive'}>{money(row.operating_profit_variance)}</td><td className={row.forecast_gap !== null && row.forecast_gap < 0 ? 'negative' : 'positive'}>{money(row.forecast_gap)}</td><td><span className="driver-pill">{row.primary_driver || '—'}</span></td><td><span className="driver-pill">{row.profit_driver || '—'}</span></td><td><span className={`status-pill ${row.status?.toLowerCase() || ''}`}>{row.status || '—'}</span></td></tr>)}</tbody></table></div>}
    </section>
  )
}
