"""RFC 7807 Problem Details error model + handlers.

See ADR-0008. The shape of every error response is governed by
`ProblemDetail` regardless of where the exception came from.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_BASE_URL = "https://brokerapp.orbiter/problems"


class FieldError(BaseModel):
    field: str
    message: str


class ProblemDetail(BaseModel):
    """RFC 7807 envelope plus our standard extension fields."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(default=f"{PROBLEM_BASE_URL}/about-blank")
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    code: str
    request_id: str | None = None
    errors: list[FieldError] | None = None


class APIError(Exception):
    """Raise from route handlers to produce a typed Problem response."""

    def __init__(
        self,
        *,
        code: str,
        status_code: int,
        title: str,
        detail: str | None = None,
        problem_type: str | None = None,
        errors: list[FieldError] | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.problem_type = problem_type or f"{PROBLEM_BASE_URL}/{code.replace('.', '-')}"
        self.errors = errors
        super().__init__(detail or title)


# Convenience constructors ---------------------------------------------------


def not_found(code: str, detail: str) -> APIError:
    return APIError(
        code=code,
        status_code=status.HTTP_404_NOT_FOUND,
        title="Not found",
        detail=detail,
    )


def conflict(code: str, detail: str) -> APIError:
    return APIError(
        code=code,
        status_code=status.HTTP_409_CONFLICT,
        title="Conflict",
        detail=detail,
    )


def unauthorized(
    code: str = "auth.unauthorized", detail: str = "Authentication required."
) -> APIError:
    return APIError(
        code=code,
        status_code=status.HTTP_401_UNAUTHORIZED,
        title="Unauthorized",
        detail=detail,
    )


def forbidden(code: str = "auth.forbidden", detail: str = "Insufficient permissions.") -> APIError:
    return APIError(
        code=code,
        status_code=status.HTTP_403_FORBIDDEN,
        title="Forbidden",
        detail=detail,
    )


def bad_request(code: str, detail: str) -> APIError:
    return APIError(
        code=code,
        status_code=status.HTTP_400_BAD_REQUEST,
        title="Bad request",
        detail=detail,
    )


# Handlers -------------------------------------------------------------------


def _request_id(request: Request) -> str | None:
    rid = request.headers.get("x-request-id")
    if rid:
        return rid
    state = getattr(request, "state", None)
    return getattr(state, "request_id", None) if state else None


def _problem_response(problem: ProblemDetail) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
    )


async def api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, APIError)
    return _problem_response(
        ProblemDetail(
            type=exc.problem_type,
            title=exc.title,
            status=exc.status_code,
            detail=exc.detail,
            instance=str(request.url.path),
            code=exc.code,
            request_id=_request_id(request),
            errors=exc.errors,
        ),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return _problem_response(
        ProblemDetail(
            title=exc.detail or "HTTP error",
            status=exc.status_code,
            detail=exc.detail if isinstance(exc.detail, str) else None,
            instance=str(request.url.path),
            code=f"http.{exc.status_code}",
            request_id=_request_id(request),
        ),
    )


async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    field_errors = [
        FieldError(
            field=".".join(str(p) for p in err["loc"]),
            message=err["msg"],
        )
        for err in exc.errors()
    ]
    return _problem_response(
        ProblemDetail(
            title="Validation failed",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more fields failed validation.",
            instance=str(request.url.path),
            code="validation.failed",
            request_id=_request_id(request),
            errors=field_errors,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler so we never leak stack traces."""
    return _problem_response(
        ProblemDetail(
            title="Internal server error",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The server encountered an unexpected error.",
            instance=str(request.url.path),
            code="server.internal_error",
            request_id=_request_id(request),
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


__all__ = [
    "APIError",
    "FieldError",
    "ProblemDetail",
    "bad_request",
    "conflict",
    "forbidden",
    "not_found",
    "register_error_handlers",
    "unauthorized",
]


# silence "imported but unused" if a downstream consumer trims
_ = Any
