from datetime import datetime, timezone
from typing import Optional, Dict, Any

from plan_manager.services import plan_repository as plan_repo
from plan_manager.services.state_repository import get_current_story_id, get_current_task_id
from plan_manager.services.activity_repository import append_event
from plan_manager.domain.models import Story, Task, Approval


def _resolve_targets(plan, item_type: str, item_id: Optional[str]) -> Dict[str, Any]:
    if item_type not in ('story', 'task'):
        raise ValueError("item_type must be 'story' or 'task'")
    if item_type == 'story':
        sid = item_id or get_current_story_id(plan.id)
        if not sid:
            raise ValueError(
                "No current story set. Provide item_id or set current story.")
        story = next((s for s in plan.stories if s.id == sid), None)
        if not story:
            raise KeyError(f"story with ID '{sid}' not found.")
        return {'story': story}
    # task: allow defaults to current story/task
    # Determine story and task
    if item_id and ':' in item_id:
        # Full qualified task ID provided
        sid, tid = item_id.split(':', 1)
        fq_task_id = item_id  # Use the provided FQ ID directly
    else:
        # Local task ID or use current context
        sid = get_current_story_id(plan.id)
        if not sid:
            raise ValueError(
                "No current story set. Provide item_id as FQ or set current story.")
        tid = (item_id or get_current_task_id(plan.id))
        if not tid:
            raise ValueError(
                "No current task set. Provide item_id or set current task.")
        # If tid is already FQ, use it; otherwise construct FQ ID
        fq_task_id = tid if ':' in tid else f"{sid}:{tid}"

    story = next((s for s in plan.stories if s.id == sid), None)
    if not story:
        raise KeyError(f"story with ID '{sid}' not found.")
    task = next((t for t in (story.tasks or []) if t.id == fq_task_id), None)
    if not task:
        raise KeyError(
            f"task with ID '{fq_task_id}' not found under story '{sid}'.")
    return {'story': story, 'task': task}


def request_approval(item_type: str, item_id: Optional[str], execution_intent: str) -> Dict[str, Any]:
    plan = plan_repo.load_current()
    targets = _resolve_targets(plan, item_type, item_id)
    ts = datetime.now(timezone.utc)
    if 'task' in targets:
        task: Task = targets['task']
        task.execution_intent = execution_intent
        appr = task.approval or Approval()
        appr.requested_at = ts
        task.approval = appr
        plan_repo.save(plan, plan_id=plan.id)
        append_event(plan.id, 'approval_requested', {
                     'task_id': task.id}, {'intent': execution_intent})
        return task.model_dump(mode='json', exclude_none=True)
    else:
        story: Story = targets['story']
        story.execution_intent = execution_intent
        appr = story.approval or Approval()
        appr.requested_at = ts
        story.approval = appr
        plan_repo.save(plan, plan_id=plan.id)
        append_event(plan.id, 'approval_requested', {
                     'story_id': story.id}, {'intent': execution_intent})
        return story.model_dump(mode='json', exclude_none=True)


def approve_item(item_type: str, item_id: Optional[str], approved: bool, notes: Optional[str]) -> Dict[str, Any]:
    plan = plan_repo.load_current()
    targets = _resolve_targets(plan, item_type, item_id)
    ts = datetime.now(timezone.utc)
    if 'task' in targets:
        task: Task = targets['task']
        appr = task.approval or Approval()
        if approved:
            appr.approved_at = ts
            # approved_by can be populated by caller future enhancement
        appr.notes = notes
        task.approval = appr
        plan_repo.save(plan, plan_id=plan.id)
        append_event(plan.id, 'approval_' + ('granted' if approved else 'rejected'),
                     {'task_id': task.id}, {'notes': notes})
        return task.model_dump(mode='json', exclude_none=True)
    else:
        story: Story = targets['story']
        appr = story.approval or Approval()
        if approved:
            appr.approved_at = ts
        appr.notes = notes
        story.approval = appr
        plan_repo.save(plan, plan_id=plan.id)
        append_event(plan.id, 'approval_' + ('granted' if approved else 'rejected'),
                     {'story_id': story.id}, {'notes': notes})
        return story.model_dump(mode='json', exclude_none=True)
