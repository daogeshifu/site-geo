from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse

from app.api.routes.audit import router as audit_router
from app.api.routes.demo import router as demo_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.health import router as health_router
from app.api.routes.report import router as report_router
from app.api.routes.tasks import router as task_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.models.responses import error_response

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GEO Audit Service",
    version="1.0.0",
    debug=settings.debug,
    default_response_class=ORJSONResponse,
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> ORJSONResponse:
    return ORJSONResponse(status_code=exc.status_code, content=error_response(exc.message, exc.errors))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> ORJSONResponse:
    return ORJSONResponse(status_code=422, content=error_response("validation error", exc.errors()))


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> ORJSONResponse:
    logger.exception("Unhandled server error", exc_info=exc)
    return ORJSONResponse(status_code=500, content=error_response("internal server error"))


app.include_router(demo_router)
app.include_router(health_router)
app.include_router(discovery_router)
app.include_router(audit_router)
app.include_router(task_router)
app.include_router(report_router)
