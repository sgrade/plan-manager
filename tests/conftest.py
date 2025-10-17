"""Pytest configuration and shared fixtures."""

import pytest
import shutil
import importlib
import os
import tempfile
from pathlib import Path


# Set TODO_DIR to temp BEFORE any modules are imported
# This happens at pytest startup, before test collection
_TEST_TODO_DIR = None


def pytest_configure(config):
    """Configure pytest - set TODO_DIR before any tests are collected."""
    global _TEST_TODO_DIR
    # Create a persistent temp directory for the entire test session
    _TEST_TODO_DIR = tempfile.mkdtemp(prefix="pytest_plan_manager_")
    os.environ["TODO_DIR"] = _TEST_TODO_DIR
    print(f"\n[TEST] TODO_DIR set to: {_TEST_TODO_DIR}")


def pytest_unconfigure(config):
    """Cleanup after all tests complete."""
    global _TEST_TODO_DIR
    if _TEST_TODO_DIR and os.path.exists(_TEST_TODO_DIR):
        shutil.rmtree(_TEST_TODO_DIR, ignore_errors=True)
        print(f"\n[TEST] Cleaned up: {_TEST_TODO_DIR}")


@pytest.fixture(autouse=True)
def isolate_tests():
    """Automatically isolate all tests to use the test temp directory.

    This fixture clears global state between tests.
    TODO_DIR is already set globally by pytest_configure.
    """
    # Clear any global state that might persist between tests
    try:
        from plan_manager.services.state_repository import (
            set_current_plan_id,
            set_current_story_id,
            set_current_task_id,
        )
        from plan_manager.services.plan_repository import set_current_plan_id as set_plan_id

        # Clear all current IDs
        set_current_plan_id(None)
        set_plan_id(None)
        set_current_story_id(None)
        set_current_task_id(None)
    except ImportError:
        # If modules aren't imported yet, that's fine
        pass

    # Yield control back to the test
    yield

    # Cleanup happens at session end via pytest_unconfigure


@pytest.fixture
def clean_workspace(tmp_path):
    """Provide a clean workspace directory for tests that need explicit control.

    Use this fixture when you need to:
    1. Test filesystem operations explicitly
    2. Verify file contents after operations
    3. Have multiple test phases with different directories

    Example:
        def test_something(clean_workspace):
            workspace = clean_workspace
            # workspace will be cleaned up automatically
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    yield workspace
    # Cleanup happens automatically via tmp_path


@pytest.fixture
def sample_plan_data():
    """Provide sample plan data for testing."""
    return {
        "title": "Test Plan",
        "description": "A test plan for unit testing",
        "priority": 1,
    }


@pytest.fixture
def sample_story_data():
    """Provide sample story data for testing."""
    return {
        "title": "Test Story",
        "description": "A test story for unit testing",
        "acceptance_criteria": ["AC1", "AC2", "AC3"],
        "priority": 2,
        "depends_on": [],
    }


@pytest.fixture
def sample_task_data():
    """Provide sample task data for testing."""
    return {
        "title": "Test Task",
        "description": "A test task for unit testing",
        "priority": 3,
        "depends_on": [],
    }
