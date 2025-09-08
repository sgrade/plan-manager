from plan_manager.schemas.outputs import (
    WorkflowStatusOut,
)
from plan_manager.services.plan_repository import get_current_plan_id
from plan_manager.services.state_repository import (
    get_current_story_id,
    get_current_task_id,
)
from plan_manager.services import plan_repository as plan_repo
from plan_manager.domain.models import Status


def register_context_tools(mcp_instance) -> None:
    """Register context tools with the MCP instance."""
    mcp_instance.tool()(workflow_status)


def workflow_status() -> WorkflowStatusOut:
    """Get current workflow status and next actions."""
    pid = get_current_plan_id()
    sid = get_current_story_id(pid)
    tid = get_current_task_id(pid)

    # Get current task details
    current_task = None
    workflow_state = {"approval_status": "none", "execution_intent": None}
    compliance = {"ready_to_start": False, "blockers": []}
    next_actions = []

    if sid and tid:
        try:
            plan = plan_repo.load_current()
            story = next((s for s in plan.stories if s.id == sid), None)
            if story:
                task = next(
                    (t for t in (story.tasks or []) if t.id == tid), None)
                if task:
                    current_task = {
                        "id": task.id,
                        "title": task.title,
                        "status": task.status.value,
                        "description": task.description
                    }

                    # Check approval status
                    approval = getattr(task, 'approval', None)
                    if approval:
                        if approval.approved_at:
                            workflow_state["approval_status"] = "approved"
                        elif approval.requested_at:
                            workflow_state["approval_status"] = "pending"

                    # Check execution intent
                    workflow_state["execution_intent"] = getattr(
                        task, 'execution_intent', None)

                    # Determine next actions based on current state
                    if task.status == Status.TODO:
                        if not workflow_state["execution_intent"]:
                            next_actions.append(
                                "Set execution_intent via request_approval")
                            compliance["blockers"].append(
                                "Missing execution_intent")
                        elif workflow_state["approval_status"] == "none":
                            next_actions.append(
                                "Request approval for this task")
                            compliance["blockers"].append(
                                "Approval not requested")
                        elif workflow_state["approval_status"] == "pending":
                            next_actions.append(
                                "Wait for approval or approve the task")
                            compliance["blockers"].append("Pending approval")
                        elif workflow_state["approval_status"] == "approved":
                            next_actions.append(
                                "Start work - update status to IN_PROGRESS")
                            compliance["ready_to_start"] = True
                    elif task.status == Status.IN_PROGRESS:
                        next_actions.append(
                            "Complete work and update status to DONE with execution_summary")
                        compliance["ready_to_start"] = True
                    elif task.status == Status.DONE:
                        next_actions.append(
                            "Advance to next task or complete story")
                        if not getattr(task, 'execution_summary', None):
                            compliance["blockers"].append(
                                "Missing execution_summary")
        except Exception as e:
            compliance["blockers"].append(f"Error loading task: {str(e)}")
    else:
        next_actions.append("Select a story and task to begin work")
        compliance["blockers"].append("No current task selected")

    actions = []
    # Populate structured action hints to reduce LLM mapping
    if not sid:
        # No story selected; suggest selecting the first story
        actions.append({
            "id": "select_first_story",
            "label": "Select first story",
            "tool": "select_first_story",
            "payload_hints": {}
        })
    elif sid and not tid:
        # Story selected but no task; suggest first unblocked task
        # Find any other story with TODO tasks and dependencies satisfied
        try:
            plan = plan_repo.load_current()
            # Find any other story with TODO tasks and dependencies satisfied
            from plan_manager.domain.models import Status as _S
            for s in plan.stories:
                if s.id == sid:
                    continue
                # Check for any TODO tasks
                has_todo = any(t.status in (_S.TODO,) for t in (s.tasks or []))
                if not has_todo:
                    continue
                actions.append({
                    "id": "switch_story",
                    "label": f"Switch to story: {s.title}",
                    "tool": "set_current_story",
                    "payload_hints": {"story_id": s.id}
                })
                break
        except Exception:
            pass
    elif sid and tid and current_task:
        if task.status == Status.TODO:
            if not workflow_state["execution_intent"]:
                actions.append({
                    "id": "draft_intent",
                    "label": "Draft execution intent",
                    "prompt": "execution_intent_template",
                    "payload_hints": {"task_title": task.title, "task_description": task.description}
                })
                actions.append({
                    "id": "request_approval",
                    "label": "Request approval",
                    "tool": "request_approval_tool",
                    "payload_hints": {"item_type": "task", "item_id": task.id, "execution_intent": "<from_prompt>"}
                })
            elif workflow_state["approval_status"] == "none":
                actions.append({
                    "id": "request_approval",
                    "label": "Request approval",
                    "tool": "request_approval_tool",
                    "payload_hints": {"item_type": "task", "item_id": task.id, "execution_intent": workflow_state["execution_intent"]}
                })
            elif workflow_state["approval_status"] == "approved":
                actions.append({
                    "id": "start_work",
                    "label": "Start work",
                    "tool": "update_task",
                    "payload_hints": {"story_id": sid, "task_id": task.id, "status": "IN_PROGRESS"}
                })
            # If blocked, surface blockers and suggest first unblocked prerequisite
            try:
                from plan_manager.services.task_service import explain_task_blockers as _explain
                local = task.id.split(':', 1)[1] if ':' in task.id else task.id
                info = _explain(sid, local)
                if info and not info.get('unblocked', True):
                    # Navigate to each dependency
                    for b in info.get('blockers', []):
                        if b.get('type') == 'task':
                            actions.append({
                                "id": f"goto_dep_{b.get('id')}",
                                "label": f"Open dependency task: {b.get('id')}",
                                "tool": "set_current_task",
                                "payload_hints": {"task_id": b.get('id')}
                            })
                        elif b.get('type') == 'story':
                            actions.append({
                                "id": f"goto_dep_story_{b.get('id')}",
                                "label": f"Open dependency story: {b.get('id')}",
                                "tool": "set_current_story",
                                "payload_hints": {"story_id": b.get('id')}
                            })
                    # Offer first unblocked prerequisite
                    first_unblocked = None
                    # Check task-type blockers first
                    for b in info.get('blockers', []):
                        if b.get('type') == 'task':
                            dep_id = b.get('id')
                            try:
                                dep_story_id, dep_local = dep_id.split(':', 1)
                            except ValueError:
                                dep_story_id, dep_local = sid, dep_id
                            dep_info = _explain(dep_story_id, dep_local)
                            if dep_info and dep_info.get('unblocked', False):
                                first_unblocked = dep_id
                                break
                    # If none, check story-type blockers for unblocked tasks inside
                    if not first_unblocked:
                        try:
                            plan2 = plan_repo.load_current()
                            for b in info.get('blockers', []):
                                if b.get('type') != 'story':
                                    continue
                                dep_story = next(
                                    (s for s in plan2.stories if s.id == b.get('id')), None)
                                if not dep_story:
                                    continue
                                for t2 in (dep_story.tasks or []):
                                    if t2.status != Status.TODO:
                                        continue
                                    loc2 = t2.id.split(':', 1)[
                                        1] if ':' in t2.id else t2.id
                                    dep_t_info = _explain(dep_story.id, loc2)
                                    if dep_t_info and dep_t_info.get('unblocked', False):
                                        first_unblocked = t2.id
                                        break
                                if first_unblocked:
                                    break
                        except Exception:
                            pass
                    if first_unblocked:
                        actions.append({
                            "id": "select_first_unblocked_prerequisite",
                            "label": f"Select unblocked prerequisite: {first_unblocked}",
                            "tool": "set_current_task",
                            "payload_hints": {"task_id": first_unblocked}
                        })
            except Exception:
                pass
        elif task.status == Status.IN_PROGRESS:
            actions.append({
                "id": "complete_with_summary",
                "label": "Complete task with summary",
                "prompt": "execution_summary_template",
                "payload_hints": {"task_title": task.title, "files_changed": "<fill_in>"}
            })
            actions.append({
                "id": "mark_done",
                "label": "Mark DONE",
                "tool": "update_task",
                "payload_hints": {"story_id": sid, "task_id": task.id, "status": "DONE", "execution_summary": "<from_prompt>"}
            })
            # Surface blockers if any
            try:
                from plan_manager.services.task_service import explain_task_blockers as _explain
                blockers_info = _explain(sid, task.id.split(
                    ':', 1)[1] if ':' in task.id else task.id)
                if blockers_info and not blockers_info.get('unblocked', True):
                    for b in blockers_info.get('blockers', []):
                        if b.get('type') == 'task':
                            actions.append({
                                "id": f"goto_dep_{b.get('id')}",
                                "label": f"Open dependency task: {b.get('id')}",
                                "tool": "set_current_task",
                                "payload_hints": {"task_id": b.get('id')}
                            })
                        elif b.get('type') == 'story':
                            actions.append({
                                "id": f"goto_dep_story_{b.get('id')}",
                                "label": f"Open dependency story: {b.get('id')}",
                                "tool": "set_current_story",
                                "payload_hints": {"story_id": b.get('id')}
                            })
            except Exception:
                pass
        elif task.status == Status.DONE:
            actions.append({
                "id": "publish_changelog",
                "label": "Generate changelog markdown",
                "tool": "publish_changelog_tool",
                "payload_hints": {"version": None, "date": None}
            })
            # If the story has no remaining TODO/IN_PROGRESS tasks, suggest marking story DONE
            try:
                plan = plan_repo.load_current()
                story = next((s for s in plan.stories if s.id == sid), None)
                if story and not any(t.status in (Status.TODO, Status.IN_PROGRESS) for t in (story.tasks or [])):
                    actions.append({
                        "id": "mark_story_done",
                        "label": "Mark story DONE",
                        "tool": "update_story",
                        "payload_hints": {"story_id": sid, "status": "DONE"}
                    })
            except Exception:
                pass

    return WorkflowStatusOut(
        current_task=current_task,
        workflow_state=workflow_state,
        compliance=compliance,
        next_actions=next_actions,
        actions=actions or None,
    )
