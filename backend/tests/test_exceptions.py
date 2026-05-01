"""
Tests for the exceptions module.
"""
from app.exceptions import (
    APIError,
    DatabaseError,
    DataQualityError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    create_error_response,
)


class TestAPIError:
    """Tests for APIError class."""

    def test_default_values(self):
        error = APIError()
        assert error.status_code == 500
        assert error.detail == "An unexpected error occurred"
        assert error.error_code == "INTERNAL_ERROR"
        assert error.context == {}

    def test_custom_values(self):
        error = APIError(
            status_code=400,
            detail="Custom error",
            error_code="CUSTOM_ERROR",
            context={"key": "value"}
        )
        assert error.status_code == 400
        assert error.detail == "Custom error"
        assert error.error_code == "CUSTOM_ERROR"
        assert error.context == {"key": "value"}


class TestValidationError:
    """Tests for ValidationError class."""

    def test_default_values(self):
        error = ValidationError()
        assert error.status_code == 400
        assert error.error_code == "VALIDATION_ERROR"

    def test_with_field(self):
        error = ValidationError(detail="Invalid value", field="year", value=2100)
        assert error.context["field"] == "year"
        assert error.context["value"] == "2100"

    def test_long_value_truncation(self):
        long_value = "x" * 200
        error = ValidationError(detail="Too long", value=long_value)
        assert len(error.context["value"]) <= 100


class TestNotFoundError:
    """Tests for NotFoundError class."""

    def test_default_values(self):
        error = NotFoundError()
        assert error.status_code == 404
        assert "not found" in error.detail.lower()

    def test_with_resource(self):
        error = NotFoundError(resource_type="District", resource_id="UP_agra_1971")
        assert "District" in error.detail
        assert "UP_agra_1971" in error.detail


class TestDatabaseError:
    """Tests for DatabaseError class."""

    def test_default_values(self):
        error = DatabaseError()
        assert error.status_code == 500
        assert error.error_code == "DATABASE_ERROR"

    def test_with_operation(self):
        error = DatabaseError(detail="Query failed", operation="SELECT")
        assert error.context["operation"] == "SELECT"


class TestRateLimitError:
    """Tests for RateLimitError class."""

    def test_default_retry_after(self):
        error = RateLimitError()
        assert error.status_code == 429
        assert error.context["retry_after"] == 60

    def test_custom_retry_after(self):
        error = RateLimitError(retry_after=120)
        assert "120 seconds" in error.detail


class TestDataQualityError:
    """Tests for DataQualityError class."""

    def test_default_values(self):
        error = DataQualityError()
        assert error.status_code == 422
        assert error.context["affected_records"] == 0

    def test_with_affected_records(self):
        error = DataQualityError(affected_records=100)
        assert error.context["affected_records"] == 100


class TestCreateErrorResponse:
    """Tests for create_error_response function."""

    def test_basic_response(self):
        error = APIError(status_code=400, detail="Test error")
        response = create_error_response(error)

        assert response["success"] is False
        assert response["error"]["message"] == "Test error"
        assert response["error"]["status_code"] == 400

    def test_with_request_id(self):
        error = ValidationError(detail="Invalid")
        response = create_error_response(error, request_id="abc123")

        assert response["request_id"] == "abc123"

    def test_with_context(self):
        error = ValidationError(detail="Invalid", field="year")
        response = create_error_response(error)

        assert "context" in response["error"]
        assert response["error"]["context"]["field"] == "year"
