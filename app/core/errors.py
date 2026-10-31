import logging
from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas.error import ApiErrorResponse, ErrorBody, ErrorDetail

logger = logging.getLogger(__name__)


def _status(status):
    try:
        return HTTPStatus(status).name.lower(), HTTPStatus(status).phrase
    except ValueError:
        return "http_error", "Request failed"


def _response(status, message, *, code=None, details=None, legacy_detail=None, headers=None):
    default_code, _ = _status(status)
    body = ApiErrorResponse(
        error=ErrorBody(code=code or default_code, message=message, details=details or []),
        detail=message if legacy_detail is None else legacy_detail,
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"), headers=headers)


async def http_error(request: Request, exc: HTTPException):
    _, fallback = _status(exc.status_code)
    message = exc.detail if isinstance(exc.detail, str) else fallback
    return _response(exc.status_code, message, legacy_detail=exc.detail, headers=exc.headers)


async def validation_error(request: Request, exc: RequestValidationError):
    # Do not echo submitted OTPs, tokens, file bytes, or model exception objects.
    errors = exc.errors()
    details = [ErrorDetail(
        field=".".join(str(part) for part in row.get("loc", ())),
        code=str(row.get("type", "invalid_value")),
        message=str(row.get("msg", "Invalid value")),
    ) for row in errors]
    legacy = [{"loc": row.get("loc", ()), "type": row.get("type", "invalid_value"), "msg": row.get("msg", "Invalid value")} for row in errors]
    return _response(
        422, "Request validation failed", code="validation_error",
        details=details, legacy_detail=legacy,
    )


class ApiErrorMiddleware:
    """Normalize unexpected HTTP errors inside CORS, before a response starts."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except Exception:
            if started:
                raise
            logger.exception("Unhandled HTTP error on %s", scope.get("path", ""))
            response = _response(500, "An unexpected server error occurred", code="internal_error")
            await response(scope, receive, send)


def configure_errors(app):
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_middleware(ApiErrorMiddleware)
