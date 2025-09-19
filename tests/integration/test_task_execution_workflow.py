import uuid
import pytest


@pytest.mark.integration
def test_task_execution_gate1_paths(monkeypatch, tmp_path):
    # Isolate filesystem storage for the test run
    monkeypatch.setenv("TODO_DIR", str(tmp_path / "todo"))

    from plan_manager.services import plan_service
    from plan_manager.services import story_service
    from plan_manager.services import task_service
    from plan_manager.services import plan_repository as repo
    from plan_manager.services import state_repository as state

    suffix = str(uuid.uuid4())[:8]
    plan_title = f"test-exec-{suffix}"
    plan = plan_service.create_plan(
        plan_title, description=None, priority=None)
    plan_id = plan['id']
    repo.set_current_plan_id(plan_id)

    story = story_service.create_story(title=f"Story A {suffix}", description=None,
                                       acceptance_criteria=None, priority=None, depends_on=[])
    story_id = story['id']
    state.set_current_story_id(story_id)

    # Create tasks: T1 (independent), T2 (depends on T1), T3 (independent), T4 (depends on T1)
    T1 = task_service.create_task(
        story_id=story_id, title=f"Task 1 {suffix}", priority=None, depends_on=[], description=None)
    T1_id = T1['id']
    T1_local = T1_id.split(':', 1)[1]
    T2 = task_service.create_task(story_id=story_id, title=f"Task 2 {suffix}", priority=None, depends_on=[
                                  T1_local], description=None)
    T2_id = T2['id']
    T2_local = T2_id.split(':', 1)[1]
    T3 = task_service.create_task(
        story_id=story_id, title=f"Task 3 {suffix}", priority=None, depends_on=[], description=None)
    T3_id = T3['id']
    T3_local = T3_id.split(':', 1)[1]
    T4 = task_service.create_task(story_id=story_id, title=f"Task 4 {suffix}", priority=None, depends_on=[
                                  T1_local], description=None)
    T4_id = T4['id']

    # Path 1: Plan-first (steps then approve) for T1 -> IN_PROGRESS
    steps = [{"title": "Do the thing"}, {
        "title": "Validate outcome", "description": "Check outputs"}]
    _ = task_service.create_steps(
        story_id=story_id, task_id=T1_local, steps=steps)
    state.set_current_task_id(T1_id)
    res1 = task_service.approve_current_task()
    assert res1["success"] is True
    cur_T1 = task_service.get_task(story_id, T1_local)
    assert str(cur_T1["status"]) == "Status.IN_PROGRESS"

    # Path 2: Fast-track (no steps, approve) for T3 -> IN_PROGRESS (+seeded step)
    state.set_current_task_id(T3_id)
    res2 = task_service.approve_current_task()
    assert res2["success"] is True
    cur_T3 = task_service.get_task(story_id, T3_local)
    assert str(cur_T3["status"]) == "Status.IN_PROGRESS"
    assert len(cur_T3.get("steps", []) or []) >= 1

    # Path 3: Blocked with steps (T2 depends on T1 not DONE) -> approval fails
    _ = task_service.create_steps(story_id=story_id, task_id=T2_local, steps=[
                                  {"title": "Attempt work while blocked"}])
    state.set_current_task_id(T2_id)
    with pytest.raises(Exception) as e1:
        _ = task_service.approve_current_task()
    assert "BLOCKED" in str(e1.value)

    # Path 4: Blocked fast-track (T4 depends on T1 not DONE) -> approval fails
    state.set_current_task_id(T4_id)
    with pytest.raises(Exception) as e2:
        _ = task_service.approve_current_task()
    assert "BLOCKED" in str(e2.value)
