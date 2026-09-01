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

The dashboard, `PVM Bridge` worksheet and Operating Profit bridge expose the same three reconciled profit effects—`PVM profit effect`, `Gross Margin` and `Opex`—with signed amount, contribution percentage, favorability direction, calculated provenance and a role owner. Portfolio KPI source labels identify public group anchors only for the unfiltered group view; BU-filtered values are synthetic allocations, and every variance/margin conclusion is labelled calculated.

The scenario decision table reports portfolio CCC for each variant at that variant's minimum-cash month. AR days are revenue-weighted, while inventory and AP days are COGS-weighted before applying `CCC = AR days + Inventory days - AP days`; this keeps the variant-level decision metric consistent with the underlying working-capital rows.

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

## v0.3 operating-decision methodology

The operating-decision case is `miniso-2026`, as of `2026-06-30`, in RMB millions. Its selected `plan_variant` remains `base`, `upside` or `downside`; it is not the existing `scenario` enum. Actual, Budget, Prior Year and H1 remain immutable. Only complete H2 category-driver rows, working-capital rows and cash-assumption rows are accepted for a stateless preview.

AR/AP/inventory days, opening cash, CAPEX proxy, other cash inputs, forecast snapshots and illustrative actions are `synthetic_plan` or `illustrative_session_action`. They do not represent MINISO internal receivables, payables, inventory, cash, forecast accuracy or action tracking. Server formulas produce `calculated` balances, NWC, cash-conversion cycle, cash effects, illustrative closing cash, headroom, forecast metrics and reconciliation results:

```text
AR = Revenue x AR days / Days in period
Inventory = COGS x Inventory days / Days in period
AP = COGS x AP days / Days in period
NWC = AR + Inventory - AP
CCC = AR days + Inventory days - AP days
Net cash change = OP + (prior AR - current AR) + (prior Inventory - current Inventory)
                  + (current AP - prior AP) - CAPEX + Other cash items
Illustrative closing cash = Opening cash + Net cash change
Headroom = Illustrative closing cash - Minimum cash buffer
```

The browser action register is session memory only. It is not written to case data, a database or a user directory. The operating-decision Excel sheet keeps source and disclosure text as literal spreadsheet-neutralized values, preserves numeric negatives as numbers, and uses auditable formulas only for calculated numeric cells. The cash bridge must be described as illustrative or synthetic, never as public reported or actual cash. All roll-ups and bridge reconciliations use a RMB 0.01m tolerance; missing or ineligible accuracy metrics remain `null` with a status rather than becoming zero.

## v0.5 governance evidence

Governance conclusions are reviewed against `miniso-2026`, as of `2026-06-30`, with `base` selected unless a preview explicitly changes it. A deterministic review edit changes `MINISO - Chinese Mainland / IP & Toys / miniso_ip_toys / 2026-07` from the committed `3.0%` volume driver to `10.0%`; the expected result is a recomputed positive revenue/profit and illustrative cash delta, with headcount unchanged. An edited Base variant reconciles to its own scenario-internal roll-up; an unedited Base variant remains checked against the committed forecast anchor. Group FP&A owns the review action. The UI and workbook expose the assumption version and git SHA, and each conclusion carries a metric, formula, source/provenance label and reconciliation status. This evidence is bounded to the case study and does not claim internal MINISO data.
