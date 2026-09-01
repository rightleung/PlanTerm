import { Plus } from 'lucide-react'
import { useState } from 'react'
import type { DecisionLogRow } from '@/types/planning'

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

function displayValue(value: DecisionLogRow[keyof DecisionLogRow]) {
  if (value === null || value === undefined || value === '') return 'Not available'
  if (Array.isArray(value)) {
    return value.map((item) => typeof item === 'string' ? item : `${item.metric}: ${item.formula} · ${item.source} · ${item.reconciliation_status}`).join(' | ')
  }
  return value
}

export function DecisionLog({ rows, onChange }: { rows: DecisionLogRow[]; onChange: (rows: DecisionLogRow[]) => void }) {
  const [draft, setDraft] = useState<DecisionLogRow>(blankDecision)
  const updateDraft = <K extends keyof DecisionLogRow>(field: K, value: DecisionLogRow[K]) => setDraft((current) => ({ ...current, [field]: value }))
  const canAdd = requiredTextFields.every((field) => typeof draft[field] === 'string' && draft[field].trim().length > 0)
  const addDecision = () => {
    if (!canAdd) return
    onChange([...rows, { ...draft, decision_id: nextDecisionId(rows), context: draft.context.trim(), decision: draft.decision.trim(), rationale: draft.rationale.trim() }])
    setDraft(blankDecision())
  }

  return <section className="panel table-panel" aria-labelledby="decision-log-title">
    <div className="section-heading"><div><div className="eyebrow">Governance</div><h2 id="decision-log-title">Decision log</h2></div><span className="unit-note">Session-only · immutable events</span></div>
    <div className="synthetic-disclosure">Added events remain in this browser session only. Existing events are read-only and cannot be edited.</div>
    <div className="table-scroll"><table><thead><tr><th>Decision ID</th>{fields.map((field) => <th key={field}>{field.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{rows.length === 0 ? <tr><td colSpan={fields.length + 1}>No decisions recorded in this session.</td></tr> : rows.map((row) => <tr key={row.decision_id}><td className="table-primary">{row.decision_id}</td>{fields.map((field) => <td key={field}>{displayValue(row[field])}</td>)}</tr>)}</tbody></table></div>
    <div className="decision-form" aria-label="Add decision">
      <h3>Add decision</h3>
      <div className="form-grid">{fields.map((field) => field === 'status' ? <label key={field}>{field.replaceAll('_', ' ')}<select value={draft.status} onChange={(event) => updateDraft('status', event.target.value as DecisionLogRow['status'])}>{statuses.map((status) => <option key={status}>{status}</option>)}</select></label> : <label key={field}>{field.replaceAll('_', ' ')}{field === 'context' || field === 'options' || field === 'decision' || field === 'rationale' || field === 'affected_contracts' || field === 'evidence' ? <textarea rows={2} value={typeof draft[field] === 'string' ? draft[field] : ''} onChange={(event) => updateDraft(field, event.target.value as never)} /> : <input type={field === 'date' ? 'date' : 'text'} value={typeof draft[field] === 'string' ? draft[field] : ''} onChange={(event) => updateDraft(field, event.target.value as never)} />}</label>)}</div>
      <button className="button button-primary" type="button" onClick={addDecision} disabled={!canAdd}><Plus size={14} /> Add decision</button>
    </div>
  </section>
}
