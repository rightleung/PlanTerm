# Operating Decision demo script

## Setup

Run the application from the repository root:

```bash
./scripts/rebuild_workspace.sh
./run_app.sh
```

Open `http://127.0.0.1:8000`. The demo case is `miniso-2026`, as of `2026-06-30`, with all money shown in RMB millions.

## Five-minute flow

1. Start on the dashboard and identify the H1 Actual, Budget, Forecast and Prior Year context. Explain that only the public group anchors are reported; allocations and planning assumptions are labelled synthetic.
2. Open Planning Inputs. Show that H1 is locked, the editable horizon is 2026-07 through 2026-12, and all three complete variants (`base`, `upside`, `downside`) remain available. Select a variant and apply the stateless preview.
3. In Working capital and illustrative cash, review AR/AP/inventory days, calculated balances, NWC and CCC. Point out the synthetic/calculated provenance and the reconciliation status.
4. Use the Revenue PVM and Operating Profit bridge to explain Volume, Mix, Price, PVM profit effect, Gross Margin and Opex. Then use the cash bridge to explain opening cash, operating profit, working-capital effects, CAPEX, other cash, net change, illustrative closing cash, minimum buffer and headroom. State explicitly that this is not reported or actual cash.
5. Review forecast accuracy. Null values remain unavailable with their eligibility status; they are never zero-filled and do not claim company-internal forecast accuracy.
6. Compare Base, Upside and Downside in the Scenario decision table. The selected plan variant changes H2-derived operating and illustrative cash outcomes only.
7. Add or edit an action using Observation, Driver, Impact, Risk, Action, Owner, Due and Cadence. Reload the page to demonstrate that it was session-only and not persisted.
8. Add a governance decision with context, options, decision, rationale, owner role, affected contracts and evidence. Confirm the row is visible but existing rows have no edit controls; reload to demonstrate session scope.
9. Open Conclusion provenance. Trace each displayed KPI to its metric/formula, source/provenance label and reconciliation status. Confirm `public_reported`, `synthetic_allocation`, `synthetic_plan` and `calculated` remain distinct and that no internal MINISO data is claimed.
10. Export the eight-sheet management pack. Confirm the `PVM Bridge` sheet contains both Revenue PVM and Operating Profit bridge, and the `Operating Decision` sheet contains workforce capacity, assumption version, git SHA, governance decision evidence, illustrative/synthetic disclosures, calculated numeric formulas, literal neutralized disclosure text and numeric negative amounts.

## Verification

```bash
cd web
npm run lint
npx tsc -b
npm run build
npx playwright test --list e2e/dashboard.spec.mjs
```

Run the backend contract gates and browser acceptance when the local service is available:

```bash
./.venv/bin/python -m pytest -q tests/test_working_capital.py tests/test_cash_forecast.py tests/test_forecast_accuracy.py tests/test_operating_decision_contract.py
cd web && npx playwright test e2e/dashboard.spec.mjs --reporter=line
```

P0-P3 implementation evidence requires API/UI/Excel parity and RMB 0.01m reconciliation checks. Final v1.0 publication additionally requires a matching direct-CI result and explicit release-owner authorization.
