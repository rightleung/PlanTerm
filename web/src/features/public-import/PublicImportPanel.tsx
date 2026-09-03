import { useState, type FormEvent } from 'react'
import { Search } from 'lucide-react'
import { ApiError, previewPublicImport } from '@/api/client'
import { apiErrorLabel, apiLabel } from '@/i18n/apiLabels'
import { useI18n } from '@/i18n'
import type { PublicImportPreview, PublicImportRequest } from '@/types/planning'

type Exchange = PublicImportRequest['exchange']
type Venue = NonNullable<PublicImportRequest['venue']>
type Periods = NonNullable<PublicImportRequest['periods']>

const exchanges: Array<{ value: Exchange; label: 'exchangeLse' | 'exchangeAShare' | 'exchangeHkex' | 'exchangeUs' }> = [
  { value: 'LSE', label: 'exchangeLse' },
  { value: 'A_SHARE', label: 'exchangeAShare' },
  { value: 'HKEX', label: 'exchangeHkex' },
  { value: 'US', label: 'exchangeUs' },
]
const venues: Array<{ value: Venue; label: 'venueSse' | 'venueSzse' }> = [
  { value: 'SSE', label: 'venueSse' },
  { value: 'SZSE', label: 'venueSzse' },
]

function localizeDisclosure(disclosure: string, t: (key: 'publicOnly' | 'notInternal' | 'noFx') => string) {
  const normalized = disclosure.toLowerCase()
  if (normalized.includes('not internal')) return t('notInternal')
  if (normalized.includes('no fx')) return t('noFx')
  if (normalized.includes('public reported')) return t('publicOnly')
  return disclosure
}

function formatValue(value: number | null, currency: string, unit: string, formatNumber: (value: number | null | undefined) => string) {
  return value === null ? '—' : `${formatNumber(value)} ${currency} · ${unit}`
}

export function PublicImportPanel() {
  const { t, formatDate, formatNumber } = useI18n()
  const [exchange, setExchange] = useState<Exchange>('US')
  const [venue, setVenue] = useState<Venue>('SSE')
  const [ticker, setTicker] = useState('')
  const [periods, setPeriods] = useState<Periods>('both')
  const [preview, setPreview] = useState<PublicImportPreview | null>(null)
  const [errorType, setErrorType] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    setErrorType(null)
    setPreview(null)
    const request: PublicImportRequest = { exchange, ticker, periods, ...(exchange === 'A_SHARE' ? { venue } : {}) }
    try {
      setPreview(await previewPublicImport(request))
    } catch (reason) {
      setErrorType(reason instanceof ApiError ? reason.errorType : 'request_error')
    } finally {
      setBusy(false)
    }
  }

  return <section className="panel public-import-panel" aria-labelledby="public-import-title">
    <div className="section-heading"><div><div className="eyebrow">{t('publicData')}</div><h2 id="public-import-title">{t('publicImport')}</h2></div><span className="unit-note">{t('publicOnly')}</span></div>
    <p className="panel-footnote">{t('publicImportDescription')}</p>
    <form className="public-import-form" onSubmit={(event) => void submit(event)}>
      <label><span>{t('exchange')}</span><select value={exchange} onChange={(event) => setExchange(event.target.value as Exchange)} aria-label={t('exchange')}>{exchanges.map((item) => <option key={item.value} value={item.value}>{t(item.label)}</option>)}</select></label>
      {exchange === 'A_SHARE' && <><label><span>{t('venue')}</span><select value={venue} onChange={(event) => setVenue(event.target.value as Venue)} aria-label={t('venue')}>{venues.map((item) => <option key={item.value} value={item.value}>{t(item.label)}</option>)}</select></label><span className="public-import-venue-note">{t('venueBseUnavailable')}</span></>}
      <label><span>{t('ticker')}</span><input value={ticker} onChange={(event) => setTicker(event.target.value)} placeholder={t('publicImportTickerPlaceholder')} maxLength={24} required aria-label={t('ticker')} /></label>
      <label><span>{t('periodSelection')}</span><select value={periods} onChange={(event) => setPeriods(event.target.value as Periods)} aria-label={t('periodSelection')}><option value="annual">{t('annual')}</option><option value="quarterly">{t('quarterly')}</option><option value="both">{t('both')}</option></select></label>
      <button className="button button-primary" type="submit" disabled={busy || !ticker.trim()}><Search size={14} /> {busy ? t('previewLoading') : t('submitPreview')}</button>
    </form>
    {errorType && <div className="inline-error" role="alert">{apiErrorLabel(errorType, t)}</div>}
    {preview && <div className="public-import-results" aria-labelledby="public-import-results-title">
      <div className="section-heading"><h3 id="public-import-results-title">{t('previewResults')}</h3><span className="unit-note">{preview.company.currency || t('nativeCurrency')} · {preview.request.normalized_symbol}</span></div>
      <div className="synthetic-disclosure">{t('notInternal')} {t('noFx')}</div>
      <div className="table-scroll" role="region" tabIndex={0} aria-label={t('statements')}><table><thead><tr><th>{t('period')}</th><th>{t('statements')}</th><th>{t('unit')}</th><th>{t('source')}</th></tr></thead><tbody>{preview.statements.length === 0 ? <tr><td colSpan={4}>{t('noStatements')}</td></tr> : preview.statements.map((statement) => <tr key={`${statement.period_end}-${statement.period_type}`}><td>{formatDate(statement.period_end)} · {statement.period_type === 'annual' ? t('annual') : t('quarterly')}</td><td>{Object.entries(statement.values).map(([key, value]) => <div key={key}><span>{apiLabel(key, t)}: </span>{formatValue(value, statement.currency, statement.unit, formatNumber)}</div>)}</td><td>{statement.currency} · {statement.unit}</td><td><a href={statement.source.url} target="_blank" rel="noreferrer">{statement.source.provider}</a><small>{t('retrieved')}: {formatDate(statement.source.retrieved_at.slice(0, 10))}{statement.source.as_of ? ` · ${t('asOf')}: ${formatDate(statement.source.as_of)}` : ''}</small></td></tr>)}</tbody></table></div>
      <div className="public-import-disclosures">{preview.disclosures.map((disclosure) => <span key={disclosure}>{localizeDisclosure(disclosure, t)}</span>)}</div>
    </div>}
  </section>
}
