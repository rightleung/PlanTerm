import type { BrandFilter, MarketFilter } from '@/types/planning'

interface FilterBarProps {
  brand: BrandFilter
  market: MarketFilter
  onBrandChange: (value: BrandFilter) => void
  onMarketChange: (value: MarketFilter) => void
  onReset: () => void
}

export function FilterBar({ brand, market, onBrandChange, onMarketChange, onReset }: FilterBarProps) {
  return (
    <section className="filter-bar" aria-label="Dashboard filters">
      <label>
        <span>Brand</span>
        <select aria-label="Brand" value={brand} onChange={(event) => onBrandChange(event.target.value as BrandFilter)}>
          <option value="all">All brands</option>
          <option value="MINISO">MINISO</option>
          <option value="TOP_TOY">TOP TOY</option>
        </select>
      </label>
      <label>
        <span>Market</span>
        <select aria-label="Market" value={market} onChange={(event) => onMarketChange(event.target.value as MarketFilter)}>
          <option value="all">All markets</option>
          <option value="mainland">Chinese Mainland</option>
          <option value="overseas">Overseas</option>
          <option value="global">Global / TOP TOY</option>
        </select>
      </label>
      <button className="button button-ghost reset-button" type="button" onClick={onReset}>Reset filters</button>
    </section>
  )
}
