"""Errors the application raises, and how they reach a client.

Domain errors (`AppError` and subclasses) are what services raise; they
know nothing about HTTP. The handlers below are the one place a domain
error becomes a status code and an `ApiErrorResponse`. Every error carries
a machine-readable `code` so a client (and the assistant) can react to a
refusal rather than parse the sentence.
"""

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from src.app.modules.common.schemas import ApiErrorResponse


class AppError(Exception):
    status_code = 500
    default_code = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str = "",
        *,
        code: Optional[str] = None,
        errors: Optional[List[Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.errors = errors
        self.extra = extra or {}

    def __str__(self) -> str:
        return self.message


class BadRequest(AppError):
    status_code = 400
    default_code = "BAD_REQUEST"


class Unauthorized(AppError):
    status_code = 401
    default_code = "UNAUTHORIZED"


class Forbidden(AppError):
    status_code = 403
    default_code = "FORBIDDEN"


class NotFound(AppError):
    status_code = 404
    default_code = "NOT_FOUND"


class Conflict(AppError):
    status_code = 409
    default_code = "CONFLICT"


class Invalid(AppError):
    status_code = 422
    default_code = "INVALID"


class TooMany(AppError):
    status_code = 429
    default_code = "TOO_MANY_REQUESTS"


class Unavailable(AppError):
    status_code = 503
    default_code = "UNAVAILABLE"


class UpstreamFailed(AppError):
    status_code = 502
    default_code = "UPSTREAM_FAILED"


class ConfirmationRequired(AppError):
    """A write was requested without the confirmation step. Not an error
    in the usual sense: the client is expected to show the draft and ask."""

    status_code = 409
    default_code = "CONFIRMATION_REQUIRED"


class UnsupportedAnswer(AppError):
    """The policy corpus does not cover the question. Returned instead of
    a guess."""

    status_code = 404
    default_code = "UNSUPPORTED_ANSWER"


def _response(status_code: int, code: str, message: str, errors=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(
            errorCode=code, message=message, errors=errors
        ).model_dump(),
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.opt(exception=exc).error(
            f"{exc.code} on {request.method} {request.url.path}: {exc.message}"
        )
    return _response(exc.status_code, exc.code, exc.message, exc.errors)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "message" in detail:
        return _response(
            exc.status_code,
            detail.get("code") or f"HTTP_{exc.status_code}",
            str(detail["message"]),
            detail.get("errors"),
        )
    return _response(exc.status_code, f"HTTP_{exc.status_code}", str(detail))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(x) for x in e["loc"]),
            "message": e["msg"],
            "type": e["type"],
        }
        for e in exc.errors()
    ]
    return _response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "Validation failed",
        errors,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """The traceback goes to the log; the client gets a fixed sentence.
    A stack frame in a response is a map of the server."""
    logger.opt(exception=exc).error(
        f"Unhandled error on {request.method} {request.url.path}"
    )
    return _response(
        500, "INTERNAL_ERROR", "Something went wrong on our side. It has been logged."
    )
