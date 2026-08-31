"""FastAPI application for the deterministic MINISO FP&A case."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import ROOT_DIR, settings
from src.repositories.case_repository import CaseNotFoundError, CaseRepository
from src.services.planning_service import build_dashboard


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
    allow_methods=["GET"],
    allow_headers=["*"],
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
):
    try:
        case = repository.get_case(case_id)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "Case not found", "error_type": "case_not_found", "case_id": case_id})
    return build_dashboard(case, brand, market)


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
