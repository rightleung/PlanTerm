import type { BrandFilter, MarketFilter } from '@/types/planning'
import { useI18n } from '@/i18n'

interface FilterBarProps {
  brand: BrandFilter
  market: MarketFilter
  availableFilters?: { valid_combinations: { brand: Exclude<BrandFilter, 'all'>; market: Exclude<MarketFilter, 'all'>; business_unit: string }[] }
  onBrandChange: (value: BrandFilter) => void
  onMarketChange: (value: MarketFilter) => void
  onReset: () => void
}

export function FilterBar({ brand, market, availableFilters, onBrandChange, onMarketChange, onReset }: FilterBarProps) {
  const { t } = useI18n()
  const isMarketAllowed = (value: MarketFilter) => value === 'all' || !availableFilters || availableFilters.valid_combinations.some((combination) => (brand === 'all' || combination.brand === brand) && combination.market === value)
  return (
    <section className="filter-bar" aria-label={t('dashboardFilters')}>
      <label>
        <span>{t('brand')}</span>
        <select aria-label={t('brand')} value={brand} onChange={(event) => onBrandChange(event.target.value as BrandFilter)}>
          <option value="all">{t('allBrands')}</option>
          <option value="MINISO">MINISO</option>
          <option value="TOP_TOY">TOP TOY</option>
        </select>
      </label>
      <label>
        <span>{t('market')}</span>
        <select aria-label={t('market')} value={market} onChange={(event) => onMarketChange(event.target.value as MarketFilter)}>
          <option value="all">{t('allMarkets')}</option>
          <option value="mainland" disabled={!isMarketAllowed('mainland')}>{t('chineseMainland')}</option>
          <option value="overseas" disabled={!isMarketAllowed('overseas')}>{t('overseas')}</option>
          <option value="global" disabled={!isMarketAllowed('global')}>{t('globalTopToy')}</option>
        </select>
      </label>
      <button className="button button-ghost reset-button" type="button" onClick={onReset}>{t('resetFilters')}</button>
    </section>
  )
}
