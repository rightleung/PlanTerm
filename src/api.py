"""FastAPI application for the deterministic MINISO FP&A case."""

from __future__ import annotations

import logging
import time
from copy import deepcopy
from functools import lru_cache
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
from src.models.public_import import CompanyLookupRequest, Exchange, PublicImportRequest, Venue
from src.services.company_profile_service import lookup_company_profile
from src.services.symbol_search_service import search_symbols
from src.services.public_import import preview_public_import
from src.services.public_import.errors import PublicImportException


logger = logging.getLogger(__name__)
repository = CaseRepository(settings.case_dir)


def api_error(error: str, error_type: str, details: dict | None = None) -> dict:
    return {"error": error, "error_type": error_type, "details": details}


@lru_cache(maxsize=32)
def _cached_dashboard(case_id: str, brand: str, market: str, plan_variant: str):
    return build_dashboard(repository.get_case(case_id), brand, market, plan_variant)


@lru_cache(maxsize=8)
def _cached_operating_plan(case_id: str, plan_variant: str):
    return build_operating_decision(repository.get_case(case_id), plan_variant)


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
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class RequestBoundaryMiddleware:
    _requests: dict[tuple[str, int], int] = {}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(("/api/v1/company/", "/api/v1/symbols/", "/api/v1/public-import/")):
            bucket = int(time.monotonic() // 60)
            client = scope.get("client")
            client_host = client[0] if client else "unknown"
            key = (client_host, bucket)
            self._requests[key] = self._requests.get(key, 0) + 1
            self._requests = {item: count for item, count in self._requests.items() if item[1] >= bucket - 1}
            if self._requests[key] > settings.request_rate_limit_per_minute:
                await self._error_response(scope, receive, send, "Too many requests", "rate_limited", 429)
                return

        content_length = next((value for name, value in scope.get("headers", []) if name.lower() == b"content-length"), None)
        if content_length:
            try:
                if int(content_length) > settings.max_request_body_bytes:
                    await self._error_response(scope, receive, send, "Request body is too large", "request_too_large", 413)
                    return
            except ValueError:
                await self._error_response(scope, receive, send, "Invalid content length", "validation_error", 400)
                return

        guarded_receive = receive
        if scope.get("method") in {"POST", "PUT", "PATCH"}:
            messages = []
            total = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body = message.get("body", b"")
                total += len(body)
                if total > settings.max_request_body_bytes:
                    await self._error_response(scope, receive, send, "Request body is too large", "request_too_large", 413)
                    return
                messages.append(body)
                if not message.get("more_body", False):
                    break
            index = 0

            async def replay_receive():
                nonlocal index
                if index >= len(messages):
                    return {"type": "http.request", "body": b"", "more_body": False}
                body = messages[index]
                index += 1
                return {"type": "http.request", "body": body, "more_body": index < len(messages)}

            guarded_receive = replay_receive

        async def secured_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                ])
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, guarded_receive, secured_send)

    @staticmethod
    async def _error_response(scope, receive, send, error, error_type, status):
        response = JSONResponse(
            content=api_error(error, error_type),
            status_code=status,
            headers={
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
            },
        )
        await response(scope, receive, send)


app.add_middleware(RequestBoundaryMiddleware)


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
    messages = " ".join(str(item.get("msg", "")) for item in exc.errors()).lower()
    error_type = "validation_error"
    loc_fields = {str(part) for item in exc.errors() for part in item.get("loc", [])}
    if "exchange" in loc_fields and "input should be" in messages:
        error_type = "invalid_exchange"
    elif "venue" in loc_fields and "input should be" in messages:
        error_type = "invalid_venue"
    elif "a-share ticker requires" in messages:
        error_type = "ambiguous_ticker"
    elif "venue is only valid" in messages:
        error_type = "invalid_venue"
    elif "ticker" in loc_fields:
        error_type = "invalid_ticker"
    return JSONResponse(content=api_error("Validation failed", error_type, {"errors": [
        {"loc": [str(part) for part in item.get("loc", [])], "msg": str(item.get("msg", "Validation error")), "type": str(item.get("type", "value_error"))}
        for item in exc.errors()
    ]}), status_code=422)


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    logger.error("Unhandled PlanTerm request error: %s", exc, exc_info=True)
    return JSONResponse(content=api_error("Internal server error", "internal_server_error", {"path": request.url.path}), status_code=500)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.version, "release_id": settings.release_id}


@app.get("/ready")
def readiness() -> dict:
    try:
        case = repository.get_case("miniso-2026")
        frontend_ready = (ROOT_DIR / "web" / "dist" / "index.html").is_file()
        if not frontend_ready:
            raise RuntimeError("frontend build is missing")
        return {"status": "ready", "case_id": case.case_id, "frontend": True}
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        return JSONResponse(content=api_error("Service is not ready", "not_ready"), status_code=503)


@app.post(
    "/api/v1/public-import/preview",
    summary="Preview allowlisted public financial data",
    description="Returns a stateless preview of public reported annual or quarterly data in its native currency and unit. It does not create or modify a case, write files, apply FX conversion, or claim internal company data.",
)
async def public_import_preview(request: PublicImportRequest):
    if not settings.public_import_enabled:
        raise HTTPException(status_code=503, detail={"error": "Public import preview is disabled", "error_type": "provider_unavailable"})
    try:
        return (await preview_public_import(request, rate_interval=settings.public_import_rate_limit_seconds)).model_dump(mode="json")
    except PublicImportException as exc:
        status = {
            "rate_limited": 429,
            "provider_timeout": 504,
            "no_data": 404,
            "provider_unavailable": 502,
            "dependency_missing": 422,
            "malformed_upstream": 422,
        }.get(exc.error_type, 422)
        raise HTTPException(status_code=status, detail={"error": exc.message, "error_type": exc.error_type, **exc.details})


@app.post(
    "/api/v1/company/profile",
    summary="Look up a listed-company profile",
    description="Returns a stateless public company profile for a ticker. The market is inferred for common ticker formats, and explicit exchange/venue fields can disambiguate a listing. It does not create or modify a case.",
)
async def company_profile(payload: CompanyLookupRequest):
    if not settings.company_profile_enabled:
        raise HTTPException(status_code=503, detail={"error": "Company profile lookup is disabled", "error_type": "provider_unavailable"})
    try:
        return (await lookup_company_profile(payload)).model_dump(mode="json")
    except PublicImportException as exc:
        status = {
            "no_data": 404,
            "rate_limited": 429,
            "provider_timeout": 504,
            "provider_unavailable": 502,
            "dependency_missing": 422,
            "unsupported_exchange": 422,
        }.get(exc.error_type, 422)
        raise HTTPException(status_code=status, detail={"error": exc.message, "error_type": exc.error_type, **exc.details})


@app.get(
    "/api/v1/symbols/search",
    summary="Search listed-company symbols",
    description="Searches public equity symbols and optionally filters them by US, HKEX, LSE or an explicit A-share venue.",
)
async def symbol_search(
    q: str = Query(..., min_length=1, max_length=80),
    exchange: Literal["US", "HKEX", "LSE", "A_SHARE"] | None = Query(None),
    venue: Literal["SSE", "SZSE", "BSE"] | None = Query(None),
    limit: int = Query(10, ge=1, le=20),
):
    if not settings.company_profile_enabled:
        raise HTTPException(status_code=503, detail={"error": "Company search is disabled", "error_type": "provider_unavailable"})
    if venue is not None and exchange != "A_SHARE":
        raise HTTPException(status_code=422, detail={"error": "Venue is only valid for A_SHARE", "error_type": "invalid_venue"})
    if exchange == "A_SHARE" and venue == "BSE":
        raise HTTPException(status_code=422, detail={"error": "BSE capability is not approved", "error_type": "unsupported_exchange"})
    try:
        result = await search_symbols(
            q,
            exchange=None if exchange is None else Exchange(exchange),
            venue=None if venue is None else Venue(venue),
            limit=limit,
        )
        return result.model_dump(mode="json")
    except PublicImportException as exc:
        status = 504 if exc.error_type == "provider_timeout" else 422 if exc.error_type == "dependency_missing" else 503
        raise HTTPException(status_code=status, detail={"error": exc.message, "error_type": exc.error_type, **exc.details})


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
        return deepcopy(_cached_dashboard(case_id, brand, market, plan_variant))
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
        if not isinstance(selected, str) or selected not in {"base", "upside", "downside"}: raise InputError("scenario_not_found", "Unknown plan variant")
        source_value = payload.get("planning_input_source", PlanningInputSource.UPLOAD.value)
        try:
            source = PlanningInputSource(source_value)
        except (TypeError, ValueError) as exc:
            raise InputError("invalid_input_source", "Unknown planning input source") from exc
        if source is PlanningInputSource.SEED:
            raise InputError("invalid_input_source", "Preview source must be upload or editor")
        selected_brand = payload.get("brand", brand or "all")
        selected_market = payload.get("market", market or "all")
        if not isinstance(selected_brand, str) or not isinstance(selected_market, str) or selected_brand not in {"all", "MINISO", "TOP_TOY"} or selected_market not in {"all", "mainland", "overseas", "global"}:
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
        return deepcopy(_cached_operating_plan(case_id, plan_variant))
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
        return deepcopy(_cached_operating_plan(case_id, "base")["forecast_accuracy"])
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
        if not isinstance(payload["case_id"], str) or payload["case_id"] != case_id:
            raise InputError("invalid_case", "Request case_id does not match path", {"case_id": payload["case_id"]})
        if not isinstance(payload["planning_input_source"], str) or payload["planning_input_source"] not in {"upload", "editor"}:
            raise InputError("invalid_input_source", "Preview source must be upload or editor")
        if not isinstance(payload["selected_plan_variant"], str) or payload["selected_plan_variant"] not in {"base", "upside", "downside"}:
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
