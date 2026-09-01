"""FastAPI application for the deterministic MINISO FP&A case."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from src.config import ROOT_DIR, settings
from src.repositories.case_repository import CaseNotFoundError, CaseRepository
from src.models.planning import PlanningInputSource
from src.services.planning_service import build_dashboard, build_operating_decision, filters_are_compatible, valid_combinations
from src.services.csv_input_service import InputError, HEADERS, parse_csv, parse_json_rows
from src.services.spreadsheet_neutralizer import sanitize_csv_row
from src.services.committed_json import DuplicateJsonKeyError, loads_json


logger = logging.getLogger(__name__)
repository = CaseRepository(settings.case_dir)


def api_error(error: str, error_type: str, details: dict | None = None) -> dict:
    return {"error": error, "error_type": error_type, "details": details}


app = FastAPI(
    title="PlanTerm — FP&A Planning and Performance Management Workbench",
    description="A deterministic public-data planning case for management performance review.",
    version=settings.version,
    docs_url="/docs",
    redoc_url="/redoc",
)


origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    __import__("fastapi.middleware.cors", fromlist=["CORSMiddleware"]).CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(HTTPException)
async def handle_http_exception(_request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    return JSONResponse(content=api_error(
        str(detail.get("error") or detail.get("message") or "Request failed"),
        str(detail.get("error_type") or "http_error"),
        {key: value for key, value in detail.items() if key not in {"error", "error_type", "message"}} or None,
    ), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(_request: Request, exc: RequestValidationError):
    return JSONResponse(content=api_error("Validation failed", "validation_error", {"errors": [
        {"loc": [str(part) for part in item.get("loc", [])], "msg": str(item.get("msg", "Validation error")), "type": str(item.get("type", "value_error"))}
        for item in exc.errors()
    ]}), status_code=422)


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    logger.error("Unhandled PlanTerm request error: %s", exc, exc_info=True)
    return JSONResponse(content=api_error("Internal server error", "internal_server_error", {"path": request.url.path}), status_code=500)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.version}


@app.get("/api/v1/cases")
def list_cases() -> dict:
    return {"cases": repository.list_cases()}


@app.get("/api/v1/cases/{case_id}/dashboard")
def dashboard(
    case_id: str,
    brand: Literal["all", "MINISO", "TOP_TOY"] = Query("all"),
    market: Literal["all", "mainland", "overseas", "global"] = Query("all"),
    plan_variant: Literal["base", "upside", "downside"] = Query("base"),
):
    try:
        case = repository.get_case(case_id)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "Case not found", "error_type": "case_not_found", "case_id": case_id})
    if not filters_are_compatible(case, brand, market):
        raise HTTPException(status_code=422, detail={
            "error": "Brand and market combination is not supported",
            "error_type": "incompatible_filters",
            "brand": brand,
            "market": market,
            "valid_combinations": valid_combinations(case),
        })
    try:
        return build_dashboard(case, brand, market, plan_variant)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc), "error_type": "rollup_reconciliation_failed"})


def _input_error(exc: InputError):
    return JSONResponse(content=api_error(exc.message, exc.error_type, exc.details), status_code=413 if exc.error_type == "upload_too_large" else 400 if exc.error_type in {"malformed_csv", "unsupported_encoding"} else 422)


@app.get("/api/v1/cases/{case_id}/planning-input-template")
def planning_input_template(case_id: str):
    try: case = repository.get_case(case_id)
    except CaseNotFoundError: raise HTTPException(status_code=404, detail={"error":"Case not found", "error_type":"case_not_found", "case_id":case_id})
    import csv, io
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=HEADERS, lineterminator="\n"); writer.writeheader(); writer.writerows(sanitize_csv_row(row) for row in case.category_seed)
    return Response(content=out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{case_id}-planning-input-template.csv"'})


@app.post("/api/v1/cases/{case_id}/planning-inputs/import")
async def planning_inputs_import(case_id: str, request: Request):
    try: case = repository.get_case(case_id)
    except CaseNotFoundError: raise HTTPException(status_code=404, detail={"error":"Case not found", "error_type":"case_not_found", "case_id":case_id})
    try:
        rows = parse_csv(await request.body(), case_id, case.taxonomy)
    except InputError as exc: return _input_error(exc)
    return {"case_id": case_id, "planning_input_source":"upload", "validated":True, "row_count":len(rows), "rows":[r.model_dump(mode="json") for r in rows], "planning_horizon":{"locked_through":"2026-06","editable_from":"2026-07","editable_to":"2026-12"}}


@app.post("/api/v1/cases/{case_id}/dashboard/preview")
async def dashboard_preview(
    case_id: str,
    request: Request,
    brand: Literal["all", "MINISO", "TOP_TOY"] | None = Query(None),
    market: Literal["all", "mainland", "overseas", "global"] | None = Query(None),
):
    try: case = repository.get_case(case_id)
    except CaseNotFoundError: raise HTTPException(status_code=404, detail={"error":"Case not found", "error_type":"case_not_found", "case_id":case_id})
    try:
        try:
            payload = loads_json(await request.body())
        except (UnicodeDecodeError, ValueError) as exc:
            raise InputError("malformed_csv", "Malformed JSON preview payload") from exc
        if not isinstance(payload, dict):
            raise InputError("incomplete_input_matrix", "Complete 252-row matrix is required")
        unexpected_top_level = sorted(set(payload) - {
            "selected_plan_variant",
            "planning_input_source",
            "brand",
            "market",
            "rows",
        })
        if unexpected_top_level:
            raise InputError("unexpected_input_key", "Unexpected preview input key", {"keys": unexpected_top_level})
        selected = payload.get("selected_plan_variant")
        if selected not in {"base", "upside", "downside"}: raise InputError("scenario_not_found", "Unknown plan variant")
        source_value = payload.get("planning_input_source", PlanningInputSource.UPLOAD.value)
        try:
            source = PlanningInputSource(source_value)
        except (TypeError, ValueError) as exc:
            raise InputError("invalid_input_source", "Unknown planning input source") from exc
        if source is PlanningInputSource.SEED:
            raise InputError("invalid_input_source", "Preview source must be upload or editor")
        selected_brand = payload.get("brand", brand or "all")
        selected_market = payload.get("market", market or "all")
        if selected_brand not in {"all", "MINISO", "TOP_TOY"} or selected_market not in {"all", "mainland", "overseas", "global"}:
            raise InputError("incompatible_filters", "Invalid brand or market filter", {"brand": selected_brand, "market": selected_market})
        if not filters_are_compatible(case, selected_brand, selected_market):
            raise InputError("incompatible_filters", "Brand and market combination is not supported", {"brand": selected_brand, "market": selected_market, "valid_combinations": valid_combinations(case)})
        raw_rows = payload.get("rows")
        if not isinstance(raw_rows, list): raise InputError("incomplete_input_matrix", "Complete 252-row matrix is required")
        canonical = parse_json_rows(raw_rows, case_id, case.taxonomy)
        return build_dashboard(case, selected_brand, selected_market, selected, source, [r.model_dump(mode="json") for r in canonical]).model_dump(mode="json")
    except InputError as exc: return _input_error(exc)
    except ValueError as exc:
        return JSONResponse(content=api_error(str(exc), "rollup_reconciliation_failed", None), status_code=422)


@app.get("/api/v1/cases/{case_id}/operating-plan")
def operating_plan(case_id: str, plan_variant: Literal["base", "upside", "downside"] = Query("base")):
    try:
        case = repository.get_case(case_id)
        return build_operating_decision(case, plan_variant)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "Case not found", "error_type": "case_not_found", "case_id": case_id})
    except InputError as exc:
        raise HTTPException(status_code=422, detail={"error": exc.message, "error_type": exc.error_type, **exc.details})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc), "error_type": "rollup_reconciliation_failed"})


@app.get("/api/v1/cases/{case_id}/forecast-accuracy")
def forecast_accuracy(case_id: str):
    try:
        case = repository.get_case(case_id)
        return build_operating_decision(case)["forecast_accuracy"]
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "Case not found", "error_type": "case_not_found", "case_id": case_id})
    except InputError as exc:
        return _input_error(exc)
    except ValueError as exc:
        return JSONResponse(content=api_error(str(exc), "validation_error", None), status_code=422)


@app.post("/api/v1/cases/{case_id}/operating-plan/preview")
async def operating_plan_preview(case_id: str, request: Request):
    try:
        case = repository.get_case(case_id)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "Case not found", "error_type": "case_not_found", "case_id": case_id})
    try:
        payload = loads_json(await request.body())
        if not isinstance(payload, dict):
            raise InputError("validation_error", "Operating-plan request must be an object")
        required = {"case_id", "selected_plan_variant", "planning_input_source", "rows", "working_capital_rows", "cash_assumption_rows"}
        missing = sorted(required - set(payload))
        if missing:
            raise InputError("validation_error", "Operating-plan request is incomplete", {"missing": missing})
        unknown = sorted(set(payload) - (required | {"actions", "headcount_rows"}))
        if unknown:
            raise InputError("unexpected_input_key", "Unexpected operating-plan request field", {"fields": unknown})
        if payload["case_id"] != case_id:
            raise InputError("invalid_case", "Request case_id does not match path", {"case_id": payload["case_id"]})
        if payload["planning_input_source"] not in {"upload", "editor"}:
            raise InputError("invalid_input_source", "Preview source must be upload or editor")
        if payload["selected_plan_variant"] not in {"base", "upside", "downside"}:
            raise InputError("invalid_variant", "Unknown plan variant")
        if "actions" in payload and not isinstance(payload["actions"], list):
            raise InputError("validation_error", "actions must be a list")
        return build_operating_decision(case, payload["selected_plan_variant"], payload["planning_input_source"], payload["rows"], payload["working_capital_rows"], payload["cash_assumption_rows"], payload.get("actions"), payload.get("headcount_rows"))
    except InputError as exc:
        return _input_error(exc)
    except ValueError as exc:
        return JSONResponse(content=api_error(str(exc), "rollup_reconciliation_failed", None), status_code=422)


frontend = ROOT_DIR / "web" / "dist"
if frontend.is_dir():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def frontend_root():
    index = frontend / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"app": settings.app_name, "message": "Frontend build not found. Run scripts/rebuild_workspace.sh."}


@app.get("/{path:path}", include_in_schema=False)
def frontend_fallback(path: str):
    if path.startswith(("api/", "docs", "redoc", "openapi.json", "health")):
        raise HTTPException(status_code=404, detail={"error": "Not found", "error_type": "not_found"})
    index = frontend / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail={"error": "Frontend not built", "error_type": "frontend_not_built"})
