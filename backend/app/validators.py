"""
Data validation utilities for I-ASCAP API.
Provides centralized validation functions and constants.
"""

import re
from datetime import datetime
from typing import Any

from .exceptions import ValidationError  # type: ignore

# Valid year range for agricultural data
YEAR_MIN = 1966
YEAR_MAX = datetime.now().year

# Valid crops in the database
VALID_CROPS: set[str] = {
    "rice",
    "wheat",
    "maize",
    "jowar",
    "bajra",
    "ragi",
    "barley",
    "sorghum",
    "millet",
    "groundnut",
    "cotton",
    "sugarcane",
    "tobacco",
    "jute",
    "potato",
    "onion",
    "pulses",
    "oilseeds",
    "cereals",
    "foodgrains",
    # Crops available in frontend Dashboard selector
    "soyabean",
    "sesamum",
    "rapeseed_and_mustard",
    "sunflower",
    "chickpea",
    "pigeonpea",
    "finger_millet",
    "pearl_millet",
}

# Valid metrics
VALID_METRICS: set[str] = {"area", "production", "yield"}

# Valid comparison modes
VALID_MODES: set[str] = {"before_after", "entity_comparison", "longitudinal"}

# Regex patterns
CDK_PATTERN = re.compile(r"^[A-Z]{2}_[a-z0-9]+_\d{4}$")
SAFE_STRING_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-_.]+$")


def validate_year(year: Any, field_name: str = "year") -> int:
    """Validate and return a year within the valid range."""
    try:
        year_int = int(year)
    except (ValueError, TypeError) as exc:
        raise ValidationError(detail=f"Invalid {field_name}: must be an integer", field=field_name, value=year) from exc

    if year_int < YEAR_MIN or year_int > YEAR_MAX:
        raise ValidationError(
            detail=f"Invalid {field_name}: must be between {YEAR_MIN} and {YEAR_MAX}", field=field_name, value=year_int
        )

    return year_int


def validate_year_range(start_year: Any, end_year: Any) -> tuple:
    """Validate a year range and ensure start <= end."""
    start = validate_year(start_year, "start_year")
    end = validate_year(end_year, "end_year")

    if start > end:
        raise ValidationError(
            detail="start_year must be less than or equal to end_year", field="year_range", value=f"{start}-{end}"
        )

    return (start, end)


def validate_crop(crop: str) -> str:
    """Validate that crop is in allowed list."""
    if not crop:
        raise ValidationError(detail="Crop name is required", field="crop")

    crop_lower = crop.lower().strip()
    if crop_lower not in VALID_CROPS:
        raise ValidationError(
            detail=f"Invalid crop: '{crop}'. Valid options: {', '.join(sorted(VALID_CROPS)[:10])}...",  # type: ignore
            field="crop",
            value=crop,
        )

    return crop_lower


def validate_metric(metric: str) -> str:
    """Validate that metric is in allowed list."""
    if not metric:
        raise ValidationError(detail="Metric is required", field="metric")

    metric_lower = metric.lower().strip()
    if metric_lower not in VALID_METRICS:
        raise ValidationError(
            detail=f"Invalid metric: '{metric}'. Valid options: {', '.join(VALID_METRICS)}",
            field="metric",
            value=metric,
        )

    return metric_lower


def validate_mode(mode: str | None) -> str:
    """Validate comparison mode."""
    if not mode:
        return "before_after"  # Default

    mode_lower = mode.lower().strip()
    if mode_lower not in VALID_MODES:
        raise ValidationError(
            detail=f"Invalid mode: '{mode}'. Valid options: {', '.join(VALID_MODES)}", field="mode", value=mode
        )

    return mode_lower


def validate_cdk(cdk: str) -> str:
    """Validate a district CDK (Canonical District Key)."""
    if not cdk:
        raise ValidationError(detail="District CDK is required", field="cdk")

    cdk_stripped = cdk.strip()

    # Basic format validation (relaxed to allow numeric LGD codes like '107')
    if len(cdk_stripped) < 1 or len(cdk_stripped) > 50:
        raise ValidationError(
            detail="Invalid CDK format: length must be between 1 and 50 characters", field="cdk", value=cdk
        )

    return cdk_stripped


def validate_cdk_list(cdks: str) -> list[str]:
    """Validate a comma-separated list of CDKs."""
    if not cdks:
        raise ValidationError(detail="CDK list is required", field="cdks")

    cdk_list = [c.strip() for c in cdks.split(",") if c.strip()]

    if len(cdk_list) == 0:
        raise ValidationError(detail="CDK list cannot be empty", field="cdks")

    if len(cdk_list) > 20:
        raise ValidationError(
            detail="Too many CDKs: maximum 20 allowed", field="cdks", value=f"{len(cdk_list)} provided"
        )

    return [validate_cdk(c) for c in cdk_list]


def validate_state_name(state: str) -> str:
    """Validate and sanitize state name."""
    if not state:
        raise ValidationError(detail="State name is required", field="state")

    state_stripped = state.strip()

    if len(state_stripped) < 2 or len(state_stripped) > 100:
        raise ValidationError(detail="Invalid state name length", field="state", value=state)

    # Basic sanitization - allow letters, spaces, and common punctuation
    if not re.match(r"^[a-zA-Z\s\-&]+$", state_stripped):
        raise ValidationError(detail="State name contains invalid characters", field="state", value=state)

    return state_stripped


def validate_limit(limit: Any, max_limit: int = 1000) -> int:
    """Validate pagination limit."""
    try:
        limit_int = int(limit)
    except (ValueError, TypeError) as exc:
        raise ValidationError(detail="Limit must be an integer", field="limit", value=limit) from exc

    if limit_int < 1:
        limit_int = 10
    elif limit_int > max_limit:
        limit_int = max_limit

    return limit_int


def validate_offset(offset: Any) -> int:
    """Validate pagination offset."""
    try:
        offset_int = int(offset)
    except (ValueError, TypeError) as exc:
        raise ValidationError(detail="Offset must be an integer", field="offset", value=offset) from exc

    if offset_int < 0:
        offset_int = 0

    return offset_int


def validate_positive_number(value: Any, field_name: str = "value") -> float:
    """Validate that a value is a positive number."""
    try:
        num = float(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(detail=f"{field_name} must be a number", field=field_name, value=value) from exc

    if num < 0:
        raise ValidationError(detail=f"{field_name} must be non-negative", field=field_name, value=num)

    return num
