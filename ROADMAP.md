# Roadmap

## v0.1.1 — Credibility hardening

Completed in this release: normalized synthetic profit allocation indices, reconciled operating-profit drivers, data-derived filter combinations, incompatible-filter errors, automatic filter reset, split-aware atomic snapshot refreshes and formula-backed Excel formatting.

## v0.1 — MINISO FP&A Portfolio MVP

Completed in this release: public-data anchored Actual / Budget / Forecast / Prior Year, three-business-unit analysis, deterministic PVM, management insights, local FastAPI API, React dashboard and Excel management pack.

## v0.2.0 — Planning inputs

Completed in this release: deterministic synthetic product-category detail, strict 252-row CSV template/import, Base / Upside / Downside H2 scenario editor and preview, scenario comparison, locked Actual/Budget/Prior Year/H1 Actual boundaries, and a seven-sheet Excel management pack with input-matrix and taxonomy provenance.

## v0.3 — Operating planning

Implemented in the working tree: Operating Decision frontend, governance decision log, conclusion provenance, Excel and documentation for `miniso-2026` as of `2026-06-30`, in RMB millions.

- Working-capital planning with AR/AP/inventory days, NWC and CCC
- Illustrative synthetic cash bridge and headroom
- Forecast-accuracy tracking from synthetic snapshots
- Scenario decision table and session-only action register
- Session-only immutable decision log with exportable evidence
- Conclusion-level metric, formula, source and reconciliation provenance

Completion evidence is recorded in `docs/release-evidence.md`; the final release gate remains direct CI on the matching commit. Workforce/headcount capacity is implemented as v0.4 scope.

CI, Git tags and release publication remain future release-owner actions; this roadmap does not claim those results.

## v0.4 — Workforce capacity

Implemented in the working tree: bounded H2 role-group workforce inputs, required-versus-planned FTE, loaded cost, capacity-gap calculations, reconciliation evidence and API/UI/Excel parity. Individual employees, payroll and HRIS data remain out of scope.

## v0.5 — Governance and portfolio pack

Implemented in the working tree: session-only immutable decision events, assumption version/git SHA metadata, conclusion-level provenance and release/demo evidence for the deterministic MINISO case. Direct CI, Git tag and publication remain release-owner actions.

## v1.0 — Integrated release

Local integration is frozen across the OpenAPI endpoint surface, TypeScript types, deterministic UI state and eight-sheet workbook. The release is not declared until matching direct CI evidence is available and the repository owner authorizes the final tag/publication.

## Future — Reporting and benchmarks

- PDF management pack
- English / Chinese interface options
- Public peer benchmark views

Later versions remain out of scope until explicitly started.
