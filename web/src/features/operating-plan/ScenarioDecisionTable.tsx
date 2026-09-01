import type { ScenarioDecisionRow } from '@/types/planning'

function amount(value: number | null) { return value === null ? 'Not available' : value.toLocaleString('en-US', { maximumFractionDigits: 1 }) }
function delta(value: number | null) { return value === null ? 'Not available' : `${value >= 0 ? '+' : ''}${amount(value)}` }

export function ScenarioDecisionTable({ decisionTable, selectedVariant }: { decisionTable: ScenarioDecisionRow[]; selectedVariant: string }) {
  const rows = decisionTable || []
  return <section className="panel table-panel" aria-labelledby="decision-table-title">
    <div className="section-heading"><div><div className="eyebrow">Decision support</div><h2 id="decision-table-title">Scenario decision table</h2></div><span className="unit-note">Selected {selectedVariant} · RMB millions</span></div>
    <div className="synthetic-disclosure">Scenario outcomes are synthetic planning assumptions with calculated deltas.</div>
    {rows.length === 0 ? <div className="empty-state" role="status">No scenario decision rows are available.</div> : <div className="table-scroll"><table><thead><tr><th>Plan variant</th><th>FY revenue delta</th><th>FY OP delta</th><th>Cash headroom</th><th>Minimum cash month</th><th>CCC</th><th>Owner</th><th>Next review</th><th>Provenance</th></tr></thead><tbody>{rows.map((row) => <tr key={row.plan_variant}><td className="table-primary">{row.plan_variant}</td><td className={row.fy_revenue_delta !== null && row.fy_revenue_delta < 0 ? 'negative' : 'positive'}>{delta(row.fy_revenue_delta)}</td><td className={row.fy_operating_profit_delta !== null && row.fy_operating_profit_delta < 0 ? 'negative' : 'positive'}>{delta(row.fy_operating_profit_delta)}</td><td>{amount(row.cash_headroom)}</td><td>{row.minimum_cash_month || 'Not available'}</td><td>{amount(row.ccc)}</td><td>{row.owner || 'Not available'}</td><td>{row.next_review_date || 'Not available'}</td><td>{row.provenance}</td></tr>)}</tbody></table></div>}
  </section>
}
