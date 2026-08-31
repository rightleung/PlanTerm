import type { PvmBridge as PvmBridgeData } from '@/types/planning'

function number(value: number | null) { return value === null ? '—' : `${value >= 0 ? '+' : ''}${value.toLocaleString('en-US', { maximumFractionDigits: 1 })}` }

export function PvmBridge({ bridge }: { bridge: PvmBridgeData }) {
  const values = [{ label: 'Volume', value: bridge.volume, tone: 'volume' }, { label: 'Mix', value: bridge.mix, tone: 'mix' }, { label: 'Price', value: bridge.price, tone: 'price' }]
  const max = Math.max(...values.map((item) => Math.abs(item.value || 0)), 1)
  return (
    <section className="panel pvm-panel" aria-labelledby="pvm-title">
      <div className="section-heading"><div><div className="eyebrow">Revenue bridge</div><h2 id="pvm-title">Price / Volume / Mix</h2></div><span className="unit-note">Actual − budget · RMBm</span></div>
      <div className="pvm-total"><div><span>Actual revenue</span><strong>{bridge.actual_revenue?.toLocaleString('en-US', { maximumFractionDigits: 1 }) || '—'}</strong></div><div className="pvm-arrow">−</div><div><span>Budget revenue</span><strong>{bridge.budget_revenue?.toLocaleString('en-US', { maximumFractionDigits: 1 }) || '—'}</strong></div><div className="pvm-arrow">=</div><div><span>Revenue variance</span><strong>{number((bridge.actual_revenue || 0) - (bridge.budget_revenue || 0))}</strong></div></div>
      <div className="bridge-list">{values.map((item) => <div className="bridge-row" key={item.label}><div className="bridge-label"><span>{item.label}</span><strong>{number(item.value)}</strong></div><div className="bridge-track"><div className={`bridge-fill ${item.tone} ${item.value !== null && item.value < 0 ? 'negative-fill' : ''}`} style={{ width: `${Math.max(Math.abs(item.value || 0) / max * 100, 2)}%` }} /></div></div>)}</div>
      <div className={`reconciliation ${Math.abs(bridge.reconciliation_difference || 0) <= 0.01 ? 'ok' : 'bad'}`}>Reconciliation difference: {bridge.reconciliation_difference?.toFixed(6) || '—'} RMBm</div>
    </section>
  )
}

