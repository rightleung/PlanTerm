# PlanTerm

PlanTerm is an FP&A planning and performance management workbench. The current integrated workbench uses the `miniso-2026` public-data case, with an as-of date of `2026-06-30` and RMB millions throughout. It presents Actual, Budget, Forecast and Prior Year across:

- MINISO — Chinese Mainland
- MINISO — Overseas
- TOP TOY — Global

The dashboard is a local-first application with English (`en`), Simplified Chinese (`zh-CN`) and Traditional Chinese (`zh-TW`) UI locales, a deterministic API and an Excel management pack. The Excel labels remain English for compatibility. It covers revenue, gross profit, operating profit, margin, variance analysis, Price / Volume / Mix and Operating Profit bridges. Public reported figures are separated from synthetic allocations and illustrative planning assumptions throughout the product.

![PlanTerm dashboard showing the MINISO portfolio planning case](./docs/assets/planterm-dashboard.png)

## Quick start

Requirements: Python 3.12+ and Node.js 24+.

```bash
./scripts/rebuild_workspace.sh
./run_app.sh
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The application reads the committed case files and does not need a database, user account or live data connection to display the case.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service health and version |
| GET | `/api/v1/cases` | Available planning cases |
| GET | `/api/v1/cases/{case_id}/dashboard` | Dashboard aggregation with `brand` and `market` filters |
| GET | `/api/v1/cases/{case_id}/planning-input-template` | Deterministic 252-row CSV template |
| POST | `/api/v1/cases/{case_id}/planning-inputs/import` | Strict, non-persistent CSV validation |
| POST | `/api/v1/cases/{case_id}/dashboard/preview` | Independent 252-row scenario preview |
| GET | `/api/v1/cases/{case_id}/operating-plan` | Working capital, illustrative cash, actions and decision data |
| POST | `/api/v1/cases/{case_id}/operating-plan/preview` | Stateless operating-plan recalculation for a selected plan variant |
| GET | `/api/v1/cases/{case_id}/forecast-accuracy` | Synthetic-snapshot forecast accuracy metrics |
| POST | `/api/v1/public-import/preview` | Stateless allowlisted public-statement preview in native currency and units |

The API uses a consistent error shape: `error`, `error_type` and `details`. Unknown cases return 404, invalid filters return 422, and internal errors do not expose stack traces.

## Data and provenance

The committed public snapshot is anchored to MINISO's 2025 Form 20-F and official 2025 H1, 2026 Q1 and 2026 H1 investor-relations releases. The case uses RMB millions and IFRS-reported group metrics. Monthly values, three-business-unit allocations, budget, forecast, volume, ticket and profit allocations are deterministic and explicitly marked as synthetic or calculated. Business-unit gross profit and operating profit are normalized synthetic allocations using documented profit-allocation indices; they are not reported segment margins. See [data methodology](./docs/data-methodology.md) for the formulas and provenance rules.

`scripts/refresh_public_actuals.py` is a dry-run-first refresh utility. It downloads the fixed official source, validates the expected HTML table fields and fails loudly when the page structure changes. Pass `--write` only after reviewing the displayed differences.

`scripts/build_miniso_case.py --check` verifies that the committed `planning_records.csv` is exactly reproducible from the snapshot and assumptions.

## Planning inputs

The editor accepts a complete 252-row matrix: three plan variants (`base`, `upside`, `downside`), six editable H2 months from 2026-07 through 2026-12, and 14 business-unit/category leaves. Actual, Budget, Prior Year and H1 Actual remain locked. `Discard All` clears browser-session inputs and restores the committed Base seed. The server independently validates CSV and JSON boundaries, recomputes all financial values with Decimal arithmetic, and never persists uploaded content.

Product-category figures are synthetic planning allocations, not public category reporting. The UI and export disclose this distinction and retain official taxonomy labels only as source-backed taxonomy provenance.

## Operating decision workflow

The v0.3 operating-decision view extends the selected `base`, `upside` or `downside` H2 plan variant with AR, inventory and AP days; calculated balances, NWC and cash-conversion cycle; an illustrative cash bridge; forecast-accuracy metrics; a scenario decision table; and an action register. The v0.4 workforce view adds bounded role-group capacity; the v0.5 governance view adds session-only decisions and portfolio evidence.

AR/AP/inventory days, opening cash, CAPEX proxy, other cash assumptions, actions and forecast snapshots are synthetic planning inputs. Balances, cash effects, NWC, CCC, headroom, accuracy metrics and reconciliations are calculated. The product does not report actual company cash, working-capital balances, internal forecasts or action records. Browser action edits are session-only and are never persisted.

Governance evidence adds a session-only immutable decision log and conclusion-level provenance links. Each conclusion identifies its metric, formula, source label and reconciliation status; `public_reported`, `synthetic_allocation`, `synthetic_plan` and `calculated` remain explicit. Assumption version and git SHA are surfaced in the UI and workbook. See [v0.5 release evidence](./docs/release-evidence.md) for the deterministic review edit, clean-checkout CI evidence and remaining owner-controlled publication action.

## v1.1 public preview and UI release candidate

The additive v1.1 slice keeps the committed MINISO case and all existing FP&A/Excel behavior unchanged. The dashboard shell is tested at 1440×900, 1280×800, 1024×768, 768×1024, 390×844 and 320×568; only named table surfaces own horizontal scrolling. The language selector persists `en`, `zh-CN` or `zh-TW` in browser storage, falls back to English for missing keys, and uses `Intl` for numbers, currencies, dates and plural rules.

`POST /api/v1/public-import/preview` is a stateless read-only preview. It supports LSE, US, HKEX and A-shares with explicit `SSE`, `SZSE` or `BSE` venue handling. The current deterministic fixture provider covers US, LSE, HKEX, SSE and SZSE; BSE returns `unsupported_exchange`. Live providers are disabled by default and optional dependencies are loaded lazily. The preview preserves native currency and unit scale, performs no FX conversion, does not create or overwrite `miniso-2026`, does not write case files or database records, and labels public data as not internal company data. No arbitrary URLs, credentials or unapproved scraping are used.

The legacy package/API version remains `0.2.0` for compatibility. The additive `/health` field `release_id` exposes `1.1.0-rc.1` for this review candidate; changing package, footer or tag metadata is a release-owner decision. See [v1.1 methodology and evidence](./docs/release-evidence.md).

## Excel management pack

The dashboard export produces `PlanTerm_MINISO_2026H1_Management_Pack.xlsx` with the seven existing sheets plus one `Operating Decision` sheet. The active order is:

1. Executive Summary
2. Monthly Trend
3. Business Unit Variance
4. PVM Bridge
5. Assumptions & Sources
6. Product Category Detail
7. Scenario Inputs & Provenance
8. Operating Decision

The `PVM Bridge` sheet contains both the Revenue PVM and the reconciled Operating Profit bridge. The `Operating Decision` sheet contains working capital, illustrative cash, workforce capacity, forecast accuracy, scenario decisions, actions and governance evidence, so the existing seven-sheet order is preserved. The export follows the active dashboard filters and selected plan variant, uses RMB millions as the default unit, and includes the exact 252-row input matrix plus taxonomy, source and operating-decision disclosures. Numeric cells, including negatives, remain numeric. Formula-backed calculated cells remain auditable; disclosure text is exported as literal, spreadsheet-neutralized text.

## v0.2.0 planning inputs

This release adds deterministic product-category planning allocations, a strict CSV template/import contract, complete Base/Upside/Downside H2 scenario editing, stateless dashboard previews, scenario comparison, category detail, and a seven-sheet Excel management pack. Public reported Actual/Prior Year anchors remain distinct from synthetic allocation and scenario-input data.

## v0.3 status

Operating Decision, workforce capacity and governance evidence are implemented and pushed. The v1.0 integration contract is frozen across the API, TypeScript surface, UI and eight-sheet workbook; matching direct CI is recorded in the release evidence. Git tags and release publication remain release-owner actions.

### Implemented versus future scope

| Implemented in this case | Explicitly future / out of scope |
|---|---|
| Public-data anchored `miniso-2026`, H1 Actual / Budget / Prior Year, H2-only planning, responsive shell, three UI locales, governance provenance, stateless session previews and four-market public-data preview | ERP, bank, HRIS, payroll, database/cloud persistence, PDF pack, peer benchmarks, LLM-generated conclusions, a second case, and localized Excel labels |
| Synthetic allocation, synthetic plan and calculated values are labelled separately from public reported anchors | Production deployment, account management, multi-user persistence and automated release publication |

## v0.1.1 hardening

This release adds data-derived valid filter combinations, incompatible-filter 422 responses, automatic filter reset, an explicit empty dashboard state, distinct revenue and operating-profit drivers, formula-backed Excel variance fields, and atomic public-snapshot refreshes that include revenue split validation.

## Validation

```bash
./.venv/bin/python -m pip check
./.venv/bin/python -m pytest -q
./.venv/bin/python scripts/build_miniso_case.py --check
cd web
npm run lint
npm run test:i18n
npx tsc -p tsconfig.app.json --noEmit
npm run build
npm run e2e:preflight
npx playwright test e2e/dashboard.spec.mjs --project=chromium
```

## Project history and license

PlanTerm is an independent repository. Its FastAPI error handling, configuration patterns and selected React UI primitives were adapted from the author's earlier project; no historical Git history is copied into this repository. PlanTerm v0.2.0 is released under the [MIT License](./LICENSE).
