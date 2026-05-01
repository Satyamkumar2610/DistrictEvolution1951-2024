"""
Tests for the validators module.
"""
import pytest

from app.exceptions import ValidationError
from app.validators import (
    YEAR_MAX,
    YEAR_MIN,
    validate_cdk,
    validate_cdk_list,
    validate_crop,
    validate_limit,
    validate_metric,
    validate_mode,
    validate_offset,
    validate_positive_number,
    validate_state_name,
    validate_year,
    validate_year_range,
)


class TestValidateYear:
    """Tests for validate_year function."""

    def test_valid_year(self):
        assert validate_year(2000) == 2000
        assert validate_year("2010") == 2010
        assert validate_year(YEAR_MIN) == YEAR_MIN
        assert validate_year(YEAR_MAX) == YEAR_MAX

    def test_invalid_year_type(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_year("not_a_year")
        assert "must be an integer" in str(exc_info.value.detail)

    def test_year_out_of_range(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_year(1900)
        assert f"between {YEAR_MIN} and {YEAR_MAX}" in str(exc_info.value.detail)

        with pytest.raises(ValidationError):
            validate_year(2100)


class TestValidateYearRange:
    """Tests for validate_year_range function."""

    def test_valid_range(self):
        start, end = validate_year_range(2000, 2020)
        assert start == 2000
        assert end == 2020

    def test_same_year(self):
        start, end = validate_year_range(2010, 2010)
        assert start == end == 2010

    def test_invalid_range(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_year_range(2020, 2000)
        assert "less than or equal to" in str(exc_info.value.detail)


class TestValidateCrop:
    """Tests for validate_crop function."""

    def test_valid_crops(self):
        for crop in ["rice", "wheat", "maize"]:
            assert validate_crop(crop) == crop

    def test_case_insensitive(self):
        assert validate_crop("RICE") == "rice"
        assert validate_crop("Wheat") == "wheat"

    def test_strip_whitespace(self):
        assert validate_crop("  rice  ") == "rice"

    def test_invalid_crop(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_crop("invalid_crop")
        assert "Invalid crop" in str(exc_info.value.detail)

    def test_empty_crop(self):
        with pytest.raises(ValidationError):
            validate_crop("")


class TestValidateMetric:
    """Tests for validate_metric function."""

    def test_valid_metrics(self):
        for metric in ["area", "production", "yield"]:
            assert validate_metric(metric) == metric

    def test_invalid_metric(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_metric("invalid")
        assert "Invalid metric" in str(exc_info.value.detail)


class TestValidateMode:
    """Tests for validate_mode function."""

    def test_valid_modes(self):
        assert validate_mode("before_after") == "before_after"
        assert validate_mode("entity_comparison") == "entity_comparison"

    def test_default_mode(self):
        assert validate_mode("") == "before_after"
        assert validate_mode(None) == "before_after"

    def test_invalid_mode(self):
        with pytest.raises(ValidationError):
            validate_mode("invalid_mode")


class TestValidateCdk:
    """Tests for validate_cdk function."""

    def test_valid_cdk(self):
        assert validate_cdk("UP_agra_1971") == "UP_agra_1971"
        assert validate_cdk("CG_bilasp_1991") == "CG_bilasp_1991"

    def test_strip_whitespace(self):
        assert validate_cdk("  UP_agra_1971  ") == "UP_agra_1971"

    def test_empty_cdk(self):
        with pytest.raises(ValidationError):
            validate_cdk("")


class TestValidateCdkList:
    """Tests for validate_cdk_list function."""

    def test_single_cdk(self):
        result = validate_cdk_list("UP_agra_1971")
        assert result == ["UP_agra_1971"]

    def test_multiple_cdks(self):
        result = validate_cdk_list("UP_agra_1971,CG_bilasp_1991")
        assert len(result) == 2

    def test_too_many_cdks(self):
        many_cdks = ",".join([f"cdk_{i}_2000" for i in range(25)])
        with pytest.raises(ValidationError) as exc_info:
            validate_cdk_list(many_cdks)
        assert "maximum 20" in str(exc_info.value.detail)

    def test_empty_list(self):
        with pytest.raises(ValidationError):
            validate_cdk_list("")


class TestValidateStateName:
    """Tests for validate_state_name function."""

    def test_valid_state(self):
        assert validate_state_name("Uttar Pradesh") == "Uttar Pradesh"
        assert validate_state_name("Tamil Nadu") == "Tamil Nadu"

    def test_invalid_characters(self):
        with pytest.raises(ValidationError):
            validate_state_name("State<script>")

    def test_empty_state(self):
        with pytest.raises(ValidationError):
            validate_state_name("")


class TestValidateLimit:
    """Tests for validate_limit function."""

    def test_valid_limit(self):
        assert validate_limit(50) == 50
        assert validate_limit("100") == 100

    def test_limit_below_min(self):
        assert validate_limit(0) == 10
        assert validate_limit(-5) == 10

    def test_limit_above_max(self):
        assert validate_limit(2000) == 1000  # Default max


class TestValidateOffset:
    """Tests for validate_offset function."""

    def test_valid_offset(self):
        assert validate_offset(0) == 0
        assert validate_offset(100) == 100

    def test_negative_offset(self):
        assert validate_offset(-10) == 0



class TestValidatePositiveNumber:
    """Tests for validate_positive_number function."""

    def test_valid_positive(self):
        assert validate_positive_number(100) == 100.0
        assert validate_positive_number(0) == 0.0
        assert validate_positive_number("50.5") == 50.5

    def test_negative_number(self):
        with pytest.raises(ValidationError):
            validate_positive_number(-10)

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            validate_positive_number("not_a_number")
