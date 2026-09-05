import type { Locale } from './index'
const labels: Record<string, keyof import('./locales/en').EnglishCatalog> = {
  revenue: 'revenueActual', gross_profit: 'grossProfit', operating_profit: 'operatingProfit', operating_margin: 'operatingMargin',
  favorable: 'favorable', unfavorable: 'unfavorable', neutral: 'neutral',
  Volume: 'volume', Mix: 'mix', Price: 'price', 'PVM profit effect': 'pvmProfitEffect', 'Gross Margin': 'grossMargin', Opex: 'opex',
  public_reported: 'publicReported', synthetic_allocation: 'syntheticAllocation', synthetic_plan: 'syntheticPlan', calculated: 'calculated',
  base: 'basePlan', upside: 'upsidePlan', downside: 'downsidePlan',
  mainland: 'chineseMainland', overseas: 'overseas', global: 'globalTopToy',
  'MINISO - Chinese Mainland': 'businessUnitChineseMainland', 'MINISO - Overseas': 'businessUnitOverseas', 'TOP TOY - Global': 'businessUnitGlobalTopToy',
  'MINISO FP&A Portfolio MVP': 'minisoPortfolioMvp', Portfolio: 'portfolio',
  'IP & Toys': 'categoryIpToys', 'Home & Lifestyle': 'categoryHomeLifestyle', 'Beauty & Personal Care': 'categoryBeautyPersonalCare', 'Electronics & Accessories': 'categoryElectronicsAccessories', 'Stationery, Food & Other': 'categoryStationeryFoodOther', 'Blind Boxes & Collectible Figures': 'categoryBlindBoxesFigures', 'Building Blocks & Model Kits': 'categoryBuildingBlocksKits', 'Plush, Dolls & Sculptures': 'categoryPlushDollsSculptures', 'Other Toys': 'categoryOtherToys',
  'store operations': 'storeOperations', 'finance/support': 'financeSupport', 'eligible': 'eligible', 'Not available': 'notAvailable', 'None identified': 'noneIdentified', 'Group FP&A': 'groupFpa', Approved: 'statusApproved', Proposed: 'statusProposed', Superseded: 'statusSuperseded', Closed: 'statusClosed', decision_table: 'decisionTableContract', cash_bridge: 'cashBridgeContract', reconciliation: 'reconciliationContract', fy_revenue_delta: 'evidenceRevenueDelta', fy_operating_profit_delta: 'evidenceOperatingProfitDelta', 'selected FY2026 revenue - base FY2026 revenue': 'evidenceRevenueDeltaFormula', 'selected FY2026 operating profit - base FY2026 operating profit': 'evidenceOperatingProfitDeltaFormula', 'calculated category scenario rollup': 'calculatedCategoryScenarioRollup',
  'Commercial / Revenue Management': 'commercialRevenueManagement', 'Sourcing / Merchandising': 'sourcingMerchandising', 'Finance / Operations': 'financeOperations',
  'MINISO 2025 Form 20-F': 'sourceMiniso2025Form20F', 'MINISO 2026 H1 results': 'sourceMiniso2026H1', 'MINISO 2026 Q1 results': 'sourceMiniso2026Q1', 'MINISO 2025 H1 results': 'sourceMiniso2025H1',
  'FY2025 IFRS group results and segment disclosure': 'sourceFy2025Scope', '2026 Q2 and H1 IFRS results and revenue split': 'source2026Q2H1Scope', '2026 Q1 IFRS results and revenue split': 'source2026Q1Scope', '2025 H1 IFRS results and revenue split': 'source2025H1Scope',
  reconciled: 'reconciled', not_reconciled: 'notReconciled', not_eligible: 'notEligible',
  capacity_gap: 'capacityGap', over_capacity: 'overCapacity', zero_capacity: 'zeroCapacity', balanced: 'balanced',
  US: 'exchangeUs', HKEX: 'exchangeHkex', LSE: 'exchangeLse', A_SHARE: 'exchangeAShare', SSE: 'venueSse', SZSE: 'venueSzse', BSE: 'venueBse',
}
const errorLabels: Record<string, keyof import('./locales/en').EnglishCatalog> = {
  invalid_exchange: 'errorInvalidExchange', invalid_venue: 'errorInvalidVenue', invalid_ticker: 'errorInvalidTicker', ambiguous_ticker: 'errorAmbiguousTicker', unsupported_exchange: 'errorUnsupportedExchange', dependency_missing: 'errorDependencyMissing', no_data: 'errorNoData', malformed_upstream: 'errorMalformedUpstream', period_inconsistent: 'errorPeriodInconsistent', currency_missing: 'errorCurrencyMissing', rate_limited: 'errorRateLimited', provider_timeout: 'errorProviderTimeout', provider_unavailable: 'errorProviderUnavailable', validation_error: 'errorValidation', internal_server_error: 'errorInternal', case_not_found: 'errorCaseNotFound', rollup_reconciliation_failed: 'errorReconciliation', request_too_large: 'errorRequestTooLarge', request_error: 'errorRequest',
}
export function apiLabel(value: string | null | undefined, t: (key: keyof import('./locales/en').EnglishCatalog, vars?: Record<string, string | number>) => string) {
  if (!value) return t('notAvailable')
  const key = labels[value] || labels[value.toLowerCase()]
  return key ? t(key) : value
}
export function apiErrorLabel(value: string | null | undefined, t: (key: keyof import('./locales/en').EnglishCatalog, vars?: Record<string, string | number>) => string) {
  return value && errorLabels[value] ? t(errorLabels[value]) : t('errorRequest')
}
export function apiLabelKey(value: string) { return labels[value] }
export type { Locale }
