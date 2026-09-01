import type { ProfitBridge as ProfitBridgeData } from '@/types/planning'

function amount(value: number | null) {
  return value === null ? '—' : `${value >= 0 ? '+' : ''}${value.toLocaleString('en-US', { maximumFractionDigits: 1 })}`
}

function share(value: number | null) {
  return value === null ? '—' : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

export function ProfitBridge({ bridge }: { bridge: ProfitBridgeData }) {
  const max = Math.max(...bridge.items.map((item) => Math.abs(item.amount || 0)), 1)
  const variance = bridge.operating_profit_variance
  return (
    <section className="panel profit-bridge-panel" aria-labelledby="profit-bridge-title">
      <div className="section-heading"><div><div className="eyebrow">Profit bridge</div><h2 id="profit-bridge-title">Operating Profit bridge</h2></div><span className="unit-note">Actual − budget · RMBm</span></div>
      <div className="pvm-total"><div><span>Actual operating profit</span><strong>{amount(bridge.actual_operating_profit)}</strong></div><div className="pvm-arrow">−</div><div><span>Budget operating profit</span><strong>{amount(bridge.budget_operating_profit)}</strong></div><div className="pvm-arrow">=</div><div><span>OP variance</span><strong>{amount(variance)}</strong></div></div>
      <div className="bridge-list">{bridge.items.map((item) => <div className="bridge-row" key={item.driver}>
        <div className="bridge-label"><span>{item.driver}</span><strong>{amount(item.amount)}</strong></div>
        <div className="bridge-track"><div className={`bridge-fill ${item.direction === 'unfavorable' ? 'negative-fill' : item.direction === 'neutral' ? 'mix' : ''}`} style={{ width: `${Math.max(Math.abs(item.amount || 0) / max * 100, 2)}%` }} /></div>
        <div className="bridge-meta"><span>{share(item.pct_of_variance)} of OP variance</span><span>{item.direction || 'not available'}</span><span>{item.provenance}</span><span>Owner: {item.action_owner}</span></div>
      </div>)}</div>
      <div className={`reconciliation ${Math.abs(bridge.reconciliation_difference || 0) <= 0.01 ? 'ok' : 'bad'}`}>Reconciliation difference: {bridge.reconciliation_difference?.toFixed(6) || '—'} RMBm · calculated</div>
    </section>
  )
}
