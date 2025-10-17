"""Integration tests for story tools, specifically testing parameter handling.

These tests verify that the get_story tool correctly accepts and handles the
story_id parameter, which is defined as Optional[str] = None. This is critical
for MCP schema generation and client interactions.

The tests confirm:
1. Explicit story_id parameter is correctly accepted and used
2. When story_id is None/omitted, current story context is used
3. Function signature matches expected Optional[str] type annotation
"""

import uuid

import pytest


@pytest.mark.integration
def test_get_story_with_explicit_id():
    """Test that get_story tool correctly accepts and uses an explicit story_id parameter."""
    # Test isolation handled by autouse fixture in conftest.py

    from plan_manager.services import plan_service, story_service
    from plan_manager.services.plan_repository import set_current_plan_id
    from plan_manager.services.state_repository import set_current_story_id
    from plan_manager.tools.story_tools import get_story

    suffix = str(uuid.uuid4())[:8]

    # Create a plan first (required for stories)
    plan = plan_service.create_plan(
        title=f"Test Plan {suffix}", description="Test plan", priority=None
    )
    set_current_plan_id(plan["id"])

    # Create two stories
    story1 = story_service.create_story(
        title=f"Story 1 {suffix}",
        description="First story",
        acceptance_criteria=["AC1"],
        priority=1,
        depends_on=[],
    )
    story1_id = story1["id"]

    story2 = story_service.create_story(
        title=f"Story 2 {suffix}",
        description="Second story",
        acceptance_criteria=["AC2"],
        priority=2,
        depends_on=[],
    )
    story2_id = story2["id"]

    # Set story1 as current
    set_current_story_id(story1_id)

    # Test 1: Get story with explicit ID (story2) - should return story2, not current story
    result = get_story(story_id=story2_id)

    assert result.id == story2_id, f"Expected story_id {story2_id}, got {result.id}"
    assert result.title == f"Story 2 {suffix}", (
        f"Expected 'Story 2 {suffix}', got {result.title}"
    )
    assert result.description == "Second story", (
        f"Expected 'Second story', got {result.description}"
    )
    assert result.priority == 2, f"Expected priority 2, got {result.priority}"

    # Test 2: Get story without ID - should return current story (story1)
    result_current = get_story()

    assert result_current.id == story1_id, (
        f"Expected current story_id {story1_id}, got {result_current.id}"
    )
    assert result_current.title == f"Story 1 {suffix}", (
        f"Expected 'Story 1 {suffix}', got {result_current.title}"
    )

    # Test 3: Get story1 with explicit ID - should return story1
    result_story1 = get_story(story_id=story1_id)

    assert result_story1.id == story1_id, (
        f"Expected story_id {story1_id}, got {result_story1.id}"
    )
    assert result_story1.title == f"Story 1 {suffix}", (
        f"Expected 'Story 1 {suffix}', got {result_story1.title}"
    )
    assert result_story1.description == "First story", (
        f"Expected 'First story', got {result_story1.description}"
    )


@pytest.mark.integration
def test_get_story_with_null_id_requires_current():
    """Test that get_story raises ValueError when no ID is provided and no current story is set."""
    # Test isolation handled by autouse fixture in conftest.py

    from plan_manager.services.state_repository import set_current_story_id
    from plan_manager.tools.story_tools import get_story

    # Clear current story
    set_current_story_id(None)

    # Attempt to get story without ID and without current story should raise ValueError
    with pytest.raises(ValueError, match="No current story set"):
        get_story()


@pytest.mark.integration
def test_get_story_parameter_types():
    """Test that get_story accepts the correct parameter types per MCP schema."""
    # Test isolation handled by autouse fixture in conftest.py

    import inspect

    from plan_manager.services import plan_service, story_service
    from plan_manager.tools.story_tools import get_story

    # Verify function signature
    sig = inspect.signature(get_story)
    story_id_param = sig.parameters["story_id"]

    # Check that story_id is Optional[str] with default None
    assert story_id_param.default is None, "story_id should default to None"
    assert story_id_param.annotation.__origin__.__name__ == "Union", (
        "story_id should be Optional (Union with None)"
    )

    # Create a plan first (required for stories)
    suffix = str(uuid.uuid4())[:8]
    plan = plan_service.create_plan(
        title=f"Test Plan {suffix}", description="Test plan", priority=None
    )
    from plan_manager.services.plan_repository import set_current_plan_id

    set_current_plan_id(plan["id"])

    # Create a test story
    story = story_service.create_story(
        title=f"Test Story {suffix}",
        description="Test",
        acceptance_criteria=None,
        priority=None,
        depends_on=[],
    )
    story_id = story["id"]

    # Test that string ID works
    result = get_story(story_id=story_id)
    assert result.id == story_id

    # Test that None explicitly passed works (should use current story if set)
    from plan_manager.services.state_repository import set_current_story_id

    set_current_story_id(story_id)
    result_none = get_story(story_id=None)
    assert result_none.id == story_id
