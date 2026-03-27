"""
Custom exception classes and error handling utilities for I-ASCAP API.
"""

from typing import Any

from fastapi import HTTPException


class APIError(HTTPException):
    """Base exception for API errors."""

    def __init__(
        self,
        status_code: int = 500,
        detail: str = "An unexpected error occurred",
        error_code: str = "INTERNAL_ERROR",
        context: dict[str, Any] | None = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.context = context or {}


class ValidationError(APIError):
    """Raised when input validation fails."""

    def __init__(
        self,
        detail: str = "Validation failed",
        field: str | None = None,
        value: Any | None = None
    ):
        context = {}
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)[:100]  # type: ignore

        super().__init__(
            status_code=400,
            detail=detail,
            error_code="VALIDATION_ERROR",
            context=context
        )


class NotFoundError(APIError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str = "Resource",
        resource_id: str | None = None
    ):
        detail = f"{resource_type} not found"
        if resource_id:
            detail = f"{resource_type} '{resource_id}' not found"

        super().__init__(
            status_code=404,
            detail=detail,
            error_code="NOT_FOUND",
            context={"resource_type": resource_type, "resource_id": resource_id}
        )


class DatabaseError(APIError):
    """Raised when a database operation fails."""

    def __init__(
        self,
        detail: str = "Database operation failed",
        operation: str | None = None
    ):
        super().__init__(
            status_code=500,
            detail=detail,
            error_code="DATABASE_ERROR",
            context={"operation": operation} if operation else {}
        )


class RateLimitError(APIError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        retry_after: int = 60
    ):
        super().__init__(
            status_code=429,
            detail=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
            error_code="RATE_LIMIT_EXCEEDED",
            context={
                "retry_after": retry_after})


class DataQualityError(APIError):
    """Raised when data quality issues are detected."""

    def __init__(
        self,
        detail: str = "Data quality issue detected",
        affected_records: int = 0
    ):
        super().__init__(
            status_code=422,
            detail=detail,
            error_code="DATA_QUALITY_ERROR",
            context={"affected_records": affected_records}
        )


# Error response schema for consistent API responses
def create_error_response(
    error: APIError,
    request_id: str | None = None
) -> dict[str, Any]:
    """Create a standardized error response."""
    response: dict[str, Any] = {
        "success": False,
        "error": {
            "code": error.error_code,
            "message": error.detail,
            "status_code": error.status_code,
        }
    }

    if error.context:
        response["error"]["context"] = error.context

    if request_id:
        response["request_id"] = request_id

    return response
