Deterministic public-import fixture symbols are defined by
`src.services.public_import.fixtures` and are selected only by tests.

Representative market coverage:

- `us_aapl.json` -> US / `AAPL` / USD
- `lse_vod.json` -> LSE / `VOD.L` / GBP
- `hkex_0005.json` -> HKEX / `0005.HK` / HKD
- `sse_600519.json` and `a_share_sse_600000.json` -> A-share / SSE / CNY
- `szse_000001.json` and `a_share_szse_000001.json` -> A-share / SZSE / CNY

Every representative payload includes annual and quarterly rows, native unit
scale, source URL, retrieval timestamp, as-of date and filing date. The
anomaly payloads cover missing data, malformed rows, duplicate/conflicting
periods and currency/period normalization errors. BSE is intentionally not a
fixture capability and returns `unsupported_exchange`.
