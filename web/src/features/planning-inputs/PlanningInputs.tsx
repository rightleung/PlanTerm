import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, Pencil, RotateCcw, Save, Upload, X } from 'lucide-react'
import { ApiError, fetchOperatingPlan, fetchPlanningTemplate, importPlanningInputs, previewDashboard } from '@/api/client'
import type { BrandFilter, DashboardResponse, MarketFilter, PlanVariant, PlanningInputRow, PlanningInputSource, WorkforceCapacityInputRow, WorkforceCapacityResponse } from '@/types/planning'
import { neutralizeSpreadsheetText, numericSpreadsheetValue } from '@/lib/spreadsheetText'
import { useI18n } from '@/i18n'
import { apiLabel } from '@/i18n/apiLabels'

const CASE_ID = 'miniso-2026'
const HEADERS = ['case_id', 'plan_variant', 'period', 'business_unit', 'category_id', 'volume_change_pct', 'average_ticket_change_pct', 'gross_margin_delta_pp', 'opex_ratio_delta_pp'] as const
type PreviewSource = Exclude<PlanningInputSource, 'seed'>
type WorkforceRowsByVariant = Record<PlanVariant, WorkforceCapacityInputRow[]>
export interface PlanningSession { rows: PlanningInputRow[]; variant: PlanVariant; source: PreviewSource; headcountRows: WorkforceCapacityInputRow[]; headcountRowsByVariant?: WorkforceRowsByVariant }

function emptyWorkforceRows(): WorkforceRowsByVariant {
  return { base: [], upside: [], downside: [] }
}

function workforceInputRows(capacity: WorkforceCapacityResponse | null | undefined, variant: PlanVariant): WorkforceCapacityInputRow[] {
  return (capacity?.headcount_rows || []).filter((row) => row.plan_variant === variant && /^2026-(0[7-9]|1[0-2])$/.test(row.period)).map((row) => ({
    case_id: row.case_id,
    plan_variant: variant,
    period: row.period,
    business_unit: row.business_unit,
    role_group: row.role_group,
    planned_fte: row.planned_fte,
    monthly_loaded_cost: row.monthly_loaded_cost,
    provenance: 'synthetic_plan' as const,
  }))
}

export function parsePlanningInputCsv(csv: string): PlanningInputRow[] {
  const text = csv.replace(/^\uFEFF/, ''); const records: string[][] = []; let row: string[] = []; let field = ''; let quoted = false
  for (let i = 0; i < text.length; i += 1) { const c = text[i]; const n = text[i + 1]; if (c === '"') { if (quoted && n === '"') { field += '"'; i += 1 } else quoted = !quoted } else if (c === ',' && !quoted) { row.push(field); field = '' } else if ((c === '\n' || c === '\r') && !quoted) { if (c === '\r' && n === '\n') i += 1; row.push(field); if (row.some((value) => value !== '')) records.push(row); row = []; field = '' } else field += c }
  if (quoted) throw new Error('Malformed CSV: unterminated quoted field'); if (field !== '' || row.length) { row.push(field); records.push(row) }
  if (records.length < 2 || records[0].length !== HEADERS.length || records[0].some((value, index) => value !== HEADERS[index])) throw new Error('Template header mismatch')
  const driverFields = ['volume_change_pct', 'average_ticket_change_pct', 'gross_margin_delta_pp', 'opex_ratio_delta_pp'] as const
  return records.slice(1).map((values) => { if (values.length !== HEADERS.length) throw new Error('Invalid CSV row shape'); const [case_id, plan_variant, period, business_unit, category_id, volume, ticket, gm, opex] = values; let drivers: number[]; try { drivers = [volume, ticket, gm, opex].map((value, index) => numericSpreadsheetValue(value, driverFields[index])) } catch { throw new Error('Invalid CSV row values') } if (!case_id || !period || !business_unit || !category_id || !['base', 'upside', 'downside'].includes(plan_variant)) throw new Error('Invalid CSV row values'); return { case_id, plan_variant: plan_variant as PlanVariant, period, business_unit, category_id, volume_change_pct: drivers[0], average_ticket_change_pct: drivers[1], gross_margin_delta_pp: drivers[2], opex_ratio_delta_pp: drivers[3] } })
}

const NUMERIC_FIELDS = new Set<keyof PlanningInputRow>(['volume_change_pct', 'average_ticket_change_pct', 'gross_margin_delta_pp', 'opex_ratio_delta_pp'])
export function csvFromRows(rows: PlanningInputRow[]) {
  const escape = (value: string | number) => `"${String(value).replaceAll('"', '""')}"`
  return [HEADERS.join(','), ...rows.map((row) => HEADERS.map((key) => {
    const value = row[key] as string | number
    return escape(NUMERIC_FIELDS.has(key) ? numericSpreadsheetValue(value, key) : neutralizeSpreadsheetText(String(value)))
  }).join(','))].join('\n')
}
function diagnostics(reason: unknown) { if (!(reason instanceof ApiError) || !Array.isArray(reason.details.diagnostics)) return []; return reason.details.diagnostics.slice(0, 50).map((item) => typeof item === 'object' && item !== null ? JSON.stringify(item) : String(item)) }

export function PlanningInputs({ dashboard, brand, market, session, workforceCapacity, onPreview, onDiscardAll }: { dashboard: DashboardResponse | null; brand: BrandFilter; market: MarketFilter; session: PlanningSession | null; workforceCapacity?: WorkforceCapacityResponse | null; onPreview: (next: DashboardResponse, nextSession: PlanningSession) => void; onDiscardAll: () => void }) {
  const { t, formatNumber } = useI18n()
  const [open, setOpen] = useState(false); const [variant, setVariant] = useState<PlanVariant>('base'); const [rows, setRows] = useState<PlanningInputRow[]>([]); const [headcountRows, setHeadcountRows] = useState<WorkforceCapacityInputRow[]>([]); const [headcountRowsByVariant, setHeadcountRowsByVariant] = useState<WorkforceRowsByVariant>(emptyWorkforceRows); const [source, setSource] = useState<PreviewSource>('editor'); const [error, setError] = useState<string | null>(null); const [errorDiagnostics, setErrorDiagnostics] = useState<string[]>([]); const [busy, setBusy] = useState(false)
  const requestId = useRef(0); const controllerRef = useRef<AbortController | null>(null); const fileRef = useRef<HTMLInputElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null); const previousFocusRef = useRef<HTMLElement | null>(null)
  const visibleRows = useMemo(() => rows.filter((row) => row.plan_variant === variant), [rows, variant])
  const visibleHeadcountRows = useMemo(() => headcountRows.filter((row) => row.plan_variant === variant), [headcountRows, variant])
  useEffect(() => { if (session?.variant) setVariant(session.variant) }, [session?.variant])
  useEffect(() => {
    if (!open) return undefined
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    closeButtonRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false); return }
      if (event.key !== 'Tab') return
      const dialog = document.querySelector('.planning-dialog')
      if (!dialog) return
      const focusable = [...dialog.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
      if (focusable.length === 0) return
      const current = document.activeElement
      const index = focusable.indexOf(current as HTMLElement)
      const next = event.shiftKey ? (index <= 0 ? focusable.length - 1 : index - 1) : (index === focusable.length - 1 ? 0 : index + 1)
      event.preventDefault(); focusable[next].focus()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => { document.removeEventListener('keydown', onKeyDown); previousFocusRef.current?.focus() }
  }, [open])
  const showError = (reason: unknown, fallback: string) => { setError(reason instanceof Error ? reason.message : fallback); setErrorDiagnostics(diagnostics(reason)) }
  const openEditor = async () => { setOpen(true); setError(null); setErrorDiagnostics([]); if (session) { const storedRows = session.headcountRowsByVariant || { ...emptyWorkforceRows(), [session.variant]: session.headcountRows }; setRows(session.rows); setHeadcountRows(session.headcountRows); setHeadcountRowsByVariant(storedRows); setVariant(session.variant); setSource(session.source); return }; setBusy(true); controllerRef.current?.abort(); const id = ++requestId.current; const controller = new AbortController(); controllerRef.current = controller; try { const variants: PlanVariant[] = ['base', 'upside', 'downside']; const capacityPromises = variants.map((item) => workforceCapacity?.plan_variant === item ? Promise.resolve(workforceCapacity) : fetchOperatingPlan(CASE_ID, item, controller.signal).then((plan) => plan.workforce_capacity || plan.headcount_capacity || null)); const [csv, ...capacities] = await Promise.all([fetchPlanningTemplate(CASE_ID, controller.signal), ...capacityPromises]); const parsed = parsePlanningInputCsv(csv); const rowsByVariant = { base: workforceInputRows(capacities[0], 'base'), upside: workforceInputRows(capacities[1], 'upside'), downside: workforceInputRows(capacities[2], 'downside') }; if (id === requestId.current) { setRows(parsed); setHeadcountRows(rowsByVariant.base); setHeadcountRowsByVariant(rowsByVariant); setVariant('base'); setSource('editor') } } catch (reason) { if (id === requestId.current && (reason as Error).name !== 'AbortError') showError(reason, t('templateLoadFailed')) } finally { if (id === requestId.current) setBusy(false) } }
  const download = () => { if (!rows.length) return; const blob = new Blob([csvFromRows(rows)], { type: 'text/csv;charset=utf-8' }); const anchor = document.createElement('a'); anchor.href = URL.createObjectURL(blob); anchor.download = 'PlanTerm_planning_inputs.csv'; anchor.click(); URL.revokeObjectURL(anchor.href) }
  const upload = async (file?: File) => { if (!file) return; controllerRef.current?.abort(); const id = ++requestId.current; const controller = new AbortController(); controllerRef.current = controller; setBusy(true); setError(null); setErrorDiagnostics([]); try { const result = await importPlanningInputs(CASE_ID, await file.text(), controller.signal); if (id === requestId.current) { setRows(result.rows); setSource('upload') } } catch (reason) { if (id === requestId.current && (reason as Error).name !== 'AbortError') showError(reason, t('uploadFailed')) } finally { if (id === requestId.current) setBusy(false) } }
  const edit = (row: PlanningInputRow, field: keyof Pick<PlanningInputRow, 'volume_change_pct' | 'average_ticket_change_pct' | 'gross_margin_delta_pp' | 'opex_ratio_delta_pp'>, value: string) => { setSource('editor'); setRows((current) => current.map((item) => item === row ? { ...item, [field]: Number(value) } : item)) }
  const editHeadcount = (row: WorkforceCapacityInputRow, field: keyof Pick<WorkforceCapacityInputRow, 'planned_fte' | 'monthly_loaded_cost'>, value: string) => { const numeric = value === '' ? 0 : Number(value); const matches = (item: WorkforceCapacityInputRow) => item.case_id === row.case_id && item.plan_variant === row.plan_variant && item.period === row.period && item.business_unit === row.business_unit && item.role_group === row.role_group; setHeadcountRows((current) => current.map((item) => matches(item) ? { ...item, [field]: numeric } : item)); setHeadcountRowsByVariant((current) => ({ ...current, [variant]: current[variant].map((item) => matches(item) ? { ...item, [field]: numeric } : item) })) }
  const selectVariant = (nextVariant: PlanVariant) => { setVariant(nextVariant); setHeadcountRows(headcountRowsByVariant[nextVariant]) }
  const apply = async () => { if (rows.length !== 252 || visibleHeadcountRows.length !== 72 || rows.some((row) => [row.volume_change_pct, row.average_ticket_change_pct, row.gross_margin_delta_pp, row.opex_ratio_delta_pp].some((value) => !Number.isFinite(value))) || headcountRows.some((row) => [row.planned_fte, row.monthly_loaded_cost].some((value) => !Number.isFinite(value)))) { setError(t('completeMatrixError')); return } setBusy(true); setError(null); setErrorDiagnostics([]); controllerRef.current?.abort(); const id = ++requestId.current; const controller = new AbortController(); controllerRef.current = controller; try { const nextSession = { rows, variant, source, headcountRows, headcountRowsByVariant: { ...headcountRowsByVariant, [variant]: headcountRows } }; const result = await previewDashboard(CASE_ID, rows, variant, source, brand, market, controller.signal); if (id === requestId.current) { onPreview(result, nextSession); setOpen(false) } } catch (reason) { if (id === requestId.current && (reason as Error).name !== 'AbortError') showError(reason, t('previewFailed')) } finally { if (id === requestId.current) setBusy(false) } }
  const discardAll = () => { controllerRef.current?.abort(); requestId.current += 1; setOpen(false); setRows([]); setHeadcountRows([]); setHeadcountRowsByVariant(emptyWorkforceRows()); setError(null); setErrorDiagnostics([]); onDiscardAll() }
  const context = dashboard?.category_detail_context || []
  return <><div className="planning-toolbar"><div><strong>{t('planningInputs')}</strong><span>{t('h2DriversLocked')}</span></div><button className="button button-primary" onClick={() => void openEditor()}><Pencil size={14} /> {t('openEditor')}</button></div>
    {open && <div className="dialog-backdrop"><div className="planning-dialog" role="dialog" aria-modal="true" aria-labelledby="planning-dialog-title" aria-describedby="planning-dialog-description"><div className="dialog-header"><div><h2 id="planning-dialog-title">{t('planningInputs')}</h2><p id="planning-dialog-description">{t('completeMatrix')}</p></div><button ref={closeButtonRef} className="icon-button" onClick={() => setOpen(false)} aria-label={t('close')}><X size={16} /></button></div>
      <div className="synthetic-disclosure">{t('syntheticCategoryDisclosure')}</div>
      <div className="planning-actions"><div className="variant-tabs" role="tablist" aria-label={t('planVariant')}>{(['base', 'upside', 'downside'] as PlanVariant[]).map((item) => <button aria-pressed={variant === item} key={item} className={variant === item ? 'active' : ''} onClick={() => selectVariant(item)}>{apiLabel(item, t)}</button>)}</div><button className="button" onClick={download} disabled={!rows.length}><Download size={14} /> {t('downloadCsv')}</button><button className="button" onClick={() => fileRef.current?.click()}><Upload size={14} /> {t('uploadCsv')}</button><input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={(event) => void upload(event.target.files?.[0])} /></div>
      <div className="locked-note">{t('lockedHorizonEditable', { count: formatNumber(visibleRows.length), variant: apiLabel(variant, t), workforce: formatNumber(visibleHeadcountRows.length) })}</div>
      <div className="planning-content-scroll">
        {error && <div className="inline-error" role="alert"><div>{error}</div>{errorDiagnostics.length > 0 && <ul>{errorDiagnostics.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>}</div>}
        {context.length > 0 && <div className="context-scroll" role="region" tabIndex={0} aria-label={t('lockedContext')}><table className="planning-context"><caption>{t('lockedContext')}</caption><thead><tr><th>{t('businessUnit')}</th><th>{t('category')}</th><th>{t('h1ActualRevenue')}</th><th>{t('priorYearRevenue')}</th><th>{t('fyBudgetRevenue')}</th><th>{t('basis')}</th></tr></thead><tbody>{context.map((item) => <tr key={`${item.business_unit}-${item.category_id}`}><td>{apiLabel(item.business_unit, t)}</td><td>{apiLabel(item.category_name, t)}</td><td>{formatNumber(item.h1_actual.revenue)}</td><td>{formatNumber(item.h1_prior_year.revenue)}</td><td>{formatNumber(item.fy_budget.revenue)}</td><td>{t('syntheticAllocation')}</td></tr>)}</tbody></table></div>}
        <div className="matrix-scroll" role="region" tabIndex={0} aria-label={t('planningInputs')}><table className="planning-matrix"><thead><tr><th>{t('period')}</th><th>{t('businessUnit')}</th><th>{t('category')}</th><th>{t('volumePercent')}</th><th>{t('ticketPercent')}</th><th>{t('gmDeltaPp')}</th><th>{t('opexDeltaPp')}</th></tr></thead><tbody>{visibleRows.map((row) => <tr key={`${row.plan_variant}-${row.period}-${row.business_unit}-${row.category_id}`}><td>{row.period}</td><td>{apiLabel(row.business_unit, t)}</td><td>{row.category_name ? apiLabel(row.category_name, t) : row.category_id}</td>{(['volume_change_pct', 'average_ticket_change_pct', 'gross_margin_delta_pp', 'opex_ratio_delta_pp'] as const).map((field) => <td key={field}><input type="number" step="0.000001" value={row[field]} onChange={(event) => edit(row, field, event.target.value)} aria-label={`${field} ${row.period} ${row.category_id}`} /></td>)}</tr>)}</tbody></table></div>
        <div className="matrix-scroll" role="region" tabIndex={0} aria-label={t('h2WorkforceInputs')}><table className="planning-matrix workforce-input-matrix"><caption>{t('h2WorkforceInputs')}</caption><thead><tr><th>{t('period')}</th><th>{t('businessUnit')}</th><th>{t('roleGroup')}</th><th>{t('plannedFte')}</th><th>{t('monthlyLoadedCost')}</th><th>{t('provenance')}</th></tr></thead><tbody>{visibleHeadcountRows.map((row) => <tr key={`${row.plan_variant}-${row.period}-${row.business_unit}-${row.role_group}`}><td>{row.period}</td><td>{apiLabel(row.business_unit, t)}</td><td>{apiLabel(row.role_group, t)}</td><td><input type="number" min="0" step="1" value={row.planned_fte} onChange={(event) => editHeadcount(row, 'planned_fte', event.target.value)} aria-label={`planned_fte ${row.period} ${row.business_unit} ${row.role_group}`} /></td><td><input type="number" min="0" step="0.001" value={row.monthly_loaded_cost} onChange={(event) => editHeadcount(row, 'monthly_loaded_cost', event.target.value)} aria-label={`monthly_loaded_cost ${row.period} ${row.business_unit} ${row.role_group}`} /></td><td>{apiLabel(row.provenance, t)}</td></tr>)}</tbody></table></div>
      </div>
      <div className="dialog-footer"><button className="button button-ghost" onClick={discardAll}><RotateCcw size={14} /> {t('discardAll')}</button><button className="button button-primary" onClick={() => void apply()} disabled={busy || rows.length !== 252 || visibleHeadcountRows.length !== 72}><Save size={14} /> {busy ? t('validating') : t('applyPreview')}</button></div>
    </div></div>}</>
}
