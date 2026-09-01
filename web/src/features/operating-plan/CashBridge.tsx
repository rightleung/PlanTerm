import type { CashBridge as CashBridgeData, ReconciliationStatus, WorkingCapitalPlan } from '@/types/planning'

function amount(value: number | null) {
  return value === null ? 'Not available' : value.toLocaleString('en-US', { maximumFractionDigits: 1 })
}

function number(value: number | null) {
  return value === null ? 'Not available' : value.toLocaleString('en-US', { maximumFractionDigits: 1 })
}

export function CashBridge({ workingCapital, cashBridge, reconciliation }: { workingCapital: WorkingCapitalPlan; cashBridge: CashBridgeData; reconciliation: ReconciliationStatus }) {
  const rows = workingCapital.rows || []
  const latest = cashBridge.rows[cashBridge.rows.length - 1] || null
  const bridge = [
    ['Opening cash', latest?.opening_cash ?? null], ['Operating profit', latest?.operating_profit ?? null], ['AR effect', latest === null || latest.prior_ar === null || latest.current_ar === null ? null : latest.prior_ar - latest.current_ar],
    ['Inventory effect', latest === null || latest.prior_inventory === null || latest.current_inventory === null ? null : latest.prior_inventory - latest.current_inventory], ['AP effect', latest === null || latest.current_ap === null || latest.prior_ap === null ? null : latest.current_ap - latest.prior_ap], ['CAPEX', latest?.capex ?? null],
    ['Other cash', latest?.other_cash_items ?? null], ['Net cash change', latest?.net_cash_change ?? null], ['Illustrative closing cash', latest?.closing_illustrative_cash ?? null],
    ['Minimum cash buffer', latest?.minimum_cash_buffer ?? null], ['Headroom', latest?.headroom ?? null],
  ] as const
  return <section className="panel table-panel" aria-labelledby="operating-cash-title">
    <div className="section-heading"><div><div className="eyebrow">Operating planning</div><h2 id="operating-cash-title">Working capital and illustrative cash</h2></div><span className="unit-note">RMB millions · calculated</span></div>
    <div className="synthetic-disclosure">Synthetic planning assumptions and calculated illustrative cash - not public reported or actual cash.</div>
    {rows.length === 0 ? <div className="empty-state" role="status">Working-capital rows are not available for this plan variant.</div> : <div className="table-scroll"><table><thead><tr><th>Period</th><th>Business unit</th><th>AR days</th><th>Inventory days</th><th>AP days</th><th>AR balance</th><th>Inventory</th><th>AP balance</th><th>NWC</th><th>CCC</th><th>Provenance</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.period}-${row.business_unit}`}><td>{row.period}</td><td className="table-primary">{row.business_unit}</td><td>{number(row.ar_days)}</td><td>{number(row.inventory_days)}</td><td>{number(row.ap_days)}</td><td>{amount(row.ar_balance)}</td><td>{amount(row.inventory_balance)}</td><td>{amount(row.ap_balance)}</td><td>{amount(row.nwc)}</td><td>{number(row.ccc)}</td><td>{row.provenance}</td></tr>)}</tbody></table></div>}
    <div className="scenario-grid">{bridge.map(([label, value]) => <div key={label}><span>{label}</span><strong className={value !== null && value < 0 ? 'negative' : ''}>{amount(value)}</strong></div>)}</div>
    <p className={`reconciliation ${reconciliation.status === 'reconciled' ? 'ok' : 'bad'}`}>Reconciliation: {reconciliation.status || 'Not available'} · cash bridge {reconciliation.cash_bridge.status || 'Not available'} · max residual {amount(reconciliation.cash_bridge.max_residual ?? null)} · category roll-up {reconciliation.category_rollup.status || 'Not available'} · revenue residual {amount(reconciliation.category_rollup.revenue_residual ?? null)} · tolerance {amount(reconciliation.tolerance_rmb_millions)}</p>
  </section>
}
