"""Fail-closed CSV trust boundary for planning inputs."""
from __future__ import annotations
import csv, io
from decimal import Decimal, InvalidOperation
from src.models.scenario import PlanningInputRow, CanonicalPlanningInputRow
from src.models.planning import PlanVariant

HEADERS = ["case_id", "plan_variant", "period", "business_unit", "category_id", "volume_change_pct", "average_ticket_change_pct", "gross_margin_delta_pp", "opex_ratio_delta_pp"]
H2_MONTHS = {f"2026-{m:02d}" for m in range(7, 13)}
MAX_BODY = 1024 * 1024
RANGES = {"volume_change_pct": (Decimal("-0.50"), Decimal("1.00")), "average_ticket_change_pct": (Decimal("-0.30"), Decimal("0.50")), "gross_margin_delta_pp": (Decimal("-0.15"), Decimal("0.15")), "opex_ratio_delta_pp": (Decimal("-0.10"), Decimal("0.10"))}

class InputError(ValueError):
    def __init__(self, error_type: str, message: str, details: dict | None = None):
        self.error_type, self.message, self.details = error_type, message, details or {}
        super().__init__(message)

def expected_keys(case_id: str, taxonomy: dict) -> set[tuple[str, str, str, str, str]]:
    leaves = [(item["business_unit"], item["category_id"]) for item in taxonomy["categories"]]
    return {(case_id, variant, period, bu, cat) for variant in ("base", "upside", "downside") for period in sorted(H2_MONTHS) for bu, cat in leaves}

def _decimal(value: str, field: str, rownum: int) -> Decimal:
    if not value or len(value) > 256 or "e" in value.lower() or any(ch in value for ch in ("=", "\x00")):
        raise InputError("invalid_input_row", "Invalid numeric input", {"row": rownum, "field": field})
    try: d = Decimal(value)
    except InvalidOperation: raise InputError("invalid_input_row", "Invalid numeric input", {"row": rownum, "field": field})
    if not d.is_finite() or abs(d.as_tuple().exponent) > 6:
        raise InputError("invalid_input_row", "Invalid numeric input", {"row": rownum, "field": field})
    lo, hi = RANGES[field]
    if d < lo or d > hi: raise InputError("invalid_input_row", "Input outside allowed range", {"row": rownum, "field": field})
    return d

def parse_csv(body: bytes, case_id: str, taxonomy: dict) -> list[CanonicalPlanningInputRow]:
    if len(body) > MAX_BODY: raise InputError("upload_too_large", "CSV body exceeds 1 MiB")
    if b"\x00" in body: raise InputError("malformed_csv", "NUL bytes are not permitted")
    try: text = body.decode("utf-8-sig")
    except UnicodeDecodeError: raise InputError("unsupported_encoding", "Only UTF-8 CSV is supported")
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        rows = list(reader)
    except csv.Error: raise InputError("malformed_csv", "Malformed CSV")
    if not rows or rows[0] != HEADERS or len(set(rows[0])) != len(rows[0]):
        raise InputError("template_header_mismatch", "CSV headers must match the committed template")
    if len(rows) - 1 > 500: raise InputError("malformed_csv", "CSV row limit exceeded")
    lookup = {(x["business_unit"], x["category_id"]): x for x in taxonomy["categories"]}
    output, seen, diagnostics = [], set(), []
    for rownum, values in enumerate(rows[1:], 2):
        if len(values) != 9:
            diagnostics.append({"row": rownum, "error": "expected 9 columns"}); continue
        if any(len(v) > 256 for v in values): diagnostics.append({"row": rownum, "error": "field too long"}); continue
        try:
            key = (values[0], values[1], values[2], values[3], values[4])
            if key in seen: raise InputError("duplicate_input_key", "Duplicate planning input key", {"row": rownum})
            seen.add(key)
            if values[0] != case_id: raise InputError("invalid_input_row", "Unknown case", {"row": rownum})
            if values[1] not in {v.value for v in PlanVariant}: raise InputError("scenario_not_found", "Unknown plan variant", {"row": rownum})
            if values[2] not in H2_MONTHS: raise InputError("locked_horizon", "Only H2 periods are editable", {"row": rownum})
            meta = lookup.get((values[3], values[4]))
            if not meta: raise InputError("unexpected_input_key", "Unknown business unit or category", {"row": rownum})
            kwargs = {field: _decimal(values[idx], field, rownum) for idx, field in zip(range(5, 9), HEADERS[5:])}
            output.append(CanonicalPlanningInputRow(case_id=case_id, plan_variant=values[1], period=values[2], business_unit=values[3], category_id=values[4], category_name=meta["category_name"], brand=meta["brand"], market=meta["market"], **kwargs))
        except InputError as exc:
            if exc.error_type in {"duplicate_input_key", "locked_horizon", "unexpected_input_key", "scenario_not_found"}:
                raise
            diagnostics.append({"row": rownum, "error": exc.error_type})
        if len(diagnostics) >= 50: break
    if diagnostics: raise InputError("invalid_input_row", "CSV validation failed", {"diagnostics": diagnostics[:50]})
    expected = expected_keys(case_id, taxonomy); observed = {(r.case_id, r.plan_variant.value, r.period, r.business_unit, r.category_id) for r in output}
    if observed != expected:
        missing, extra = expected - observed, observed - expected
        if extra: raise InputError("unexpected_input_key", "Unexpected planning input key", {"count": len(extra)})
        raise InputError("incomplete_input_matrix", "Complete 252-row matrix is required", {"missing_count": len(missing)})
    return output

def parse_json_rows(rows: list[dict], case_id: str, taxonomy: dict) -> list[CanonicalPlanningInputRow]:
    """Re-run the complete CSV contract for preview, including metadata trust checks."""
    if not isinstance(rows, list):
        raise InputError("incomplete_input_matrix", "Complete 252-row matrix is required")
    allowed = set(HEADERS) | {"category_name", "brand", "market", "provenance"}
    clean = []
    lookup = {(x["business_unit"], x["category_id"]): x for x in taxonomy["categories"]}
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise InputError("invalid_input_row", "Each planning row must be an object", {"row": index})
        unknown = set(row) - allowed
        if unknown:
            raise InputError("unexpected_input_key", "Unexpected planning input field", {"row": index, "fields": sorted(unknown)})
        missing = set(HEADERS) - set(row)
        if missing:
            raise InputError("template_header_mismatch", "Planning input row schema mismatch", {"row": index, "missing": sorted(missing)})
        bu, cat = row.get("business_unit", ""), row.get("category_id", "")
        meta = lookup.get((bu, cat))
        for field in ("category_name", "brand", "market", "provenance"):
            if field in row and field != "provenance" and meta and str(row[field]) != str(meta[field]):
                raise InputError("unexpected_input_key", "Planning metadata does not match taxonomy", {"row": index, "field": field})
            # Echoed canonical rows may carry only the server-injected marker.
            # It is discarded below, so client JSON cannot control provenance.
            if field == "provenance" and field in row and row[field] != "synthetic_plan":
                raise InputError("unexpected_input_key", "Invalid planning provenance", {"row": index})
        clean.append({field: row.get(field, "") for field in HEADERS})
    buf = io.StringIO(); writer = csv.DictWriter(buf, fieldnames=HEADERS, lineterminator="\n"); writer.writeheader()
    writer.writerows(clean)
    return parse_csv(buf.getvalue().encode(), case_id, taxonomy)
