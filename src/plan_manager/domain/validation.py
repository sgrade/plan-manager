import logging
from typing import Any

logger = logging.getLogger(__name__)


def validate_plan_dependencies(stories: list[Any]) -> None:
    """Validate story and task dependencies across the plan.

    - Ensures story.depends_on references existing stories and not self
    - Ensures task.depends_on references existing stories or tasks (local or FQ), and not self
    """
    story_ids = {story.id for story in stories}
    task_ids: set[str] = set()
    for s in stories:
        for t in s.tasks or []:
            tid = getattr(t, "id", None)
            if tid:
                task_ids.add(tid)

    for story in stories:
        if story.depends_on:
            for dep_id in story.depends_on:
                if dep_id not in story_ids:
                    raise ValueError(
                        f"story '{story.id}' has unmet dependency: '{dep_id}'"
                    )
            if story.id in story.depends_on:
                raise ValueError(f"story '{story.id}' cannot depend on itself.")
        for task in story.tasks or []:
            deps = getattr(task, "depends_on", None)
            if not deps:
                continue
            for dep in deps:
                if not isinstance(dep, str) or not dep.strip():
                    raise ValueError(
                        f"task '{task.id}' in story '{story.id}' has invalid dependency entry: {dep}"
                    )
                dep_str = dep.strip()
                if ":" in dep_str:
                    if dep_str == getattr(task, "id", None):
                        raise ValueError(f"task '{task.id}' cannot depend on itself.")
                    if dep_str not in task_ids:
                        raise ValueError(
                            f"task '{task.id}' depends on unknown task '{dep_str}'."
                        )
                else:
                    if dep_str in story_ids:
                        continue
                    fq = f"{story.id}:{dep_str}"
                    if fq == getattr(task, "id", None):
                        raise ValueError(f"task '{task.id}' cannot depend on itself.")
                    if fq not in task_ids:
                        raise ValueError(
                            f"task '{task.id}' depends on unknown task '{dep_str}' in story '{story.id}'."
                        )
