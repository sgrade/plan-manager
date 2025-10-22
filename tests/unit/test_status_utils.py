"""Unit tests for status utility functions."""

from plan_manager.domain.models import Status
from plan_manager.services.status_utils import rollup_plan_status, rollup_story_status


class TestRollupStoryStatus:
    """Test rollup_story_status function."""

    def test_empty_list_returns_todo(self):
        """Test that empty task list returns TODO."""
        assert rollup_story_status([]) == Status.TODO

    def test_all_done_returns_done(self):
        """Test that all DONE tasks returns DONE."""
        statuses = [Status.DONE, Status.DONE, Status.DONE]
        assert rollup_story_status(statuses) == Status.DONE

    def test_any_in_progress_returns_in_progress(self):
        """Test that any IN_PROGRESS task returns IN_PROGRESS."""
        statuses = [Status.DONE, Status.IN_PROGRESS, Status.TODO]
        assert rollup_story_status(statuses) == Status.IN_PROGRESS

    def test_any_pending_review_returns_in_progress(self):
        """Test that any PENDING_REVIEW task returns IN_PROGRESS."""
        statuses = [Status.DONE, Status.PENDING_REVIEW, Status.TODO]
        assert rollup_story_status(statuses) == Status.IN_PROGRESS

    def test_mixed_done_and_todo_returns_in_progress(self):
        """Test that mix of DONE and TODO returns IN_PROGRESS (work started)."""
        statuses = [Status.DONE, Status.TODO, Status.TODO]
        assert rollup_story_status(statuses) == Status.IN_PROGRESS

    def test_mixed_done_and_blocked_returns_in_progress(self):
        """Test that mix of DONE and BLOCKED returns IN_PROGRESS."""
        statuses = [Status.DONE, Status.BLOCKED]
        assert rollup_story_status(statuses) == Status.IN_PROGRESS

    def test_mixed_done_and_deferred_returns_in_progress(self):
        """Test that mix of DONE and DEFERRED returns IN_PROGRESS."""
        statuses = [Status.DONE, Status.DEFERRED]
        assert rollup_story_status(statuses) == Status.IN_PROGRESS

    def test_all_todo_returns_todo(self):
        """Test that all TODO tasks returns TODO."""
        statuses = [Status.TODO, Status.TODO]
        assert rollup_story_status(statuses) == Status.TODO

    def test_all_blocked_returns_todo(self):
        """Test that all BLOCKED tasks returns TODO."""
        statuses = [Status.BLOCKED, Status.BLOCKED]
        assert rollup_story_status(statuses) == Status.TODO

    def test_mixed_todo_and_blocked_returns_todo(self):
        """Test that mix of TODO and BLOCKED returns TODO (no work started)."""
        statuses = [Status.TODO, Status.BLOCKED, Status.DEFERRED]
        assert rollup_story_status(statuses) == Status.TODO

    def test_single_done_returns_done(self):
        """Test that single DONE task returns DONE."""
        assert rollup_story_status([Status.DONE]) == Status.DONE

    def test_single_todo_returns_todo(self):
        """Test that single TODO task returns TODO."""
        assert rollup_story_status([Status.TODO]) == Status.TODO

    def test_single_in_progress_returns_in_progress(self):
        """Test that single IN_PROGRESS task returns IN_PROGRESS."""
        assert rollup_story_status([Status.IN_PROGRESS]) == Status.IN_PROGRESS

    def test_accepts_string_values(self):
        """Test that function accepts string values in addition to Status enums."""
        statuses = ["DONE", "TODO"]
        assert rollup_story_status(statuses) == Status.IN_PROGRESS


class TestRollupPlanStatus:
    """Test rollup_plan_status function."""

    def test_empty_list_returns_todo(self):
        """Test that empty story list returns TODO."""
        assert rollup_plan_status([]) == Status.TODO

    def test_all_done_returns_done(self):
        """Test that all DONE stories returns DONE."""
        statuses = [Status.DONE, Status.DONE, Status.DONE]
        assert rollup_plan_status(statuses) == Status.DONE

    def test_any_in_progress_returns_in_progress(self):
        """Test that any IN_PROGRESS story returns IN_PROGRESS."""
        statuses = [Status.DONE, Status.IN_PROGRESS, Status.TODO]
        assert rollup_plan_status(statuses) == Status.IN_PROGRESS

    def test_mixed_done_and_todo_returns_in_progress(self):
        """Test that mix of DONE and TODO returns IN_PROGRESS (work started)."""
        statuses = [Status.DONE, Status.TODO, Status.TODO]
        assert rollup_plan_status(statuses) == Status.IN_PROGRESS

    def test_all_todo_returns_todo(self):
        """Test that all TODO stories returns TODO."""
        statuses = [Status.TODO, Status.TODO]
        assert rollup_plan_status(statuses) == Status.TODO

    def test_single_done_returns_done(self):
        """Test that single DONE story returns DONE."""
        assert rollup_plan_status([Status.DONE]) == Status.DONE

    def test_single_todo_returns_todo(self):
        """Test that single TODO story returns TODO."""
        assert rollup_plan_status([Status.TODO]) == Status.TODO

    def test_accepts_string_values(self):
        """Test that function accepts string values in addition to Status enums."""
        statuses = ["DONE", "TODO"]
        assert rollup_plan_status(statuses) == Status.IN_PROGRESS
