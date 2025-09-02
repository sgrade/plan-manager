import os
import yaml
import logging

from pydantic import ValidationError

from typing import List, Dict, Any
from plan_manager.domain.models import Plan
from plan_manager.config import PLAN_FILE_PATH, ARCHIVE_PLAN_FILE_PATH, TODO_DIR, PLANS_INDEX_FILE_PATH


logger = logging.getLogger(__name__)


def ensure_initialized(file_path: str = PLAN_FILE_PATH) -> None:
    """Ensure the main plan file exists on disk.

    Creates parent directory and writes an empty plan structure if missing.
    """
    plan_dir = os.path.dirname(file_path)
    os.makedirs(plan_dir, exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"stories": []}, f,
                           default_flow_style=False, sort_keys=False)
        logger.info(f"Initialized new plan file at {file_path}")


def _plan_file_path(plan_id: str) -> str:
    return os.path.join(TODO_DIR, plan_id, 'plan.yaml')


def _ensure_plans_index_exists() -> None:
    index_dir = os.path.dirname(PLANS_INDEX_FILE_PATH)
    os.makedirs(index_dir, exist_ok=True)
    if not os.path.exists(PLANS_INDEX_FILE_PATH):
        with open(PLANS_INDEX_FILE_PATH, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"current": "default", "plans": [{"id": "default", "title": "default", "status": "TODO"}]}, f,
                           default_flow_style=False, sort_keys=False)


def load(plan_id: str = 'default') -> Plan:
    """Load a specific plan by ID from todo/<plan_id>/plan.yaml using a strict index.

    Requires that the plan be declared in the index; does not fall back to scanning directories.
    """
    _ensure_plans_index_exists()
    with open(PLANS_INDEX_FILE_PATH, 'r', encoding='utf-8') as idxf:
        idx = yaml.safe_load(idxf) or {}
    plans_list = idx.get('plans') or []
    if plan_id not in [p.get('id') for p in plans_list]:
        raise FileNotFoundError(
            f"Plan '{plan_id}' is not registered in the index at {PLANS_INDEX_FILE_PATH}")

    file_path = _plan_file_path(plan_id)
    plan_dir = os.path.dirname(file_path)
    os.makedirs(plan_dir, exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"id": plan_id, "title": plan_id, "stories": [
            ]}, f, default_flow_style=False, sort_keys=False)
        logger.info(
            f"Initialized new plan file for '{plan_id}' at {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}
    try:
        return Plan.model_validate(raw)
    except ValidationError as e:
        logger.exception(
            f"Plan file {file_path} failed schema validation: {e}")
        raise


def load_current() -> Plan:
    """Convenience wrapper to load the current plan from the index."""
    return load(get_current_plan_id())


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


def load_archive() -> Plan:
    """Load the archive plan from YAML (skips cross-story dependency checks)."""
    if not os.path.exists(ARCHIVE_PLAN_FILE_PATH):
        return Plan(stories=[])
    with open(ARCHIVE_PLAN_FILE_PATH, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}
    # Skip dependency checks via context
    return Plan.model_validate(raw, context={"skip_dependency_check": True})


def save_archive(plan: Plan) -> None:
    """Persist a Plan model to the archive plan YAML file."""
    data = plan.model_dump(mode='json', exclude_none=True)
    os.makedirs(os.path.dirname(ARCHIVE_PLAN_FILE_PATH), exist_ok=True)
    with open(ARCHIVE_PLAN_FILE_PATH, 'w', encoding='utf-8') as f:
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
