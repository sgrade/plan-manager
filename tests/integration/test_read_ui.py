# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import importlib
import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from plan_manager.domain.models import Status
from plan_manager.server.app import starlette_app
from plan_manager.services.shared import service_uow
from plan_manager.storage import repositories


def _seed_plan_with_story_and_tasks() -> tuple[str, str]:
    with service_uow(write=True, operation="seed_ui_test_data") as conn:
        plan_id = repositories.create_plan(
            conn,
            base_id="ui-plan",
            title="UI Plan",
            description="Plan description",
            status=Status.TODO,
            priority=1,
        )
        story_id = repositories.create_story(
            conn,
            plan_id=plan_id,
            base_id="ui-story",
            title="UI Story",
            description="Story description",
            status=Status.TODO,
            priority=1,
            acceptance_criteria=["One", "Two"],
            depends_on=[],
            body="# Story Notes\n\n<script>alert('x')</script>\n\n<img src=x onerror=alert(1)>",
        )
        repositories.create_task(
            conn,
            plan_id=plan_id,
            story_id=story_id,
            base_local_id="safe-task",
            title="Safe Task",
            description="Task description",
            status=Status.TODO,
            priority=1,
            depends_on=[],
            steps=[],
            changes=[],
            review_feedback=[],
            body=(
                "Task body with [bad link](javascript:alert(1)) and raw HTML <b>bold</b>\n\n"
                "<script>alert('task')</script>\n"
                "<img src=x onerror=alert('boom')>"
            ),
        )
        repositories.set_current_story(
            conn,
            plan_id=plan_id,
            current_story_id=story_id,
        )
        repositories.set_current_task(
            conn,
            plan_id=plan_id,
            current_task_story_id=story_id,
            current_task_local_id="safe-task",
        )
        for idx in range(60):
            repositories.append_event(
                conn,
                plan_id=plan_id,
                event_type=f"event_{idx}",
                scope={"event": idx},
                data={"index": idx},
            )
    return plan_id, story_id


@pytest.mark.integration
def test_ui_routes_render_content_and_bound_events():
    plan_id, story_id = _seed_plan_with_story_and_tasks()
    with TestClient(starlette_app(), base_url="http://127.0.0.1:3000") as client:
        plans_page = client.get("/ui")
        assert plans_page.status_code == 200
        assert "UI Plan" in plans_page.text
        assert plans_page.headers["content-security-policy"] == (
            "default-src 'none'; style-src 'self'"
        )
        assert plans_page.headers["x-content-type-options"] == "nosniff"

        plan_page = client.get(f"/ui/{plan_id}")
        assert plan_page.status_code == 200
        assert "UI Story" in plan_page.text
        assert "Current story" in plan_page.text
        assert "Current task" in plan_page.text
        assert "event_59" in plan_page.text
        assert "event_0" not in plan_page.text
        assert plan_page.text.count("event_") == 50

        story_page = client.get(f"/ui/{plan_id}/{story_id}")
        assert story_page.status_code == 200
        assert "Safe Task" in story_page.text
        # Task rows carry plain status strings, not Status members, so a `.value`
        # lookup in the template renders empty; pin the whole row to catch that.
        assert f"{story_id}:safe-task | TODO | Priority 1" in story_page.text
        assert "<script>alert('task')</script>" not in story_page.text
        assert "<img src=x onerror=" not in story_page.text
        assert 'href="javascript:' not in story_page.text
        assert "&lt;script&gt;alert(" in story_page.text
        assert story_page.headers["content-security-policy"] == (
            "default-src 'none'; style-src 'self'"
        )
        assert story_page.headers["x-content-type-options"] == "nosniff"


@pytest.mark.integration
def test_ui_unknown_ids_render_escaped_not_found():
    with TestClient(starlette_app(), base_url="http://127.0.0.1:3000") as client:
        response = client.get("/ui/%3Cscript%3E")
    assert response.status_code == 404
    assert "&lt;script&gt;" in response.text
    assert "<script>" not in response.text


@pytest.mark.integration
def test_ui_flag_disabled_returns_404(monkeypatch):
    monkeypatch.setenv("PLAN_MANAGER_ENABLE_UI", "false")
    import plan_manager.config as config_module
    import plan_manager.server.app as app_module

    importlib.reload(config_module)
    reloaded = importlib.reload(app_module)

    try:
        with TestClient(
            reloaded.starlette_app(), base_url="http://127.0.0.1:3000"
        ) as client:
            response = client.get("/ui")
            static_response = client.get("/ui/static/ui.css")
        assert response.status_code == 404
        assert static_response.status_code == 404
    finally:
        monkeypatch.delenv("PLAN_MANAGER_ENABLE_UI", raising=False)
        importlib.reload(config_module)
        importlib.reload(app_module)


@pytest.mark.integration
def test_templates_do_not_use_safe_filter():
    template_root = Path("src/plan_manager/server/templates")
    for path in template_root.rglob("*.html"):
        content = path.read_text(encoding="utf-8")
        assert "|safe" not in content, f"Unsafe template filter used in {path}"


@pytest.mark.integration
def test_valid_correlation_id_is_reflected():
    with TestClient(starlette_app(), base_url="http://127.0.0.1:3000") as client:
        response = client.get("/ui", headers={"x-correlation-id": "valid-id_123.abc"})
    assert response.status_code == 200
    assert response.headers.get("x-correlation-id") == "valid-id_123.abc"


@pytest.mark.integration
def test_invalid_correlation_id_replaced_on_ui_route():
    with TestClient(starlette_app(), base_url="http://127.0.0.1:3000") as client:
        response = client.get("/ui", headers={"x-correlation-id": "bad<script>"})
    assert response.status_code == 200
    corr_id = response.headers.get("x-correlation-id")
    assert corr_id is not None
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        corr_id,
    )


def test_markdown_link_schemes_are_allowlisted():
    """U8 review L-1: entity-obfuscated schemes must not become live hrefs."""
    from plan_manager.server.app import _MARKDOWN

    hostile = _MARKDOWN.render(
        "[click](jav&#x09;ascript:alert(1)) "
        "[also](javascript:alert(2)) "
        "[data](data:text/html;base64,PHNjcmlwdD4=) "
        "[fine](https://example.com) [rel](../sibling) [mail](mailto:a@b.c)"
    )
    # Rejected links render as literal text, never as live hrefs.
    lowered = hostile.lower()
    assert 'href="jav' not in lowered
    assert 'href="javascript:' not in lowered
    assert 'href="data:' not in lowered
    assert 'href="https://example.com"' in hostile
    assert 'href="../sibling"' in hostile
    assert 'href="mailto:a@b.c"' in hostile
