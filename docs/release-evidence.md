# v0.5 / v1.0 integration evidence

## v1.2 company lookup evidence

The current release metadata is `1.2.0`. `POST /api/v1/company/profile` and `GET /api/v1/symbols/search` are additive endpoints. Common US, HKEX, LSE, SSE and SZSE formats are covered by deterministic tests; live yfinance profile smoke was verified for `AAPL`, `600519`, `000001`, `0700.HK` and `VOD.L`. Results retain provider values and are disclosed as public data, not internal company data. The release uses a non-Docker virtualenv/Uvicorn deployment path, a readiness endpoint and production startup without `--reload` or runtime dependency installation.

The final local review run for the current working tree passed `128` Python tests with one opt-in live test skipped, frontend lint, i18n tests, both TypeScript projects, production build, npm and Python dependency audits, and all `21` Chromium browser tests. A clean `planterm-1.2.0` wheel was built successfully. GitHub Actions must be rerun after committing this working tree; the historical CI run below does not cover these changes.

This is an evidence pack for review, not a release declaration. The implemented scope is the `miniso-2026` case, as of `2026-06-30`, in RMB millions, with the `base` plan variant selected by default.

## v1.1 historical release candidate evidence

This section records the historical v1.1 compatibility evidence. The current release metadata is recorded in the v1.2 section above.

### Acceptance gates

The final local gate set is recorded as real command output, with the live provider smoke test intentionally skipped because live access is disabled by default:

| Gate | Command | Result |
|---|---|---|
| Dependency integrity | `./.venv/bin/python -m pip check` | Exit 0 · `No broken requirements found.` |
| Full Python suite | `./.venv/bin/python -m pytest -q` | Exit 0 · `116 passed, 1 skipped, 1 warning in 49.43s`; the single skip is the opt-in live smoke and the warning is the existing Starlette/httpx deprecation |
| Case reproducibility | `./.venv/bin/python scripts/build_miniso_case.py --check` | Exit 0 · 882 planning rows and 252 category rows |
| Frontend lint | `cd web && npm run lint` | Exit 0 |
| Locale unit tests | `cd web && npm run test:i18n` | Exit 0 · 5 tests passed |
| App TypeScript | `cd web && npx tsc -p tsconfig.app.json --noEmit` | Exit 0 |
| Production build | `cd web && npm run build` | Exit 0 · 2,347 modules transformed |
| Browser preflight | `cd web && npm run e2e:preflight` | Exit 0 · 19 Chromium tests passed |
| Dashboard browser suite | `cd web && npx playwright test e2e/dashboard.spec.mjs --project=chromium` | Exit 0 · 19 tests passed, including locale persistence/fallback |

The implementation-plan command writes `web/dashboard.spec.mjs` after changing directory to `web`; the repository path is `web/e2e/dashboard.spec.mjs` from the repository root, or `e2e/dashboard.spec.mjs` from `web`. The final run used the latter to avoid the duplicated `web/web` path.

### Responsive shell evidence

The six-viewport Playwright measurement logs recorded equal document/client widths, zero visible unowned overflow elements, card bounds inside the content shell, and four table scroll owners with `overflow-x: auto` at every viewport. The compact evidence below is the exact measured shell range; fractional values are browser layout pixels.

| Viewport | document/client width | content and visible-card edge range | unowned overflow | table owners |
|---|---:|---:|---:|---:|
| 1440×900 | 1440 / 1440 | 80.0 … 1360.0 | 0 | 4 · auto |
| 1280×800 | 1280 / 1280 | 64.0 … 1216.0 | 0 | 4 · auto |
| 1024×768 | 1024 / 1024 | 51.2 … 972.8 | 0 | 4 · auto |
| 768×1024 | 768 / 768 | 38.4 … 729.6 | 0 | 4 · auto |
| 390×844 | 390 / 390 | 19.5 … 370.5 | 0 | 4 · auto |
| 320×568 | 320 / 320 | 16.0 … 304.0 | 0 | 4 · auto |

The dialog test also passed at 1024px, 768px and 390px with focus retained in the dialog, footer/close controls reachable, unchanged page width and matrix/context scroll contained inside labeled surfaces. The overflow detector excludes only intentionally visually-hidden `.sr-only` accessibility text and zero-area Recharts measurement nodes; page-level width equality and all visible-element bounds remain asserted.

### Public-import API, provider and fixture evidence

`POST /api/v1/public-import/preview` is additive to the existing OpenAPI surface. Deterministic fixture routing returned normalized symbols for US `AAPL`, LSE `VOD.L`, HKEX `0005.HK`, A-share SSE `600519.SS` and SZSE `000001.SZ`; bare six-digit A-share input returned `ambiguous_ticker`, and explicit BSE returned `unsupported_exchange`. Representative rows include annual and quarterly periods, common metric IDs with per-metric flow/stock semantics, native currency/scale, null optional values, source URL, UTC retrieved-at, as-of and filing metadata. Malformed upstream, period and currency errors map to HTTP 422 per the implementation contract.

The fixture inventory is `tests/fixtures/public_import/{us_aapl,lse_vod,hkex_0005,sse_600519,szse_000001,a_share_sse_600000,a_share_szse_000001}.json`; anomaly fixtures cover `missing.json`, `malformed.json`, `duplicate.json`/`mismatched.json`, currency ambiguity and period inconsistency. SHA-256 hashes for all 11 JSON fixtures are captured by the release-owner review command `shasum -a 256 tests/fixtures/public_import/*.json`.

```text
a_share_sse_600000.json cb38b042c44282688627889f95b75c6c56f9a70102a77b5326964d6a86b6b978
a_share_szse_000001.json 15927f1000db614d4db3f63b8f3c9f5d3e022466f36ca9b2e2207cb83afe0640
duplicate.json 2919797e7783475a5f6f3804abdb5554e38c685cbaea5c956ba9cb2f22de7a69
hkex_0005.json 53e08b3f2ca3ecddbb0ea88aae82e0c59bc8a88ea1969b7643ac287ef04c93b1
lse_vod.json c7446da14ea5c1e0244cda8c8f3ec8f5929d1a131ba18d1a019910ce80096a59
malformed.json 76327c58d445c5aa04be539dc1cd988edef73dd07050d8770c1ef5297b770bb3
mismatched.json dca1ea461745db8ec07f6cdb91e34031827256eed20246c2c41aba0019973ae0
missing.json 03deac8e7ab4673974dc53c59fcad9edc22e83b38bd975ba17a4686d92d6c1cd
sse_600519.json dbe66436393dcbf5cdcb381ef5485f5854a6009dc7af15929d54d3cbcabfbf87
szse_000001.json b13e60302fdc509e5f77b1339236e4b02725158f41647409560309c7fc40725f
us_aapl.json bbf08806a02f13cc4dffbaea554edcf6405477008babe4240a1a90cdb8d886e7
```

The provider protocol separates routing, symbol normalization, period/currency/unit normalization, provenance and bounded I/O. The service uses a bounded thread pool/semaphore, 8-second provider timeout, 12-second total deadline, at-most-two transient retries, positive/negative/rate-limit in-memory caches, single-flight coalescing and one-request-per-provider-per-second rate limiting. Typed tests cover dependency absence, provider outage, timeout, retry, rate limiting, unsupported ticker/venue, malformed upstream, duplicate/conflicting periods, inconsistent currency and no-data behavior. No fixture or live result is merged into `miniso-2026`; `dashboard_ready` remains false and no FX conversion is performed.

### Disclosure, security and provider-terms checklist

- [x] Live public providers default off; opt-in smoke requires `PLANTERM_LIVE_PUBLIC_DATA=1` and an explicit `PLANTERM_PUBLIC_IMPORT_ALLOWLIST` entry.
- [x] No arbitrary URL, credential, cookie, authorization header or raw request body is accepted or logged; source URLs are fixed HTTPS URLs without query strings/fragments.
- [x] No scraping or browser automation is used for public import. yfinance and AkShare are optional, lazy-loaded adapters; the current AkShare A-share live path reports not enabled, and BSE is unsupported.
- [x] Native currency and declared unit scale are shown; no FX conversion or cross-currency consolidation is performed.
- [x] Public reported statements are separately disclosed as not internal company data; synthetic MINISO planning values retain their existing provenance labels.
- [x] Rollback is additive: disable `public_import_enabled` on the server and `VITE_PUBLIC_IMPORT_ENABLED` in the frontend; stale API clients receive `provider_unavailable`/disabled behavior while `miniso-2026` remains available.
- [ ] Release owner terms/licensing review for each live provider and optional dependency.
- [ ] Release owner decision on changing package/UI labels from the compatibility version and on final tag/publication.

### ITSSX routing evidence

Delegated implementation starts used direct CLI relay sessions with explicit `model_provider="itssx"`; startup headers were observed for every session. The sequence and requested settings were: unique leader `gpt-5.6-sol/high`, Worker A `gpt-5.6-terra/high`, Worker C `gpt-5.6-sol/high` in parallel, Worker B `gpt-5.6-terra/high` after A's CSS/selector contract, and Reviewer D `gpt-5.6-sol/high` after this evidence section. No desktop launcher, OAuth child, `spawn_agent` or recursive `codex exec` was used.

## Deterministic review edit

Edit one H2 driver in the browser session: set `MINISO - Chinese Mainland / IP & Toys / miniso_ip_toys / 2026-07` volume change from the committed `3.0%` to `+10.0%` in the `base` variant, then apply the preview. The server recomputes the category, business-unit and portfolio roll-ups; no uploaded value is persisted. Because Base is edited, the category reconciliation is explicitly anchored to the scenario's own recalculated roll-up rather than the committed forecast anchor.

Direct API evidence for this edit is dashboard `200` and operating-plan `200`: FY Revenue `+20.1666`, Gross Profit `+8.7725` and Operating Profit `+2.8233` RMB millions versus the committed Base. The July illustrative net-cash/headroom movement is `+1.4230` RMB millions; December closing cash/headroom converges to the unedited case because of the deterministic catch-up assumptions. Category residual is `0.0`, the anchor is `scenario_internal`, and workforce deltas remain zero. The review owner is Group FP&A; the action is to compare the preview deltas, reconcile the portfolio residuals, and record an approved decision in the session-only decision log.

## Provenance disclosures

- `public_reported`: committed MINISO group Actual and Prior Year anchors only.
- `synthetic_allocation`: deterministic business-unit and category allocations.
- `synthetic_plan`: budget, forecast, H2 drivers, working-capital, cash and workforce inputs.
- `calculated`: formulas, bridges, roll-ups, reconciliations and derived KPIs.

The product does not claim internal MINISO cash, working capital, payroll, HRIS, forecast or action-register data. Decision-log entries are immutable after addition and exist only for the browser session.

## v1.0 integration evidence

- API surface: the OpenAPI document exposes the existing dashboard/planning routes plus the operating-plan GET/preview and forecast-accuracy routes; governance fields are additive to the operating-plan payload.
- TypeScript surface: `OperatingPlanResponse` carries `decision_log`, `assumption_registry`, `assumption_version`, `git_sha` and the eleven decision-event fields.
- Deterministic parity: `miniso-2026`, `2026-06-30`, RMB millions, selected variant and locked horizon are shared by API, UI and Excel. Revenue PVM and the three-part Operating Profit bridge (`PVM profit effect`, `Gross Margin`, `Opex`) reconcile at the `0.01` RMB million tolerance; the scenario decision table carries portfolio CCC at each variant's minimum-cash month; workforce capacity is embedded in `Operating Decision`, preserving the seven existing sheets plus that one additive sheet.
- Local checks: the verification ledger below records the current Python suite, `pip check`, generator, frontend lint, TypeScript and production build; terminal Playwright remains environment-limited by Chromium launch permissions, while the in-app browser session check confirmed seeded read-only events, required-field gating, add flow and reload-clearing (`beforeAdd=true`, `afterAdd=1`, `afterReload=0`).
- Clean-checkout demo: the [matching direct CI run](https://github.com/rightleung/PlanTerm/actions/runs/33511921647) checked out the pushed implementation commit and ran all 16 Playwright tests successfully in the frontend job.
- Screenshot: [Operating Decision evidence](./assets/planterm-operating-decision.png) captured from the integrated local build; it contains no sensitive data.

## Verification ledger

| Gate | Command / evidence | Result |
|---|---|---|
| Dependencies | `./.venv/bin/python -m pip check` | Exit 0 · no broken requirements |
| Backend regression | `./.venv/bin/python -m pytest -q` | Exit 0 · 86 passed, 1 existing `StarletteDeprecationWarning`, no skips/xfails |
| Case completeness | `./.venv/bin/python scripts/build_miniso_case.py --check` | Exit 0 · 882 planning rows and 252 category rows |
| Frontend lint | `cd web && npm run lint` | Exit 0 |
| Frontend type checks | `tsc -p tsconfig.app.json --noEmit` and `tsc -p tsconfig.node.json --noEmit` | Exit 0 for both |
| Production build | `cd web && npm run build` | Exit 0 · 2,341 modules transformed |
| Browser acceptance | Terminal preflight is blocked before test execution by Chromium launch permissions; focused governance checks and the earlier in-app browser session passed seeded/read-only, required-field, add, provenance and reload-clearing flows. | Environment-limited; no full terminal E2E PASS is claimed |

## Direct CI evidence

- Implementation commit: `99f5817fa878f94fba00ebe44a072dc5007d54b2` (`test: align browser assertions with integrated data`).
- Run: [GitHub Actions CI run 33511921647](https://github.com/rightleung/PlanTerm/actions/runs/33511921647).
- Head SHA: `99f5817fa878f94fba00ebe44a072dc5007d54b2`; status: `completed`; conclusion: `success`.
- All three jobs passed: Python package and tests, frontend lint/build/browser tests, and dependency security audit. The frontend job ran from a clean checkout and completed 16/16 Playwright tests.

## Immutable baseline hashes

The baseline values recorded before P3/P4 and the current working-tree values are identical:

| File | Baseline SHA-256 | Current SHA-256 |
|---|---|---|
| `data/cases/miniso-2026/planning_records.csv` | `70ec0f851aa0089cfdf1208329b745c08882ed16dbd64be1ce4ced187a65f30a` | `70ec0f851aa0089cfdf1208329b745c08882ed16dbd64be1ce4ced187a65f30a` |
| `data/cases/miniso-2026/category_scenario_seed.csv` | `7ec49244501d915358d31677725adb739ef2ee96bdfebd3587acf51051772477` | `7ec49244501d915358d31677725adb739ef2ee96bdfebd3587acf51051772477` |
| `data/source/miniso_public_actuals.json` | `81869e9add4426518689d4a6fe19fc25a09f895caff3353325692a1869f6443a` | `81869e9add4426518689d4a6fe19fc25a09f895caff3353325692a1869f6443a` |
| `data/cases/miniso-2026/metadata.json` | `c9acb182338779e2baf20656b1eb47bb82611dacef74eac009955cdd3052ba16` | `c9acb182338779e2baf20656b1eb47bb82611dacef74eac009955cdd3052ba16` |

## API / UI / Excel parity

| Contract | API | UI | Excel Management Pack |
|---|---|---|---|
| Case, as-of, currency and unit | `miniso-2026`, `2026-06-30`, RMB millions | Metadata strip and disclosure | Executive Summary and Operating Decision |
| Variant and horizon | `base` / `upside` / `downside`; H2 July–December editable | Variant tabs and locked-horizon controls | Scenario Inputs & Provenance and selected detail |
| Provenance | Four explicit labels and evidence rows | Legend plus conclusion-level evidence | Source/provenance columns and governance evidence |
| Reconciliation | Category, cash and workforce residual/status | Provenance and operating-plan status rows | Operating Decision reconciliation row |
| Driver bridges | Revenue PVM plus reconciled PVM profit effect / GM / Opex bridge | PVM and Operating Profit bridge panels with direction, provenance and owner | PVM Bridge sheet with formula-backed amounts and contribution percentages |
| Governance | Three seeded decision events and assumption registry | Read-only seed rows plus session-only add flow | Operating Decision metadata and decision evidence |

## Delegation and review gate

All successful delegation starts used a fresh harmless probe followed by a startup header showing `provider: itssx` and the requested model/reasoning pair. The routing record is:

| Role | Provider / model / effort | Outcome |
|---|---|---|
| Leader | ITSSX / `gpt-5.6-sol` / high | Frozen contract, ownership and reconciliation completed |
| Backend/Data worker | ITSSX / `gpt-5.6-terra` / high | P3 backend and contract tests completed |
| Frontend/Excel worker | ITSSX / `gpt-5.6-terra` / high | P3 UI, export, E2E fixture and documentation completed |
| Independent QA | ITSSX / `gpt-5.6-luna` / xhigh | Found issues; root fixes are present and current local checks are green |
| Independent reviewer | ITSSX / `gpt-5.6-sol` / high | Final post-fix review PASS; no code-level High/Blocker/strict Medium. CCC, Decimal aggregation, filtered-view Excel provenance, generated-directory lint, profit bridge, workforce variant isolation and version consistency were verified |

Matching direct CI evidence is complete for the pushed implementation commit. Existing tags are preserved; the v1.0.0 tag and release publication remain explicit release-owner actions and were not performed by Codex.

## Checklist

- [x] Decision-log add/view flow is English, bounded, controlled and session-only.
- [x] Existing decision events render read-only; no edit path is exposed.
- [x] Conclusion provenance shows metric, formula, source label and reconciliation status.
- [x] Assumption version and git SHA are visible in the UI and Excel export (local SHA is explicitly marked unavailable when not injected).
- [x] Excel management pack has the seven existing sheets plus `Operating Decision`; workforce capacity is embedded there without displacing `Assumptions & Sources`.
- [x] Spreadsheet text is neutralized while numeric cells, including negative values, remain numeric.
- [x] Frontend lint, typecheck, build and focused browser checks pass locally; the full terminal preflight is environment-limited by Chromium launch permissions.
- [x] P1 API/UI/Excel parity and RMB 0.01m reconciliation gates are covered by backend tests, Excel assertions and in-app browser verification.
- [x] Matching direct CI result is recorded for the pushed implementation commit; the clean-checkout browser job completed 16/16 tests.
- [ ] v1.0.0 Git tag and release publication — explicit release-owner action; not performed by Codex.
