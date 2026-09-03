import { Plus } from 'lucide-react'
import { useState } from 'react'
import type { DecisionLogRow } from '@/types/planning'
import { useI18n, type TranslationKey } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

const statuses: DecisionLogRow['status'][] = ['Proposed', 'Approved', 'Superseded', 'Closed']
const blankDecision = (): DecisionLogRow => ({
  decision_id: `decision-${Date.now()}`,
  date: new Date().toISOString().slice(0, 10),
  context: '', options: '', decision: '', rationale: '', owner_role: 'Group FP&A',
  affected_contracts: '', evidence: '', supersedes: null, status: 'Proposed',
})

const fields: Array<keyof DecisionLogRow> = ['date', 'context', 'options', 'decision', 'rationale', 'owner_role', 'affected_contracts', 'evidence', 'supersedes', 'status']
const requiredTextFields = ['date', 'context', 'options', 'decision', 'rationale', 'owner_role', 'affected_contracts', 'evidence'] as const

function nextDecisionId(rows: DecisionLogRow[]) {
  const base = `decision-${Date.now()}`
  let candidate = base
  let suffix = 2
  while (rows.some((row) => row.decision_id === candidate)) candidate = `${base}-${suffix++}`
  return candidate
}

const fieldLabels: Record<string, TranslationKey> = { date: 'date', context: 'context', options: 'options', decision: 'decision', rationale: 'rationale', owner_role: 'ownerRole', affected_contracts: 'affectedContracts', evidence: 'evidence', supersedes: 'supersedes', status: 'status' }

function displayValue(value: DecisionLogRow[keyof DecisionLogRow], notAvailable: string, locale: string, t: (key: TranslationKey, vars?: Record<string, string | number>) => string) {
  if (value === null || value === undefined || value === '') return notAvailable
  if (Array.isArray(value)) {
    return value.map((item) => typeof item === 'string' ? apiLabel(item, t) : `${apiLabel(item.metric, t)}: ${apiLabel(item.formula, t)} · ${apiLabel(item.source, t)} · ${apiLabel(item.reconciliation_status, t)}`).join(' | ')
  }
  if (locale !== 'en' && typeof value === 'string') {
    const context = value.match(/^FY2026 (base|upside|downside) operating-plan conclusion$/)
    if (context) return t('decisionContext', { variant: apiLabel(context[1], t) })
    const decision = value.match(/^Use the (base|upside|downside) plan variant for review$/)
    if (decision) return t('decisionUseVariant', { variant: apiLabel(decision[1], t) })
    if (value === 'Scenario conclusion is calculated from the committed category and cash bridges.') return t('decisionRationale')
  }
  return typeof value === 'string' ? apiLabel(value, t) : value
}

export function DecisionLog({ rows, onChange }: { rows: DecisionLogRow[]; onChange: (rows: DecisionLogRow[]) => void }) {
  const { locale, t } = useI18n()
  const [draft, setDraft] = useState<DecisionLogRow>(blankDecision)
  const updateDraft = <K extends keyof DecisionLogRow>(field: K, value: DecisionLogRow[K]) => setDraft((current) => ({ ...current, [field]: value }))
  const canAdd = requiredTextFields.every((field) => typeof draft[field] === 'string' && draft[field].trim().length > 0)
  const addDecision = () => {
    if (!canAdd) return
    onChange([...rows, { ...draft, decision_id: nextDecisionId(rows), context: draft.context.trim(), decision: draft.decision.trim(), rationale: draft.rationale.trim() }])
    setDraft(blankDecision())
  }

  return <section className="panel table-panel" aria-labelledby="decision-log-title">
    <div className="section-heading"><div><div className="eyebrow">{t('governance')}</div><h2 id="decision-log-title">{t('decisionLog')}</h2></div><span className="unit-note">{t('sessionImmutable')}</span></div>
    <div className="synthetic-disclosure">{t('addedEventsSession')}</div>
    <div className="table-scroll" role="region" tabIndex={0} aria-label={t('decisionLog')}><table><thead><tr><th>{t('decisionId')}</th>{fields.map((field) => <th key={field}>{t(fieldLabels[field])}</th>)}</tr></thead><tbody>{rows.length === 0 ? <tr><td colSpan={fields.length + 1}>{t('noDecisions')}</td></tr> : rows.map((row) => <tr key={row.decision_id}><td className="table-primary">{row.decision_id}</td>{fields.map((field) => <td key={field}>{displayValue(row[field], t('notAvailable'), locale, t)}</td>)}</tr>)}</tbody></table></div>
    <div className="decision-form" aria-label={t('addDecision')}>
      <h3>{t('addDecision')}</h3>
      <div className="form-grid">{fields.map((field) => field === 'status' ? <label key={field}>{t(fieldLabels[field])}<select aria-label={t(fieldLabels[field])} value={draft.status} onChange={(event) => updateDraft('status', event.target.value as DecisionLogRow['status'])}>{statuses.map((status) => <option key={status} value={status}>{apiLabel(status, t)}</option>)}</select></label> : <label key={field}>{t(fieldLabels[field])}{field === 'context' || field === 'options' || field === 'decision' || field === 'rationale' || field === 'affected_contracts' || field === 'evidence' ? <textarea aria-label={t(fieldLabels[field])} rows={2} value={typeof draft[field] === 'string' ? draft[field] : ''} onChange={(event) => updateDraft(field, event.target.value as never)} /> : <input aria-label={t(fieldLabels[field])} type={field === 'date' ? 'date' : 'text'} value={field === 'owner_role' && draft[field] === 'Group FP&A' ? apiLabel(draft[field], t) : typeof draft[field] === 'string' ? draft[field] : ''} onChange={(event) => updateDraft(field, event.target.value as never)} />}</label>)}</div>
      <button className="button button-primary" type="button" onClick={addDecision} disabled={!canAdd}><Plus size={14} /> {t('addDecision')}</button>
    </div>
  </section>
}
