"""Unit tests for changelog service."""

import pytest

from plan_manager.domain.models import Task
from plan_manager.services import changelog_service


class TestGenerateChangelogForTask:
    """Test generate_changelog_for_task function."""

    def test_generate_with_valid_category(self):
        """Test generating changelog with valid category."""
        task = Task(
            id="story-1:task-1",
            title="Implement login",
            story_id="story-1",
            local_id="task-1",
            changelog_entries=[
                "Added POST /auth/login endpoint",
                "Implemented JWT tokens",
            ],
        )

        result = changelog_service.generate_changelog_for_task(
            task, category="Added", version="0.9.0", date="2025-01-19"
        )

        assert "## [0.9.0] - 2025-01-19" in result
        assert "### Added" in result
        assert "- Added POST /auth/login endpoint" in result
        assert "- Implemented JWT tokens" in result

    def test_generate_without_version(self):
        """Test generating changelog without version."""
        task = Task(
            id="story-1:task-1",
            title="Fix bug",
            story_id="story-1",
            local_id="task-1",
            changelog_entries=["Fixed authentication bug"],
        )

        result = changelog_service.generate_changelog_for_task(task, category="Fixed")

        assert "### Fixed" in result
        assert "- Fixed authentication bug" in result
        # No version header should be present (should not have "## [" pattern)
        assert "## [" not in result

    def test_generate_with_empty_entries(self):
        """Test generating changelog with empty entries list."""
        task = Task(
            id="story-1:task-1",
            title="Task",
            story_id="story-1",
            local_id="task-1",
            changelog_entries=[],
        )

        result = changelog_service.generate_changelog_for_task(task, category="Changed")

        assert "### Changed" in result
        assert "- No entries provided" in result

    def test_invalid_category_raises(self):
        """Test that invalid category raises ValueError."""
        task = Task(
            id="story-1:task-1",
            title="Task",
            story_id="story-1",
            local_id="task-1",
            changelog_entries=["Entry"],
        )

        with pytest.raises(ValueError, match="Invalid category"):
            changelog_service.generate_changelog_for_task(
                task, category="InvalidCategory"
            )


class TestGenerateCommitMessageForTask:
    """Test generate_commit_message_for_task function."""

    def test_generate_with_valid_type(self):
        """Test generating commit message with valid type."""
        task = Task(
            id="story-1:task-1",
            title="Implement login",
            story_id="story-1",
            local_id="task-1",
            changelog_entries=[
                "Added POST /auth/login endpoint",
                "Implemented JWT tokens",
            ],
        )

        result = changelog_service.generate_commit_message_for_task(
            task, commit_type="feat"
        )

        assert "feat(task-1): Implement login" in result
        assert "- Added POST /auth/login endpoint" in result
        assert "- Implemented JWT tokens" in result
        assert "Refs: story-1" in result

    def test_generate_without_story_id(self):
        """Test generating commit message without story_id."""
        task = Task(
            id="task-1",
            title="Fix bug",
            local_id="task-1",
            changelog_entries=["Fixed bug"],
        )

        result = changelog_service.generate_commit_message_for_task(
            task, commit_type="fix"
        )

        assert "fix(task-1): Fix bug" in result
        assert "- Fixed bug" in result
        assert "Refs:" not in result  # No story reference

    def test_generate_with_empty_entries(self):
        """Test generating commit message with empty entries."""
        task = Task(
            id="story-1:task-1",
            title="Task",
            story_id="story-1",
            local_id="task-1",
            changelog_entries=[],
        )

        result = changelog_service.generate_commit_message_for_task(
            task, commit_type="chore"
        )

        assert "chore(task-1): Task" in result
        assert "Refs: story-1" in result
        # Should not have bullet points if no entries

    def test_invalid_commit_type_raises(self):
        """Test that invalid commit type raises ValueError."""
        task = Task(
            id="story-1:task-1",
            title="Task",
            story_id="story-1",
            local_id="task-1",
            changelog_entries=["Entry"],
        )

        with pytest.raises(ValueError, match="Invalid commit type"):
            changelog_service.generate_commit_message_for_task(
                task, commit_type="invalid"
            )

    def test_extracts_local_id_from_full_id(self):
        """Test that local_id is extracted from full task ID if local_id is not set."""
        task = Task(
            id="story-1:my-task-id",
            title="Task",
            story_id="story-1",
            changelog_entries=["Entry"],
        )

        result = changelog_service.generate_commit_message_for_task(
            task, commit_type="feat"
        )

        assert "feat(my-task-id): Task" in result
