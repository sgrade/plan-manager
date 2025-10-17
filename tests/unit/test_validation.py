"""Unit tests for validation module."""

import pytest

from plan_manager.validation import (
    validate_acceptance_criteria,
    validate_description,
    validate_title,
)


class TestValidateTitle:
    """Test title validation."""

    def test_valid_title(self):
        """Test that a valid title is accepted."""
        result = validate_title("Valid Title")
        assert result == "Valid Title"

    def test_empty_title_raises_error(self):
        """Test that an empty title raises ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            validate_title("")

    def test_whitespace_only_title_returns_empty(self):
        """Test that a whitespace-only title returns empty after strip."""
        # Note: validate_title checks "if not title" before strip,
        # so "   " passes the check but gets stripped to ""
        result = validate_title("   ")
        assert result == ""

    def test_none_title_raises_error(self):
        """Test that None title raises ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            validate_title(None)

    def test_title_strips_whitespace(self):
        """Test that title whitespace is stripped."""
        result = validate_title("  Title with spaces  ")
        assert result == "Title with spaces"

    def test_long_title(self):
        """Test that very long titles raise ValueError (max 200)."""
        long_title = "A" * 500
        with pytest.raises(ValueError, match="Title too long"):
            validate_title(long_title)

    def test_max_length_title(self):
        """Test that title at max length is accepted."""
        max_title = "A" * 200
        result = validate_title(max_title)
        assert result == max_title


class TestValidateDescription:
    """Test description validation."""

    def test_valid_description(self):
        """Test that a valid description is accepted."""
        result = validate_description("Valid description")
        assert result == "Valid description"

    def test_none_description(self):
        """Test that None description is accepted."""
        result = validate_description(None)
        assert result is None

    def test_empty_description(self):
        """Test that empty description returns empty string after strip."""
        result = validate_description("")
        assert result == ""

    def test_whitespace_only_description(self):
        """Test that whitespace-only description returns empty string after strip."""
        result = validate_description("   ")
        assert result == ""

    def test_description_strips_whitespace(self):
        """Test that description whitespace is stripped."""
        result = validate_description("  Description with spaces  ")
        assert result == "Description with spaces"


class TestValidateAcceptanceCriteria:
    """Test acceptance criteria validation."""

    def test_valid_criteria_list(self):
        """Test that a valid criteria list is accepted."""
        criteria = ["Criterion 1", "Criterion 2"]
        result = validate_acceptance_criteria(criteria)
        assert result == criteria

    def test_none_criteria(self):
        """Test that None criteria is accepted."""
        result = validate_acceptance_criteria(None)
        assert result is None

    def test_empty_list(self):
        """Test that empty list raises ValueError."""
        with pytest.raises(ValueError, match="Acceptance criteria cannot be empty"):
            validate_acceptance_criteria([])

    def test_criteria_with_empty_strings_raises(self):
        """Test that empty strings in criteria raise ValueError."""
        criteria = ["Valid", "", "  ", "Another valid"]
        with pytest.raises(ValueError, match="Acceptance criterion .* cannot be empty"):
            validate_acceptance_criteria(criteria)

    def test_all_empty_strings_raises(self):
        """Test that list with only empty strings raises ValueError."""
        criteria = ["", "  ", "   "]
        with pytest.raises(ValueError, match="Acceptance criterion .* cannot be empty"):
            validate_acceptance_criteria(criteria)

    def test_criteria_strips_whitespace(self):
        """Test that criteria items have whitespace stripped."""
        criteria = ["  First  ", "  Second  "]
        result = validate_acceptance_criteria(criteria)
        assert result == ["First", "Second"]
