# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import re

from plan_manager.prompts.plan_prompts import build_create_plan_prompt_messages
from plan_manager.prompts.story_prompts import build_create_stories_prompt_messages
from plan_manager.prompts.task_prompts import (
    create_steps_messages,
    create_tasks_messages,
)

_PATH = re.compile(r"\.plan-manager-tmp/[0-9a-f]{32}/[a-z]+\.json")


def _last_text(messages) -> str:
    return messages[-1].content.text


def test_all_prompts_are_authority_neutral_and_invocation_unique():
    builders = [
        build_create_plan_prompt_messages,
        lambda: build_create_stories_prompt_messages("plan-1"),
        lambda: create_tasks_messages("plan-1", "story-1"),
        lambda: create_steps_messages("plan-1", "story-1:task-1"),
    ]

    paths: list[str] = []
    for build in builders:
        first = _last_text(build())
        second = _last_text(build())
        for text in (first, second):
            match = _PATH.search(text)
            assert match is not None
            paths.append(match.group())
            assert "authority already recorded" in text
            assert "missing or reserved decision" in text
            assert "does not grant or verify authority" in text
            assert "Then STOP" not in text
            assert "when I say 'approve'" not in text
            assert "todo/temp" not in text

    assert len(paths) == len(set(paths))


def test_repeated_step_prompts_for_same_task_do_not_collide():
    first = _PATH.search(_last_text(create_steps_messages("plan-1", "story-1:task-1")))
    second = _PATH.search(_last_text(create_steps_messages("plan-1", "story-1:task-1")))
    assert first is not None
    assert second is not None
    assert first.group() != second.group()
