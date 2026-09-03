import type { PvmBridge as PvmBridgeData } from '@/types/planning'
import { useI18n } from '@/i18n'

export function PvmBridge({ bridge }: { bridge: PvmBridgeData }) {
  const { t, formatNumber } = useI18n()
  const number = (value: number | null) => value === null ? t('notAvailable') : `${value >= 0 ? '+' : ''}${formatNumber(value)}`
  const values = [{ label: t('volume'), value: bridge.volume, tone: 'volume' }, { label: t('mix'), value: bridge.mix, tone: 'mix' }, { label: t('price'), value: bridge.price, tone: 'price' }]
  const max = Math.max(...values.map((item) => Math.abs(item.value || 0)), 1)
  const revenueVariance = bridge.actual_revenue === null || bridge.budget_revenue === null ? null : bridge.actual_revenue - bridge.budget_revenue
  return (
    <section className="panel pvm-panel" aria-labelledby="pvm-title">
      <div className="section-heading"><div><div className="eyebrow">{t('revenueBridge')}</div><h2 id="pvm-title">{t('priceVolumeMix')}</h2></div><span className="unit-note">{t('actualBudgetRmbm')}</span></div>
      <div className="pvm-total"><div><span>{t('actualRevenue')}</span><strong>{formatNumber(bridge.actual_revenue)}</strong></div><div className="pvm-arrow">−</div><div><span>{t('budgetRevenue')}</span><strong>{formatNumber(bridge.budget_revenue)}</strong></div><div className="pvm-arrow">=</div><div><span>{t('revenueVariance')}</span><strong>{number(revenueVariance)}</strong></div></div>
      <div className="bridge-list">{values.map((item) => <div className="bridge-row" key={item.label}><div className="bridge-label"><span>{item.label}</span><strong>{number(item.value)}</strong></div><div className="bridge-track"><div className={`bridge-fill ${item.tone} ${item.value !== null && item.value < 0 ? 'negative-fill' : ''}`} style={{ width: `${Math.max(Math.abs(item.value || 0) / max * 100, 2)}%` }} /></div></div>)}</div>
      <div className={`reconciliation ${Math.abs(bridge.reconciliation_difference || 0) <= 0.01 ? 'ok' : 'bad'}`}>{t('reconciliationDifference')}: {bridge.reconciliation_difference === null ? t('notAvailable') : formatNumber(bridge.reconciliation_difference, { maximumFractionDigits: 6 })} RMBm</div>
    </section>
  )
}
