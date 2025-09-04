from datetime import datetime, timezone
from typing import Optional

from plan_manager.services.plan_repository import get_current_plan_id
from plan_manager.services.activity_repository import list_events
from plan_manager.services import plan_repository as plan_repo


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _classify(bucket_from: str, bucket_to: str) -> str:
    # Simple mapping: DONE becomes "Changed" by default
    if bucket_to == 'DONE':
        return 'Changed'
    if bucket_to == 'IN_PROGRESS':
        return 'Changed'
    return 'Added'


def render_changelog(version: Optional[str], date: Optional[str]) -> str:
    pid = get_current_plan_id()
    events = list_events(pid)
    # Collect changes by simple buckets
    buckets = {'Added': [], 'Changed': [], 'Fixed': []}
    for ev in events:
        et = ev.get('type')
        if et in ('story_status_changed', 'task_status_changed'):
            scope = ev.get('scope') or {}
            to_status = (ev.get('data') or {}).get('to') or ''
            # Only include DONE items; fetch execution_summary if available
            if str(to_status) == 'DONE':
                ident = scope.get('task_id') or scope.get(
                    'story_id') or 'unknown'
                summary = _lookup_summary(pid, scope)
                bucket = 'Changed'
                entry = f"- {ident}: {summary or 'completed'}"
                buckets.setdefault(bucket, []).append(entry)
    header = []
    if version:
        header.append(f"## {version} - {date or _today_str()}\n")
    else:
        header.append(f"## {date or _today_str()}\n")
    body = []
    for name in ('Added', 'Changed', 'Fixed'):
        items = buckets.get(name) or []
        if not items:
            continue
        body.append(f"### {name}\n")
        body.extend(items)
        body.append("")
    return "\n".join(header + body).strip() + "\n"


def _lookup_summary(plan_id: str, scope: dict) -> Optional[str]:
    """Lookup execution_summary for the scoped item (story/task)."""
    plan = plan_repo.load(plan_id)
    sid = scope.get('story_id')
    tid = scope.get('task_id')
    if tid:
        # tid is FQ
        for s in plan.stories:
            for t in (s.tasks or []):
                if t.id == tid:
                    return getattr(t, 'execution_summary', None)
    if sid:
        for s in plan.stories:
            if s.id == sid:
                return getattr(s, 'execution_summary', None)
    return None


def publish_changelog(markdown: str, target_path: str) -> None:
    with open(target_path, 'a', encoding='utf-8') as f:
        f.write("\n" + markdown)
