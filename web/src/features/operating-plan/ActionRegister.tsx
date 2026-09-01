import { Plus, Trash2 } from 'lucide-react'
import type { ActionRegisterRow } from '@/types/planning'

const blankAction = (): ActionRegisterRow => ({ action_id: `session-${Date.now()}`, observation: '', driver: '', impact: null, risk: '', action: '', owner: 'FP&A', due_period: '', cadence: 'monthly', status: 'Open', provenance: 'synthetic_plan' })
const fields: Array<keyof Pick<ActionRegisterRow, 'observation' | 'driver' | 'impact' | 'risk' | 'action' | 'owner' | 'due_period' | 'cadence' | 'status'>> = ['observation', 'driver', 'impact', 'risk', 'action', 'owner', 'due_period', 'cadence', 'status']

const optionValues = {
  owner: ['FP&A', 'Commercial', 'Supply Chain', 'Operations', 'Supply Chain Finance', 'Group FP&A'],
  cadence: ['weekly', 'monthly', 'quarterly'],
  status: ['Open', 'In progress', 'Blocked', 'Done'],
}

export function ActionRegister({ actions, onChange }: { actions: ActionRegisterRow[]; onChange: (actions: ActionRegisterRow[]) => void }) {
  const update = (index: number, field: typeof fields[number], value: string) => onChange(actions.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: field === 'impact' ? (value === '' ? null : Number(value)) : value, provenance: 'synthetic_plan' } : item))
  return <section className="panel table-panel" aria-labelledby="action-register-title">
    <div className="section-heading"><div><div className="eyebrow">Business partnering</div><h2 id="action-register-title">Action register</h2></div><button className="button" type="button" onClick={() => onChange([...actions, blankAction()])}><Plus size={14} /> Add action</button></div>
    <div className="synthetic-disclosure">Illustrative actions stay in this browser session only and are never persisted.</div>
    <div className="table-scroll"><table><thead><tr><th>Observation</th><th>Driver</th><th>Impact</th><th>Risk</th><th>Action</th><th>Owner</th><th>Due</th><th>Cadence</th><th>Status</th><th>Remove</th></tr></thead><tbody>{actions.map((row, index) => <tr key={row.action_id}>{fields.map((field) => <td key={field}>{field === 'owner' || field === 'status' || field === 'cadence' ? <select aria-label={`${field} action ${index + 1}`} value={row[field] || ''} onChange={(event) => update(index, field, event.target.value)}>{[...new Set([...optionValues[field], row[field] || ''])].filter(Boolean).map((item) => <option key={item}>{item}</option>)}</select> : <input type={field === 'impact' ? 'number' : 'text'} aria-label={`${field} action ${index + 1}`} value={row[field] ?? ''} onChange={(event) => update(index, field, event.target.value)} />}</td>)}<td><button className="icon-button" type="button" aria-label={`Remove action ${index + 1}`} onClick={() => onChange(actions.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={14} /></button></td></tr>)}</tbody></table></div>
  </section>
}
