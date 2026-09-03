import { Plus, Trash2 } from 'lucide-react'
import type { ActionRegisterRow } from '@/types/planning'
import { useI18n, type TranslationKey } from '@/i18n'

const blankAction = (): ActionRegisterRow => ({ action_id: `session-${Date.now()}`, observation: '', driver: '', impact: null, risk: '', action: '', owner: 'FP&A', due_period: '', cadence: 'monthly', status: 'Open', provenance: 'synthetic_plan' })
const fields: Array<keyof Pick<ActionRegisterRow, 'observation' | 'driver' | 'impact' | 'risk' | 'action' | 'owner' | 'due_period' | 'cadence' | 'status'>> = ['observation', 'driver', 'impact', 'risk', 'action', 'owner', 'due_period', 'cadence', 'status']

const optionValues = {
  owner: ['FP&A', 'Commercial', 'Supply Chain', 'Operations', 'Supply Chain Finance', 'Group FP&A'],
  cadence: ['weekly', 'monthly', 'quarterly'],
  status: ['Open', 'In progress', 'Blocked', 'Done'],
}
const fieldLabels: Record<string, TranslationKey> = { observation: 'observation', driver: 'driver', impact: 'impact', risk: 'risk', action: 'action', owner: 'owner', due_period: 'due', cadence: 'cadence', status: 'status' }
const optionLabels: Record<string, TranslationKey> = { Open: 'statusOpen', 'In progress': 'statusInProgress', Blocked: 'statusBlocked', Done: 'statusDone', weekly: 'weekly', monthly: 'monthly', quarterly: 'quarterly', 'FP&A': 'fpa', Commercial: 'commercial', 'Supply Chain': 'supplyChain', Operations: 'operations', 'Supply Chain Finance': 'supplyChainFinance', 'Group FP&A': 'groupFpa' }

export function ActionRegister({ actions, onChange }: { actions: ActionRegisterRow[]; onChange: (actions: ActionRegisterRow[]) => void }) {
  const { t } = useI18n()
  const optionLabel = (value: string) => optionLabels[value] ? t(optionLabels[value]) : value
  const fieldAriaLabel = (field: typeof fields[number], index: number) => `${t(fieldLabels[field])} ${index + 1}`
  const update = (index: number, field: typeof fields[number], value: string) => onChange(actions.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: field === 'impact' ? (value === '' ? null : Number(value)) : value, provenance: 'synthetic_plan' } : item))
  return <section className="panel table-panel" aria-labelledby="action-register-title">
    <div className="section-heading"><div><div className="eyebrow">{t('businessPartnering')}</div><h2 id="action-register-title">{t('actionRegister')}</h2></div><button className="button" type="button" onClick={() => onChange([...actions, blankAction()])}><Plus size={14} /> {t('addAction')}</button></div>
    <div className="synthetic-disclosure">{t('illustrativeActions')}</div>
    <div className="table-scroll" role="region" tabIndex={0} aria-label={t('actionRegister')}><table><thead><tr>{fields.map((field) => <th key={field}>{t(fieldLabels[field])}</th>)}<th>{t('remove')}</th></tr></thead><tbody>{actions.map((row, index) => <tr key={row.action_id}>{fields.map((field) => <td key={field}>{field === 'owner' || field === 'status' || field === 'cadence' ? <select aria-label={fieldAriaLabel(field, index)} value={row[field] || ''} onChange={(event) => update(index, field, event.target.value)}>{[...new Set([...optionValues[field], row[field] || ''])].filter(Boolean).map((item) => <option key={item} value={item}>{optionLabel(item)}</option>)}</select> : <input type={field === 'impact' ? 'number' : 'text'} aria-label={fieldAriaLabel(field, index)} value={row[field] ?? ''} onChange={(event) => update(index, field, event.target.value)} />}</td>)}<td><button className="icon-button" type="button" aria-label={t('removeAction', { number: index + 1 })} onClick={() => onChange(actions.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={14} /></button></td></tr>)}</tbody></table></div>
  </section>
}
