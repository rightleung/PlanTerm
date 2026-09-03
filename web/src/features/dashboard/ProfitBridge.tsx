import type { ProfitBridge as ProfitBridgeData } from '@/types/planning'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

export function ProfitBridge({ bridge }: { bridge: ProfitBridgeData }) {
  const { t, formatNumber } = useI18n()
  const amount = (value: number | null) => value === null ? t('notAvailable') : `${value >= 0 ? '+' : ''}${formatNumber(value)}`
  const share = (value: number | null) => value === null ? t('notAvailable') : `${value >= 0 ? '+' : ''}${formatNumber(value * 100)}%`
  const max = Math.max(...bridge.items.map((item) => Math.abs(item.amount || 0)), 1)
  const variance = bridge.operating_profit_variance
  return (
    <section className="panel profit-bridge-panel" aria-labelledby="profit-bridge-title">
      <div className="section-heading"><div><div className="eyebrow">{t('profitBridge')}</div><h2 id="profit-bridge-title">{t('operatingProfitBridge')}</h2></div><span className="unit-note">{t('actualBudgetRmbm')}</span></div>
      <div className="pvm-total"><div><span>{t('actualOperatingProfit')}</span><strong>{amount(bridge.actual_operating_profit)}</strong></div><div className="pvm-arrow">−</div><div><span>{t('budgetOperatingProfit')}</span><strong>{amount(bridge.budget_operating_profit)}</strong></div><div className="pvm-arrow">=</div><div><span>{t('opVariance')}</span><strong>{amount(variance)}</strong></div></div>
      <div className="bridge-list">{bridge.items.map((item) => <div className="bridge-row" key={item.driver}>
        <div className="bridge-label"><span>{apiLabel(item.driver, t)}</span><strong>{amount(item.amount)}</strong></div>
        <div className="bridge-track"><div className={`bridge-fill ${item.direction === 'unfavorable' ? 'negative-fill' : item.direction === 'neutral' ? 'mix' : ''}`} style={{ width: `${Math.max(Math.abs(item.amount || 0) / max * 100, 2)}%` }} /></div>
        <div className="bridge-meta"><span>{share(item.pct_of_variance)} {t('ofOpVariance')}</span><span>{apiLabel(item.direction, t)}</span><span>{apiLabel(item.provenance, t)}</span><span>{t('owner')}: {apiLabel(item.action_owner, t)}</span></div>
      </div>)}</div>
      <div className={`reconciliation ${Math.abs(bridge.reconciliation_difference || 0) <= 0.01 ? 'ok' : 'bad'}`}>{t('reconciliationDifference')}: {bridge.reconciliation_difference === null ? t('notAvailable') : formatNumber(bridge.reconciliation_difference, { maximumFractionDigits: 6 })} RMBm · {t('calculated')}</div>
    </section>
  )
}
