"""Input validation utilities for Plan Manager."""

import re
from typing import Any, Optional

# Input length limits
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_ACCEPTANCE_CRITERIA_LENGTH = 5000
MAX_CHANGELOG_ENTRY_LENGTH = 500
MAX_FEEDBACK_LENGTH = 2000

# Regular expression for safe identifiers (alphanumeric, hyphens, underscores)
SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# Regular expression for safe text (no control characters except newlines/tabs)
SAFE_TEXT_PATTERN = re.compile(r"^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]*$")

# Reserved words that shouldn't be used in identifiers
RESERVED_WORDS = {
    "null",
    "none",
    "undefined",
    "true",
    "false",
    "admin",
    "system",
    "root",
    "config",
    "settings",
}


def validate_title(title: str) -> str:
    """Validate and sanitize a title.

    Args:
        title: The title to validate

    Returns:
        str: The validated title

    Raises:
        ValueError: If the title is invalid
    """
    if not title:
        raise ValueError("Title cannot be empty")

    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"Title too long (max {MAX_TITLE_LENGTH} characters)")

    if not SAFE_TEXT_PATTERN.match(title):
        raise ValueError("Title contains invalid characters")

    # Prevent colon in titles as it's used as a separator in fully qualified IDs
    if ":" in title:
        raise ValueError("Title cannot contain ':' (reserved as ID separator)")

    return title.strip()


def validate_description(description: Optional[str]) -> Optional[str]:
    """Validate and sanitize a description.

    Args:
        description: The description to validate (can be None)

    Returns:
        Optional[str]: The validated description

    Raises:
        ValueError: If the description is invalid
    """
    if description is None:
        return None

    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(
            f"Description too long (max {MAX_DESCRIPTION_LENGTH} characters)"
        )

    if not SAFE_TEXT_PATTERN.match(description):
        raise ValueError("Description contains invalid characters")

    return description.strip()


def validate_acceptance_criteria(criteria: Optional[list[str]]) -> Optional[list[str]]:
    """Validate acceptance criteria.

    Args:
        criteria: List of acceptance criteria strings

    Returns:
        Optional[List[str]]: Validated criteria

    Raises:
        ValueError: If criteria are invalid
    """
    if criteria is None:
        return None

    if not isinstance(criteria, list):
        raise TypeError("Acceptance criteria must be a list")

    if len(criteria) == 0:
        raise ValueError("Acceptance criteria cannot be empty")

    validated_criteria = []
    total_length = 0

    for i, criterion in enumerate(criteria):
        if not isinstance(criterion, str):
            raise TypeError(f"Acceptance criterion {i + 1} must be a string")

        if not criterion.strip():
            raise ValueError(f"Acceptance criterion {i + 1} cannot be empty")

        if len(criterion) > 500:  # Individual criterion length limit
            raise ValueError(
                f"Acceptance criterion {i + 1} too long (max 500 characters)"
            )

        if not SAFE_TEXT_PATTERN.match(criterion):
            raise ValueError(
                f"Acceptance criterion {i + 1} contains invalid characters"
            )

        validated_criteria.append(criterion.strip())
        total_length += len(criterion)

    if total_length > MAX_ACCEPTANCE_CRITERIA_LENGTH:
        raise ValueError(
            f"Total acceptance criteria too long (max {MAX_ACCEPTANCE_CRITERIA_LENGTH} characters)"
        )

    return validated_criteria


def validate_changes(changes: list[str]) -> list[str]:
    """Validate changes list (PR description / changelog entries).

    Args:
        changes: List of changes to validate

    Returns:
        list[str]: Validated changes

    Raises:
        ValueError: If changes are invalid
    """
    if not changes:
        raise ValueError("Changes list cannot be empty")

    if len(changes) > 50:
        raise ValueError("Too many changes (max 50)")

    validated = []
    for i, change in enumerate(changes):
        if not isinstance(change, str):
            raise TypeError(f"Change {i + 1} must be a string")

        stripped_change = change.strip()
        if not stripped_change:
            raise ValueError(f"Change {i + 1} is empty")

        if len(stripped_change) > MAX_CHANGELOG_ENTRY_LENGTH:
            raise ValueError(
                f"Change {i + 1} too long (max {MAX_CHANGELOG_ENTRY_LENGTH} characters)"
            )

        # Remove leading bullets if present (we'll add them in formatting)
        cleaned_change = stripped_change.lstrip("- ").lstrip("* ").strip()
        validated.append(cleaned_change)

    return validated


def validate_feedback(feedback: str) -> str:
    """Validate feedback text.

    Args:
        feedback: The feedback to validate

    Returns:
        str: The validated feedback

    Raises:
        ValueError: If the feedback is invalid
    """
    if not feedback:
        raise ValueError("Feedback cannot be empty")

    if len(feedback) > MAX_FEEDBACK_LENGTH:
        raise ValueError(f"Feedback too long (max {MAX_FEEDBACK_LENGTH} characters)")

    if not SAFE_TEXT_PATTERN.match(feedback):
        raise ValueError("Feedback contains invalid characters")

    return feedback.strip()


def validate_task_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate task steps structure.

    Args:
        steps: List of step dictionaries

    Returns:
        List[Dict[str, Any]]: Validated steps

    Raises:
        ValueError: If steps are invalid
    """
    if not steps:
        raise ValueError("Steps cannot be empty")

    if not isinstance(steps, list):
        raise TypeError("Steps must be a list")

    if len(steps) > 50:  # Reasonable limit for number of steps
        raise ValueError("Too many steps (max 50)")

    validated_steps = []

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise TypeError(f"Step {i + 1} must be a dictionary")

        if "title" not in step:
            raise ValueError(f"Step {i + 1} missing required 'title' field")

        title = step["title"]
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Step {i + 1} title must be a non-empty string")

        if len(title) > 200:
            raise ValueError(f"Step {i + 1} title too long (max 200 characters)")

        if not SAFE_TEXT_PATTERN.match(title):
            raise ValueError(f"Step {i + 1} title contains invalid characters")

        # Validate optional description
        description = step.get("description")
        if description is not None:
            if not isinstance(description, str):
                raise ValueError(f"Step {i + 1} description must be a string")

            if len(description) > 1000:
                raise ValueError(
                    f"Step {i + 1} description too long (max 1000 characters)"
                )

            if not SAFE_TEXT_PATTERN.match(description):
                raise ValueError(
                    f"Step {i + 1} description contains invalid characters"
                )

        validated_steps.append(
            {
                "title": title.strip(),
                "description": description.strip() if description else None,
            }
        )

    return validated_steps


def validate_identifier(identifier: str, field_name: str = "identifier") -> str:
    """Validate an identifier string.

    Args:
        identifier: The identifier to validate
        field_name: Name of the field for error messages

    Returns:
        str: The validated identifier

    Raises:
        ValueError: If the identifier is invalid
    """
    if not identifier:
        raise ValueError(f"{field_name} cannot be empty")

    if len(identifier) > 100:
        raise ValueError(f"{field_name} too long (max 100 characters)")

    if not SAFE_ID_PATTERN.match(identifier):
        raise ValueError(
            f"{field_name} contains invalid characters (only letters, numbers, hyphens, and underscores allowed)"
        )

    if identifier.lower() in RESERVED_WORDS:
        raise ValueError(f"{field_name} cannot use reserved word '{identifier}'")

    return identifier.strip()
