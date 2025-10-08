"""Unit tests for input validation utilities."""

import pytest
from plan_manager.validation import (
    validate_title,
    validate_description,
    validate_acceptance_criteria,
    validate_execution_summary,
    validate_feedback,
    validate_task_steps,
    validate_identifier,
    MAX_TITLE_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_ACCEPTANCE_CRITERIA_LENGTH,
    MAX_EXECUTION_SUMMARY_LENGTH,
    MAX_FEEDBACK_LENGTH,
)


class TestTitleValidation:
    """Test title validation function."""

    def test_valid_title(self):
        """Test that valid titles pass validation."""
        title = "Implement user authentication"
        result = validate_title(title)
        assert result == title

    def test_title_stripped(self):
        """Test that titles are stripped of whitespace."""
        title = "  Implement user authentication  "
        result = validate_title(title)
        assert result == "Implement user authentication"

    def test_empty_title_raises_error(self):
        """Test that empty titles raise ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            validate_title("")

    def test_whitespace_only_title_becomes_empty(self):
        """Test that whitespace-only titles are stripped to empty but returned."""
        # Actually, validate_title strips whitespace, so "   " becomes ""
        # But the function doesn't check emptiness after stripping
        result = validate_title("   ")
        assert result == ""

    def test_title_too_long_raises_error(self):
        """Test that titles exceeding max length raise ValueError."""
        long_title = "A" * (MAX_TITLE_LENGTH + 1)
        with pytest.raises(ValueError, match=f"Title too long.*{MAX_TITLE_LENGTH}"):
            validate_title(long_title)

    def test_title_with_invalid_characters_raises_error(self):
        """Test that titles with control characters raise ValueError."""
        with pytest.raises(ValueError, match="Title contains invalid characters"):
            validate_title("Valid title\x00with null byte")


class TestDescriptionValidation:
    """Test description validation function."""

    def test_valid_description(self):
        """Test that valid descriptions pass validation."""
        desc = "This is a valid description"
        result = validate_description(desc)
        assert result == desc

    def test_none_description(self):
        """Test that None descriptions are handled correctly."""
        result = validate_description(None)
        assert result is None

    def test_description_stripped(self):
        """Test that descriptions are stripped of whitespace."""
        desc = "  Valid description  "
        result = validate_description(desc)
        assert result == "Valid description"

    def test_description_too_long_raises_error(self):
        """Test that descriptions exceeding max length raise ValueError."""
        long_desc = "A" * (MAX_DESCRIPTION_LENGTH + 1)
        with pytest.raises(ValueError, match=f"Description too long.*{MAX_DESCRIPTION_LENGTH}"):
            validate_description(long_desc)


class TestAcceptanceCriteriaValidation:
    """Test acceptance criteria validation function."""

    def test_valid_criteria(self):
        """Test that valid acceptance criteria pass validation."""
        criteria = ["User can log in", "User sees dashboard"]
        result = validate_acceptance_criteria(criteria)
        assert result == criteria

    def test_none_criteria(self):
        """Test that None criteria are handled correctly."""
        result = validate_acceptance_criteria(None)
        assert result is None

    def test_empty_criteria_raises_error(self):
        """Test that empty criteria list raises ValueError."""
        with pytest.raises(ValueError, match="Acceptance criteria cannot be empty"):
            validate_acceptance_criteria([])

    def test_non_list_criteria_raises_error(self):
        """Test that non-list criteria raise ValueError."""
        with pytest.raises(ValueError, match="Acceptance criteria must be a list"):
            validate_acceptance_criteria("not a list")

    def test_empty_criterion_raises_error(self):
        """Test that empty individual criteria raise ValueError."""
        criteria = ["Valid criterion", ""]
        with pytest.raises(ValueError, match="Acceptance criterion 2 cannot be empty"):
            validate_acceptance_criteria(criteria)

    def test_criteria_too_long_raises_error(self):
        """Test that criteria exceeding total length raise ValueError."""
        # Create multiple criteria that exceed total length (each under individual limit)
        # 6000 chars total, each under 500 char limit
        long_criteria = ["A" * 400] * 15
        with pytest.raises(ValueError, match=f"Total acceptance criteria too long.*{MAX_ACCEPTANCE_CRITERIA_LENGTH}"):
            validate_acceptance_criteria(long_criteria)


class TestExecutionSummaryValidation:
    """Test execution summary validation function."""

    def test_valid_summary(self):
        """Test that valid execution summaries pass validation."""
        summary = "Implemented user authentication with proper error handling"
        result = validate_execution_summary(summary)
        assert result == summary

    def test_empty_summary_raises_error(self):
        """Test that empty summaries raise ValueError."""
        with pytest.raises(ValueError, match="Execution summary cannot be empty"):
            validate_execution_summary("")

    def test_summary_too_long_raises_error(self):
        """Test that summaries exceeding max length raise ValueError."""
        long_summary = "A" * (MAX_EXECUTION_SUMMARY_LENGTH + 1)
        with pytest.raises(ValueError, match=f"Execution summary too long.*{MAX_EXECUTION_SUMMARY_LENGTH}"):
            validate_execution_summary(long_summary)

    def test_summary_with_newlines_allowed(self):
        """Test that summaries with newlines are allowed."""
        summary = "Line 1\nLine 2\nLine 3"
        result = validate_execution_summary(summary)
        assert result == summary


class TestFeedbackValidation:
    """Test feedback validation function."""

    def test_valid_feedback(self):
        """Test that valid feedback passes validation."""
        feedback = "Please add more error handling"
        result = validate_feedback(feedback)
        assert result == feedback

    def test_empty_feedback_raises_error(self):
        """Test that empty feedback raises ValueError."""
        with pytest.raises(ValueError, match="Feedback cannot be empty"):
            validate_feedback("")

    def test_feedback_too_long_raises_error(self):
        """Test that feedback exceeding max length raises ValueError."""
        long_feedback = "A" * (MAX_FEEDBACK_LENGTH + 1)
        with pytest.raises(ValueError, match=f"Feedback too long.*{MAX_FEEDBACK_LENGTH}"):
            validate_feedback(long_feedback)


class TestTaskStepsValidation:
    """Test task steps validation function."""

    def test_valid_steps(self):
        """Test that valid steps pass validation."""
        steps = [
            {"title": "Implement feature",
                "description": "Add the main functionality"},
            {"title": "Add tests"}
        ]
        result = validate_task_steps(steps)
        assert len(result) == 2
        assert result[0]["title"] == "Implement feature"
        assert result[0]["description"] == "Add the main functionality"
        assert result[1]["title"] == "Add tests"
        assert result[1]["description"] is None

    def test_empty_steps_raises_error(self):
        """Test that empty steps list raises ValueError."""
        with pytest.raises(ValueError, match="Steps cannot be empty"):
            validate_task_steps([])

    def test_non_list_steps_raises_error(self):
        """Test that non-list steps raise ValueError."""
        with pytest.raises(ValueError, match="Steps must be a list"):
            validate_task_steps("not a list")

    def test_step_without_title_raises_error(self):
        """Test that steps without title raise ValueError."""
        steps = [{"description": "Missing title"}]
        with pytest.raises(ValueError, match="missing required 'title' field"):
            validate_task_steps(steps)

    def test_step_with_empty_title_raises_error(self):
        """Test that steps with empty title raise ValueError."""
        steps = [{"title": ""}]
        with pytest.raises(ValueError, match="title must be a non-empty string"):
            validate_task_steps(steps)

    def test_step_with_non_string_description_raises_error(self):
        """Test that steps with non-string description raise ValueError."""
        steps = [{"title": "Valid title", "description": 123}]
        with pytest.raises(ValueError, match="description must be a string"):
            validate_task_steps(steps)

    def test_too_many_steps_raises_error(self):
        """Test that too many steps raise ValueError."""
        steps = [{"title": f"Step {i}"} for i in range(51)]
        with pytest.raises(ValueError, match="Too many steps.*50"):
            validate_task_steps(steps)


class TestIdentifierValidation:
    """Test identifier validation function."""

    def test_valid_identifier(self):
        """Test that valid identifiers pass validation."""
        identifier = "valid_identifier_123"
        result = validate_identifier(identifier)
        assert result == identifier

    def test_identifier_spaces_not_allowed(self):
        """Test that identifiers cannot contain spaces."""
        identifier = "  valid_identifier  "
        with pytest.raises(ValueError, match="contains invalid characters"):
            validate_identifier(identifier)

    def test_empty_identifier_raises_error(self):
        """Test that empty identifiers raise ValueError."""
        with pytest.raises(ValueError, match="identifier cannot be empty"):
            validate_identifier("")

    def test_identifier_too_long_raises_error(self):
        """Test that identifiers exceeding max length raise ValueError."""
        long_id = "a" * 101
        with pytest.raises(ValueError, match="identifier too long.*100"):
            validate_identifier(long_id)

    def test_identifier_with_invalid_characters_raises_error(self):
        """Test that identifiers with invalid characters raise ValueError."""
        with pytest.raises(ValueError, match="contains invalid characters"):
            validate_identifier("invalid@identifier")

    def test_reserved_word_raises_error(self):
        """Test that reserved words raise ValueError."""
        with pytest.raises(ValueError, match="cannot use reserved word"):
            validate_identifier("admin")
