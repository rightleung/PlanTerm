# PlanTerm data methodology

## Public anchors

The committed snapshot stores MINISO Group Holding Limited results in RMB millions under IFRS. It records the official FY2025, 2025 H1, 2026 Q1, 2026 Q2 and 2026 H1 group metrics and revenue split, with source URL, source date, period end and `public_reported` provenance on every period.

## Synthetic three-business-unit view

The public revenue split is mapped to the three v0.1 business units. The immaterial reported `Others` revenue is allocated to MINISO Chinese Mainland so the portfolio remains exactly reconciled to group revenue. Monthly values are deterministic allocations using the committed seasonality weights and are marked `synthetic_allocation`.

Gross profit and operating profit are not reported by these exact business units in the snapshot. For FY2025, 2025 H1 and 2026 H1, each unit receives an initial weight of `revenue × index`, then the weights are normalized separately to the reported group gross profit and operating profit totals:

```text
Gross Profit_i = Group Gross Profit ×
                 (Revenue_i × Gross-margin index_i) /
                 Σ(Revenue × Gross-margin index)

Operating Profit_i = Group Operating Profit ×
                     (Revenue_i × Operating-margin index_i) /
                     Σ(Revenue × Operating-margin index)
```

The indices are explicit synthetic controls. The generator fails if an allocation produces negative cost of sales, negative operating expense or gross profit above revenue. Allocated profit and cost records remain `synthetic_allocation`, never `public_reported`.

## Variance and driver bridges

Revenue PVM uses YTD Actual versus YTD Budget. Its Volume, Mix and Price effects reconcile to revenue variance. The operating-profit bridge applies each unit's budget gross margin to the revenue PVM effects, then adds the gross-margin and operating-expense effects:

```text
PVM profit effect = Revenue PVM effect × Budget gross margin
Gross Margin effect = Actual revenue × (Actual GM − Budget GM)
Opex effect = −(Actual Opex − Budget Opex)
```

The sum is checked against Actual versus Budget Operating Profit with a RMB 0.01 million tolerance. `Revenue driver` is selected only from Price, Volume and Mix; `Profit driver` is selected independently from those effects, Gross Margin and Opex.

## Refresh behavior

`scripts/refresh_public_actuals.py` is dry-run by default. It parses the official H1 metrics and revenue split, validates the source URL, period, unit, finite non-negative split values and split-to-group reconciliation, and only then performs an atomic replacement when `--write` is supplied. A missing split or changed page structure fails loudly rather than combining a new group total with an old split.

## v0.2 planning-input methodology

The planning-input layer is deliberately stateless. The committed category seed contains 252 rows: three complete plan variants, six H2 months (2026-07 through 2026-12), and 14 business-unit/category leaves. The CSV contract contains only the four driver changes—volume, average ticket, gross-margin delta and opex-ratio delta. The server injects category names and provenance and recomputes all financial amounts; it does not accept category revenue, profit, Actual, Budget, Prior Year or source fields from the client.

For each row, the scenario formulas are:

```text
scenario_volume = budget_volume × (1 + volume_change_pct)
scenario_ticket = budget_ticket × (1 + average_ticket_change_pct)
scenario_gross_margin = budget_gross_margin + gross_margin_delta_pp
scenario_opex_ratio = budget_opex_ratio + opex_ratio_delta_pp
revenue = scenario_volume × scenario_ticket
gross_profit = revenue × scenario_gross_margin
opex = revenue × scenario_opex_ratio
operating_profit = gross_profit − opex
```

The selected plan variant changes H2 Forecast only. FY Forecast is frozen H1 Actual plus the selected H2 scenario. Existing YTD Actual versus fixed Budget PVM, Actual, Budget and Prior Year remain unchanged. Base is reverse-inferred from the committed Budget-to-Forecast case; Upside and Downside are committed complete matrices rather than runtime fallbacks. Category-to-business-unit and business-unit-to-portfolio totals, financial identities and the Base compatibility anchor are checked with a RMB 0.01 million tolerance.

Official MINISO and TOP TOY labels are retained as taxonomy provenance with source URL and period. They do not represent reported category revenue or profitability. All category values are labelled `synthetic_allocation`, `synthetic_plan` or `calculated`, and browser upload/editor contents are discarded rather than written to the case files.
