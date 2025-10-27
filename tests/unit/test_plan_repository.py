"""Unit tests for plan_repository module.

These tests verify the repository handles both normalized and corrupted data formats.
Tests use the public load() API which internally calls _load_story().
"""

import uuid

import yaml

from plan_manager.config import TODO_DIR
from plan_manager.services import plan_repository


class TestLoadPlanWithNormalizedFormat:
    """Test loading plans with normalized story/task format (string IDs only)."""

    def test_load_plan_with_normalized_story_tasks(self):
        """Test that load() correctly loads stories with string task IDs (normalized format)."""
        # Use centralized TODO_DIR, create unique plan to avoid conflicts
        from pathlib import Path

        test_id = str(uuid.uuid4())[:8]
        plan_id = f"test_plan_{test_id}"
        story_id = f"test_story_{test_id}"

        # Create plan file
        plan_dir = Path(TODO_DIR) / plan_id
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.yaml"
        plan_data = {
            "id": plan_id,
            "title": "Test Plan",
            "status": "TODO",
            "creation_time": "2025-10-27T16:00:00Z",
            "stories": [story_id],
        }
        with plan_file.open("w") as f:
            yaml.safe_dump(plan_data, f)

        # Create story file with string task IDs (normalized format)
        story_dir = plan_dir / story_id
        tasks_dir = story_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        story_file = story_dir / "story.md"
        story_data = {
            "id": story_id,
            "title": "Test Story",
            "status": "TODO",
            "creation_time": "2025-10-27T16:00:00Z",
            "tasks": ["task1", "task2"],  # String IDs (normalized)
        }
        with story_file.open("w") as f:
            f.write("---\n")
            yaml.safe_dump(story_data, f)
            f.write("---\n")

        # Create task files
        for task_local_id in ["task1", "task2"]:
            task_file = tasks_dir / f"{task_local_id}.md"
            task_data = {
                "id": f"{story_id}:{task_local_id}",
                "title": f"Task {task_local_id}",
                "status": "TODO",
                "creation_time": "2025-10-27T16:00:00Z",
                "story_id": story_id,
                "local_id": task_local_id,
            }
            with task_file.open("w") as f:
                f.write("---\n")
                yaml.safe_dump(task_data, f)
                f.write("---\n")

        # Act: load through public API
        plan = plan_repository.load(plan_id)

        # Assert: plan loaded with story and tasks
        assert plan is not None
        assert plan.id == plan_id
        assert len(plan.stories) == 1

        story = plan.stories[0]
        assert story.id == story_id
        assert story.title == "Test Story"
        assert len(story.tasks) == 2
        assert story.tasks[0].local_id == "task1"
        assert story.tasks[1].local_id == "task2"

    def test_load_plan_rejects_story_with_embedded_task_dicts(self, caplog):
        """Test that load() rejects stories with embedded task dicts (corrupted format)."""
        # Use centralized TODO_DIR
        from pathlib import Path

        test_id = str(uuid.uuid4())[:8]
        plan_id = f"test_plan_corrupt_{test_id}"
        story_id = f"story_corrupt_{test_id}"

        # Create plan file
        plan_dir = Path(TODO_DIR) / plan_id
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.yaml"
        plan_data = {
            "id": plan_id,
            "title": "Test Plan Corrupted",
            "status": "TODO",
            "creation_time": "2025-10-27T16:00:00Z",
            "stories": [story_id],
        }
        with plan_file.open("w") as f:
            yaml.safe_dump(plan_data, f)

        # Create corrupted story with embedded task dict
        story_dir = plan_dir / story_id
        story_dir.mkdir(parents=True)
        story_file = story_dir / "story.md"

        story_data = {
            "id": story_id,
            "title": "Corrupted Story",
            "status": "TODO",
            "creation_time": "2025-10-27T16:00:00Z",
            "tasks": [
                # Embedded dict - corrupted format that should be rejected
                {
                    "id": f"{story_id}:task1",
                    "title": "Embedded Task",
                    "status": "TODO",
                    "creation_time": "2025-10-27T16:00:00Z",
                    "story_id": story_id,
                    "local_id": "task1",
                },
            ],
        }
        with story_file.open("w") as f:
            f.write("---\n")
            yaml.safe_dump(story_data, f)
            f.write("---\n")

        # Act: load through public API
        plan = plan_repository.load(plan_id)

        # Assert: plan and story loaded, but embedded dict task was rejected
        assert plan is not None
        assert len(plan.stories) == 1

        story = plan.stories[0]
        assert story.id == story_id
        assert len(story.tasks) == 0  # Embedded dict was rejected

        # Verify error was logged
        assert "Invalid task reference" in caplog.text
        assert "expected string ID" in caplog.text
        assert story_id in caplog.text
