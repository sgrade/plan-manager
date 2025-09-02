import os
import yaml
import logging

# from pydantic import ValidationError

from typing import List, Dict, Any
from plan_manager.domain.models import Plan
from plan_manager.config import TODO_DIR, PLANS_INDEX_FILE_PATH


logger = logging.getLogger(__name__)


def _plan_file_path(plan_id: str) -> str:
    return os.path.join(TODO_DIR, plan_id, 'plan.yaml')


def _ensure_plans_index_exists() -> None:
    index_dir = os.path.dirname(PLANS_INDEX_FILE_PATH)
    os.makedirs(index_dir, exist_ok=True)
    if not os.path.exists(PLANS_INDEX_FILE_PATH):
        with open(PLANS_INDEX_FILE_PATH, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"current": "default", "plans": [{"id": "default", "title": "default", "status": "TODO"}]}, f,
                           default_flow_style=False, sort_keys=False)


def save(plan: Plan, plan_id: str = 'default') -> None:
    """Persist a validated Plan model to todo/<plan_id>/plan.yaml and ensure it's in the index."""
    _ensure_plans_index_exists()
    with open(PLANS_INDEX_FILE_PATH, 'r', encoding='utf-8') as idxf:
        idx = yaml.safe_load(idxf) or {}
    plans_list = idx.get('plans') or []
    if plan_id not in [p.get('id') for p in plans_list]:
        plans_list.append({"id": plan_id, "title": getattr(
            plan, 'title', plan_id), "status": getattr(plan, 'status', 'TODO')})
        idx['plans'] = plans_list
        with open(PLANS_INDEX_FILE_PATH, 'w', encoding='utf-8') as idxf:
            yaml.safe_dump(idx, idxf, default_flow_style=False,
                           sort_keys=False)

    data = plan.model_dump(mode='json', exclude_none=True)
    file_path = _plan_file_path(plan_id)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def list_plans() -> List[Dict[str, Any]]:
    """List plans from the strict index file. No directory scanning fallback."""
    _ensure_plans_index_exists()
    with open(PLANS_INDEX_FILE_PATH, 'r', encoding='utf-8') as idxf:
        idx = yaml.safe_load(idxf) or {}
    plans_list = idx.get('plans')
    if plans_list is None:
        raise ValueError(
            f"Plans index at {PLANS_INDEX_FILE_PATH} is missing 'plans' key")
    return list(plans_list)


def get_current_plan_id() -> str:
    _ensure_plans_index_exists()
    with open(PLANS_INDEX_FILE_PATH, 'r', encoding='utf-8') as f:
        idx = yaml.safe_load(f) or {}
    cur = idx.get('current')
    if not cur:
        raise ValueError(
            f"'current' plan is not set in index {PLANS_INDEX_FILE_PATH}")
    plans_list = idx.get('plans') or []
    if cur not in [p.get('id') for p in plans_list]:
        raise ValueError(
            f"Current plan '{cur}' not present in index {PLANS_INDEX_FILE_PATH}")
    return cur


def set_current_plan_id(plan_id: str) -> None:
    _ensure_plans_index_exists()
    with open(PLANS_INDEX_FILE_PATH, 'r', encoding='utf-8') as f:
        idx = yaml.safe_load(f) or {}
    plans_list = idx.get('plans') or []
    if plan_id not in [p.get('id') for p in plans_list]:
        raise ValueError(
            f"Plan '{plan_id}' not present in index {PLANS_INDEX_FILE_PATH}")
    idx['current'] = plan_id
    with open(PLANS_INDEX_FILE_PATH, 'w', encoding='utf-8') as f:
        yaml.safe_dump(idx, f, default_flow_style=False, sort_keys=False)
