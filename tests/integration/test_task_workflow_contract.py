# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import inspect
import json

import pytest

from plan_manager.schemas.outputs import ActionType, WhoRuns
from plan_manager.tools import report_tools, task_tools
from plan_manager.tools.plan_tools import create_plan
from plan_manager.tools.story_tools import create_story


def _make_task() -> tuple[str, str, str]:
    plan = create_plan("Contract Plan")
    story = create_story(plan.id, "Contract Story")
    task = task_tools.create_task(plan.id, story.id, "Contract Task")
    return plan.id, story.id, task.id


def _iter_emitted_tool_calls(next_actions):
    for action in next_actions:
        if action.kind == "tool":
            yield action.name, action.arguments or {}, action.pending_arguments or []
        args = action.arguments if isinstance(action.arguments, dict) else None
        if not args:
            continue
        then_steps = args.get("then")
        if not isinstance(then_steps, list):
            continue
        for step in then_steps:
            if not isinstance(step, dict):
                continue
            tool_name = step.get("tool")
            tool_args = step.get("arguments")
            pending_args = step.get("pending_arguments")
            if isinstance(tool_name, str) and isinstance(tool_args, dict):
                if not isinstance(pending_args, list):
                    pending_args = []
                yield tool_name, tool_args, pending_args


def _assert_action_arguments_match_tool_signature(
    tool_name: str, arguments: dict, pending_arguments: list[str]
) -> None:
    tool_by_name = {
        "start_task": task_tools.start_task,
        "submit_pr": task_tools.submit_pr,
        "approve_pr": task_tools.approve_pr,
        "request_pr_changes": task_tools.request_pr_changes,
        "merge_pr": task_tools.merge_pr,
        "list_tasks": task_tools.list_tasks,
        "report": report_tools.report,
    }
    tool_fn = tool_by_name.get(tool_name)
    assert tool_fn is not None, f"Unsupported tool in next_actions: {tool_name}"
    sig = inspect.signature(tool_fn)
    required_params = [
        param.name
        for param in sig.parameters.values()
        if param.default is inspect.Signature.empty
        and param.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    ]

    missing = [name for name in required_params if name not in arguments]
    assert set(missing) == set(pending_arguments), (
        f"{tool_name} missing arguments {missing} must exactly match "
        f"pending_arguments {pending_arguments}"
    )

    for pending_name in pending_arguments:
        assert pending_name in required_params, (
            f"{tool_name}.pending_arguments contains non-required parameter: "
            f"{pending_name}"
        )

    for name in required_params:
        if name in missing:
            continue
        value = arguments[name]
        assert value is not None, f"{tool_name}.{name} cannot be null"
        if isinstance(value, str):
            assert value.strip(), f"{tool_name}.{name} cannot be empty"
        if isinstance(value, list):
            assert value, f"{tool_name}.{name} cannot be empty list"


@pytest.mark.integration
def test_gate_1_metadata_requires_user_approval_before_start():
    plan_id, _story_id, task_id = _make_task()
    result = task_tools.create_task_steps(
        plan_id=plan_id,
        task_id=task_id,
        steps=[{"title": "Implement contract updates"}],
    )

    assert result.action == ActionType.CREATE_STEPS
    recommended = [action for action in result.next_actions if action.recommended]
    assert len(recommended) == 1
    assert recommended[0].name == "user_approves_steps"
    start_action = next(
        action for action in result.next_actions if action.name == "start_task"
    )
    assert start_action.who == WhoRuns.AGENT_AFTER_USER_APPROVAL
    assert start_action.recommended is False

    for tool_name, args, pending_args in _iter_emitted_tool_calls(result.next_actions):
        _assert_action_arguments_match_tool_signature(tool_name, args, pending_args)


@pytest.mark.integration
def test_gate_2_metadata_recommends_prompt_before_mutations():
    plan_id, _story_id, task_id = _make_task()
    task_tools.create_task_steps(
        plan_id=plan_id,
        task_id=task_id,
        steps=[{"title": "Implement contract updates"}],
    )
    started = task_tools.start_task(plan_id=plan_id, task_id=task_id)
    assert started.action == ActionType.START_TASK

    # Regression guard (U6c ergonomics re-review): the EXECUTING state must
    # emit a structured submit_pr continuation so a blind agent never stalls
    # between working and submitting.
    submit_continuations = [
        action for action in started.next_actions if action.name == "submit_pr"
    ]
    assert len(submit_continuations) == 1
    assert submit_continuations[0].pending_arguments == ["changes"]
    assert submit_continuations[0].arguments["plan_id"] == plan_id

    submitted = task_tools.submit_pr(
        plan_id=plan_id,
        task_id=task_id,
        changes=["Aligned gate metadata with policy"],
    )
    assert submitted.action == ActionType.SUBMIT_PR

    recommended = [action for action in submitted.next_actions if action.recommended]
    assert len(recommended) == 1
    assert recommended[0].name == "display_review_and_prompt"

    approve_action = next(
        action for action in submitted.next_actions if action.name == "approve_pr"
    )
    merge_action = next(
        action for action in submitted.next_actions if action.name == "merge_pr"
    )
    assert approve_action.who == WhoRuns.AGENT_AFTER_USER_APPROVAL
    assert merge_action.who == WhoRuns.AGENT_AFTER_USER_APPROVAL
    assert approve_action.recommended is False
    assert merge_action.recommended is False

    for tool_name, args, pending_args in _iter_emitted_tool_calls(
        submitted.next_actions
    ):
        _assert_action_arguments_match_tool_signature(tool_name, args, pending_args)

    nested_merge = next(
        step
        for action in submitted.next_actions
        if action.name == "user_approves_review"
        for step in (action.arguments or {}).get("then", [])
        if step.get("tool") == "merge_pr"
    )
    assert nested_merge["pending_arguments"] == ["changelog_category", "commit_type"]

    top_level_merge = next(
        action for action in submitted.next_actions if action.name == "merge_pr"
    )
    assert top_level_merge.pending_arguments == ["changelog_category", "commit_type"]

    nested_feedback = next(
        step
        for action in submitted.next_actions
        if action.name == "user_provides_feedback"
        for step in (action.arguments or {}).get("then", [])
        if step.get("tool") == "request_pr_changes"
    )
    assert nested_feedback["pending_arguments"] == ["feedback"]


@pytest.mark.integration
def test_start_task_failure_raises_with_action_none_payload():
    plan_id, _story_id, task_id = _make_task()

    with pytest.raises(ValueError, match="structured_recovery=") as exc:
        task_tools.start_task(plan_id=plan_id, task_id=task_id)

    payload_json = str(exc.value).split("structured_recovery=", maxsplit=1)[1]
    payload = json.loads(payload_json)
    assert payload["action"] == ActionType.NONE.value
    assert payload["success"] is False


@pytest.mark.integration
def test_request_pr_changes_failure_raises_with_action_none_payload():
    plan_id, _story_id, task_id = _make_task()

    with pytest.raises(ValueError, match="structured_recovery=") as exc:
        task_tools.request_pr_changes(
            plan_id=plan_id,
            task_id=task_id,
            feedback="Need more tests",
        )

    payload_json = str(exc.value).split("structured_recovery=", maxsplit=1)[1]
    payload = json.loads(payload_json)
    assert payload["action"] == ActionType.NONE.value
    assert payload["success"] is False


@pytest.mark.integration
def test_merge_pr_response_reports_merge_action_type():
    plan_id, _story_id, task_id = _make_task()
    task_tools.create_task_steps(
        plan_id=plan_id,
        task_id=task_id,
        steps=[{"title": "Implement contract updates"}],
    )
    task_tools.start_task(plan_id=plan_id, task_id=task_id)
    task_tools.submit_pr(
        plan_id=plan_id,
        task_id=task_id,
        changes=["Prepared merge artifacts"],
    )
    merged = task_tools.merge_pr(
        plan_id=plan_id,
        task_id=task_id,
        changelog_category="Changed",
        commit_type="chore",
    )
    assert merged.action == ActionType.MERGE_PR
