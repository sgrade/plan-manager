# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Pytest configuration and shared fixtures."""

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

# Set TODO_DIR to temp BEFORE any modules are imported
# This happens at pytest startup, before test collection
_TEST_TODO_DIR = None
_TEST_DB_ROOT = None


def pytest_configure(config):
    """Configure pytest - set TODO_DIR before any tests are collected."""
    global _TEST_TODO_DIR, _TEST_DB_ROOT
    # Create a persistent temp directory for the entire test session
    _TEST_TODO_DIR = tempfile.mkdtemp(prefix="pytest_plan_manager_")
    _TEST_DB_ROOT = tempfile.mkdtemp(prefix="pytest_plan_manager_db_")
    os.environ["TODO_DIR"] = _TEST_TODO_DIR
    os.environ["PLAN_MANAGER_DB_DIR"] = str(Path(_TEST_DB_ROOT) / "session")


def pytest_unconfigure(config):
    """Cleanup after all tests complete."""
    global _TEST_TODO_DIR, _TEST_DB_ROOT
    if _TEST_TODO_DIR and os.path.exists(_TEST_TODO_DIR):
        shutil.rmtree(_TEST_TODO_DIR, ignore_errors=True)
    if _TEST_DB_ROOT and os.path.exists(_TEST_DB_ROOT):
        shutil.rmtree(_TEST_DB_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolate_tests():
    """Automatically isolate all tests to use the test temp directory.

    This fixture clears global state between tests.
    TODO_DIR is already set globally by pytest_configure.
    """
    test_db_dir = Path(_TEST_DB_ROOT) / uuid.uuid4().hex
    test_db_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PLAN_MANAGER_DB_DIR"] = str(test_db_dir)

    # Yield control back to the test
    yield
    shutil.rmtree(test_db_dir, ignore_errors=True)


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
    return workspace
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
