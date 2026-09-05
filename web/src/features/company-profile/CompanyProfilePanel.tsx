import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Search } from 'lucide-react'
import { ApiError, lookupCompanyProfile, searchCompanySymbols } from '@/api/client'
import { apiErrorLabel, apiLabel } from '@/i18n/apiLabels'
import { useI18n } from '@/i18n'
import type { CompanyLookupRequest, CompanyLookupResponse, SymbolSearchResult } from '@/types/planning'

type MarketSelection = 'AUTO' | NonNullable<CompanyLookupRequest['exchange']>

function valueOrFallback(value: string | number | null | undefined, fallback: string) {
  return value === null || value === undefined || value === '' ? fallback : String(value)
}

export function CompanyProfilePanel() {
  const { t, formatNumber, formatDate } = useI18n()
  const [ticker, setTicker] = useState('')
  const [market, setMarket] = useState<MarketSelection>('AUTO')
  const [venue, setVenue] = useState<NonNullable<CompanyLookupRequest['venue']>>('SSE')
  const [suggestions, setSuggestions] = useState<SymbolSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [activeSuggestion, setActiveSuggestion] = useState(-1)
  const [result, setResult] = useState<CompanyLookupResponse | null>(null)
  const [errorType, setErrorType] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const searchRequest = useRef<AbortController | null>(null)
  const searchRequestId = useRef(0)

  useEffect(() => {
    const query = ticker.trim()
    const requestId = ++searchRequestId.current
    searchRequest.current?.abort()
    setActiveSuggestion(-1)
    if (!query) {
      setSuggestions([])
      setSearching(false)
      return undefined
    }
    const controller = new AbortController()
    searchRequest.current = controller
    setSearching(true)
    const timer = window.setTimeout(() => {
      searchCompanySymbols(query, market === 'AUTO' ? undefined : market, market === 'A_SHARE' ? venue : undefined, controller.signal)
        .then((response) => { if (requestId === searchRequestId.current && !controller.signal.aborted) setSuggestions(response.results) })
        .catch((reason: unknown) => { if (requestId === searchRequestId.current && (reason as Error).name !== 'AbortError') setSuggestions([]) })
        .finally(() => { if (requestId === searchRequestId.current && !controller.signal.aborted) setSearching(false) })
    }, 300)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [ticker, market, venue])

  const selectSuggestion = (suggestion: SymbolSearchResult) => {
    setTicker(suggestion.symbol)
    setMarket(suggestion.exchange)
    if (suggestion.venue) setVenue(suggestion.venue)
    setSuggestions([])
    setActiveSuggestion(-1)
  }

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!suggestions.length) return
    if (event.key === 'ArrowDown') { event.preventDefault(); setActiveSuggestion((current) => Math.min(current + 1, suggestions.length - 1)) }
    if (event.key === 'ArrowUp') { event.preventDefault(); setActiveSuggestion((current) => Math.max(current - 1, 0)) }
    if (event.key === 'Escape') { setSuggestions([]); setActiveSuggestion(-1) }
    if (event.key === 'Enter' && activeSuggestion >= 0) { event.preventDefault(); selectSuggestion(suggestions[activeSuggestion]) }
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    setErrorType(null)
    setResult(null)
    try {
      setSuggestions([])
      setResult(await lookupCompanyProfile({ ticker: ticker.trim(), ...(market === 'AUTO' ? {} : { exchange: market }), ...(market === 'A_SHARE' ? { venue } : {}) }))
    } catch (reason) {
      setErrorType(reason instanceof ApiError ? reason.errorType : 'request_error')
    } finally {
      setBusy(false)
    }
  }

  return <section className="panel company-profile-panel" aria-labelledby="company-profile-title">
    <div className="section-heading"><div><div className="eyebrow">{t('companyLookupEyebrow')}</div><h2 id="company-profile-title">{t('companyLookup')}</h2></div><span className="unit-note">{t('publicOnly')}</span></div>
    <p className="panel-footnote">{t('companyLookupDescription')}</p>
    <form className="company-profile-form" onSubmit={(event) => void submit(event)} aria-busy={busy || searching}>
      <label><span>{t('companyMarket')}</span><select value={market} onChange={(event) => setMarket(event.target.value as MarketSelection)} aria-label={t('companyMarketSelector')}><option value="AUTO">{t('companyMarketAuto')}</option><option value="US">{t('exchangeUs')}</option><option value="HKEX">{t('exchangeHkex')}</option><option value="LSE">{t('exchangeLse')}</option><option value="A_SHARE">{t('exchangeAShare')}</option></select></label>
      {market === 'A_SHARE' && <label><span>{t('venue')}</span><select value={venue} onChange={(event) => setVenue(event.target.value as NonNullable<CompanyLookupRequest['venue']>)} aria-label={t('venue')}><option value="SSE">{t('venueSse')}</option><option value="SZSE">{t('venueSzse')}</option></select></label>}
      <label className="company-ticker-field"><span>{t('ticker')}</span><input role="combobox" aria-autocomplete="list" aria-expanded={suggestions.length > 0} aria-controls="company-symbol-suggestions" aria-activedescendant={activeSuggestion >= 0 ? `company-symbol-${activeSuggestion}` : undefined} value={ticker} onChange={(event) => setTicker(event.target.value)} onKeyDown={handleInputKeyDown} placeholder={t('companyLookupPlaceholder')} maxLength={24} required aria-label={t('ticker')} />
        {suggestions.length > 0 && <div id="company-symbol-suggestions" className="company-suggestions" role="listbox" aria-label={t('companySuggestions')}>{suggestions.map((suggestion, index) => <button id={`company-symbol-${index}`} role="option" aria-selected={activeSuggestion === index} className={activeSuggestion === index ? 'active' : ''} type="button" key={`${suggestion.exchange}-${suggestion.venue || ''}-${suggestion.symbol}`} onMouseDown={(event) => event.preventDefault()} onClick={() => selectSuggestion(suggestion)}><strong>{suggestion.symbol}</strong><span>{suggestion.name}</span><small>{apiLabel(suggestion.exchange, t)}{suggestion.venue ? ` · ${suggestion.venue}` : ''}</small></button>)}</div>}
      </label>
      <button className="button button-primary" type="submit" disabled={busy || !ticker.trim()}><Search size={14} /> {busy ? t('companyLookupLoading') : t('companyLookupSubmit')}</button>
    </form>
    {searching && <div className="company-search-status" role="status">{t('companySearching')}</div>}
    {errorType && <div className="inline-error" role="alert">{apiErrorLabel(errorType, t)}</div>}
    {result && <div className="company-profile-result" aria-live="polite">
      <div className="company-profile-heading"><div><h3>{result.profile.name}</h3><span>{result.profile.symbol} · {apiLabel(result.profile.exchange, t)}{result.profile.venue ? ` · ${result.profile.venue}` : ''}</span></div><strong>{valueOrFallback(result.profile.currency, t('notAvailable'))}</strong></div>
      {result.profile.description && <p className="company-profile-description">{result.profile.description}</p>}
      <dl className="company-profile-grid">
        <div><dt>{t('companyCountry')}</dt><dd>{valueOrFallback(result.profile.country, t('notAvailable'))}</dd></div>
        <div><dt>{t('companySector')}</dt><dd>{valueOrFallback(result.profile.sector, t('notAvailable'))}</dd></div>
        <div><dt>{t('companyIndustry')}</dt><dd>{valueOrFallback(result.profile.industry, t('notAvailable'))}</dd></div>
        <div><dt>{t('companyEmployees')}</dt><dd>{result.profile.employees == null ? t('notAvailable') : formatNumber(result.profile.employees, { maximumFractionDigits: 0 })}</dd></div>
        <div><dt>{t('companyMarketCap')}</dt><dd>{result.profile.market_cap == null ? t('notAvailable') : `${formatNumber(result.profile.market_cap)} ${result.profile.market_cap_currency || ''}`}</dd></div>
        <div><dt>{t('companyWebsite')}</dt><dd>{result.profile.website ? <a href={result.profile.website} target="_blank" rel="noreferrer">{result.profile.website}</a> : t('notAvailable')}</dd></div>
      </dl>
      <div className="company-profile-source">{t('companySource')}: {result.source.provider} · {formatDate(result.source.retrieved_at.slice(0, 10))}</div>
      <div className="public-import-disclosures">{result.disclosures.map((disclosure) => <span key={disclosure}>{disclosure.toLowerCase().includes('not internal') ? t('notInternal') : disclosure.toLowerCase().includes('delayed') ? t('publicDataMayChange') : disclosure}</span>)}</div>
    </div>}
  </section>
}
