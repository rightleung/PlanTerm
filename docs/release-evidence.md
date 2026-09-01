# v0.5 / v1.0 integration evidence

This is an evidence pack for review, not a release declaration. The implemented scope is the `miniso-2026` case, as of `2026-06-30`, in RMB millions, with the `base` plan variant selected by default.

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
