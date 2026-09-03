import type { CashBridge as CashBridgeData, ReconciliationStatus, WorkingCapitalPlan } from '@/types/planning'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

export function CashBridge({ workingCapital, cashBridge, reconciliation }: { workingCapital: WorkingCapitalPlan; cashBridge: CashBridgeData; reconciliation: ReconciliationStatus }) {
  const { t, formatNumber } = useI18n()
  const amount = (value: number | null) => value === null ? t('notAvailable') : formatNumber(value)
  const number = amount
  const rows = workingCapital.rows || []
  const latest = cashBridge.rows[cashBridge.rows.length - 1] || null
  const bridge = [
    ['Opening cash', latest?.opening_cash ?? null], ['Operating profit', latest?.operating_profit ?? null], ['AR effect', latest === null || latest.prior_ar === null || latest.current_ar === null ? null : latest.prior_ar - latest.current_ar],
    ['Inventory effect', latest === null || latest.prior_inventory === null || latest.current_inventory === null ? null : latest.prior_inventory - latest.current_inventory], ['AP effect', latest === null || latest.current_ap === null || latest.prior_ap === null ? null : latest.current_ap - latest.prior_ap], ['CAPEX', latest?.capex ?? null],
    ['Other cash', latest?.other_cash_items ?? null], ['Net cash change', latest?.net_cash_change ?? null], ['Illustrative closing cash', latest?.closing_illustrative_cash ?? null],
    ['Minimum cash buffer', latest?.minimum_cash_buffer ?? null], ['Headroom', latest?.headroom ?? null],
  ] as const
  const bridgeLabels = { 'Opening cash': 'openingCash', 'Operating profit': 'operatingProfit', 'AR effect': 'arEffect', 'Inventory effect': 'inventoryEffect', 'AP effect': 'apEffect', CAPEX: 'capex', 'Other cash': 'otherCash', 'Net cash change': 'netCashChange', 'Illustrative closing cash': 'illustrativeClosingCash', 'Minimum cash buffer': 'minimumCashBuffer', Headroom: 'headroom' } as const
  return <section className="panel table-panel" aria-labelledby="operating-cash-title">
    <div className="section-heading"><div><div className="eyebrow">{t('operatingPlanning')}</div><h2 id="operating-cash-title">{t('workingCapitalCash')}</h2></div><span className="unit-note">{t('rmbMillions')} · {t('calculated')}</span></div>
    <div className="synthetic-disclosure">{t('syntheticCashDisclosure')}</div>
    {rows.length === 0 ? <div className="empty-state" role="status">{t('workingCapitalUnavailable')}</div> : <div className="table-scroll" role="region" tabIndex={0} aria-label={t('workingCapitalCash')}><table><thead><tr><th>{t('period')}</th><th>{t('businessUnit')}</th><th>{t('arDays')}</th><th>{t('inventoryDays')}</th><th>{t('apDays')}</th><th>{t('arBalance')}</th><th>{t('inventory')}</th><th>{t('apBalance')}</th><th>{t('nwc')}</th><th>{t('ccc')}</th><th>{t('provenance')}</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.period}-${row.business_unit}`}><td>{row.period}</td><td className="table-primary">{apiLabel(row.business_unit, t)}</td><td>{number(row.ar_days)}</td><td>{number(row.inventory_days)}</td><td>{number(row.ap_days)}</td><td>{amount(row.ar_balance)}</td><td>{amount(row.inventory_balance)}</td><td>{amount(row.ap_balance)}</td><td>{amount(row.nwc)}</td><td>{number(row.ccc)}</td><td>{apiLabel(row.provenance, t)}</td></tr>)}</tbody></table></div>}
    <div className="scenario-grid">{bridge.map(([label, value]) => <div key={label}><span>{t(bridgeLabels[label])}</span><strong className={value !== null && value < 0 ? 'negative' : ''}>{amount(value)}</strong></div>)}</div>
    <p className={`reconciliation ${reconciliation.status === 'reconciled' ? 'ok' : 'bad'}`}>{t('reconciliationSummary', { status: apiLabel(reconciliation.status, t), cashStatus: apiLabel(reconciliation.cash_bridge.status, t), maxResidual: amount(reconciliation.cash_bridge.max_residual ?? null), categoryStatus: apiLabel(reconciliation.category_rollup.status, t), revenueResidual: amount(reconciliation.category_rollup.revenue_residual ?? null), tolerance: amount(reconciliation.tolerance_rmb_millions) })}</p>
  </section>
}
