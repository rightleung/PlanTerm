import type { WorkforceCapacityResponse, WorkforceCapacityRollup, WorkforceRoleGroup } from '@/types/planning'

const ROLE_GROUPS: WorkforceRoleGroup[] = ['store operations', 'commercial', 'supply chain', 'finance/support']

function amount(value: number | null | undefined) {
  return value === null || value === undefined || !Number.isFinite(value) ? '—' : value.toLocaleString('en-US', { maximumFractionDigits: 1 })
}

function fte(value: number | null | undefined) { return amount(value) }

function rollupMetric(rollup: WorkforceCapacityRollup | undefined, metric: keyof WorkforceCapacityRollup) {
  const value = rollup?.[metric]
  return typeof value === 'number' ? value : null
}

export function HeadcountCapacity({ capacity }: { capacity: WorkforceCapacityResponse }) {
  const rows = capacity.headcount_rows || []
  const selected = capacity.plan_variant
  const portfolio = capacity.rollups?.portfolio
  const evidence = capacity.reconciliation_evidence || { status: 'Not available' }
  const delta = capacity.selected_vs_base_delta || {}
  return <section className="panel table-panel" aria-labelledby="workforce-capacity-title">
    <div className="section-heading"><div><div className="eyebrow">Operating planning</div><h2 id="workforce-capacity-title">Workforce Capacity</h2></div><span className="unit-note">Selected {selected} · {capacity.unit}</span></div>
    <div className="synthetic-disclosure">{capacity.disclosure || 'Synthetic payroll/headcount and capacity planning data; not reported or HRIS data.'}</div>
    <p className="panel-footnote">Productivity basis: {rows[0]?.productivity_basis || 'Revenue / planned FTE'} · role-group planning only; no individual employees.</p>
    {capacity.locked_rows?.length > 0 && <div className="synthetic-disclosure">Locked horizon through 2026-06; editable workforce planning begins 2026-07.</div>}
    <div className="scenario-grid">
      <div><span>Portfolio planned FTE</span><strong>{fte(rollupMetric(portfolio, 'planned_fte'))}</strong></div>
      <div><span>Required FTE</span><strong>{fte(rollupMetric(portfolio, 'required_fte'))}</strong></div>
      <div><span>Capacity gap</span><strong>{fte(rollupMetric(portfolio, 'capacity_gap'))}</strong></div>
      <div><span>Loaded cost</span><strong>{amount(rollupMetric(portfolio, 'loaded_cost'))}</strong></div>
      <div><span>Variant delta</span><strong>{amount(delta.loaded_cost ?? null)}</strong></div>
    </div>
    <div className="table-scroll"><table><thead><tr><th>Role group</th><th>Planned FTE</th><th>Required FTE</th><th>Capacity gap</th><th>Loaded cost</th><th>Revenue / FTE</th><th>Variant delta</th><th>Status</th><th>Provenance</th></tr></thead><tbody>
      {ROLE_GROUPS.map((role) => { const summary = capacity.rollups?.role_group?.[role]; const roleRows = rows.filter((row) => row.role_group === role); const revenue = roleRows.reduce((total, row) => total + (Number.isFinite(row.revenue) ? row.revenue : 0), 0); const planned = rollupMetric(summary, 'planned_fte') || 0; const revenuePerFte = planned > 0 ? revenue / planned : null; const status = roleRows.some((row) => row.status === 'capacity_gap') ? 'capacity_gap' : roleRows.some((row) => row.status === 'over_capacity') ? 'over_capacity' : roleRows.length > 0 && roleRows.every((row) => row.status === 'zero_capacity') ? 'zero_capacity' : 'balanced'; return <tr key={role}><td className="table-primary">{role}</td><td>{fte(rollupMetric(summary, 'planned_fte'))}</td><td>{fte(rollupMetric(summary, 'required_fte'))}</td><td>{fte(rollupMetric(summary, 'capacity_gap'))}</td><td>{amount(rollupMetric(summary, 'loaded_cost'))}</td><td>{amount(revenuePerFte)}</td><td>{amount(delta[`${role}.loaded_cost`] ?? null)}</td><td>{status}</td><td>{summary?.provenance || capacity.provenance}</td></tr> })}
      <tr><td className="table-primary">Portfolio total</td><td>{fte(rollupMetric(portfolio, 'planned_fte'))}</td><td>{fte(rollupMetric(portfolio, 'required_fte'))}</td><td>{fte(rollupMetric(portfolio, 'capacity_gap'))}</td><td>{amount(rollupMetric(portfolio, 'loaded_cost'))}</td><td>{amount((rollupMetric(portfolio, 'planned_fte') || 0) > 0 ? (rows.reduce((t, r) => t + r.revenue, 0) / (rollupMetric(portfolio, 'planned_fte') || 1)) : null)}</td><td>{amount(delta.loaded_cost ?? null)}</td><td>{evidence.status}</td><td>{capacity.provenance}</td></tr>
    </tbody></table></div>
    <p className={`reconciliation ${evidence.status === 'reconciled' ? 'ok' : 'bad'}`}>Reconciliation: {evidence.status || 'Not available'} · residual {amount(evidence.residual ?? evidence.max_residual ?? null)} · tolerance {amount(evidence.tolerance_rmb_millions ?? null)}{evidence.no_double_counting === true ? ' · no double counting' : ''}</p>
  </section>
}
