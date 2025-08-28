import os
import yaml
import logging

from pydantic import ValidationError

from plan_manager.domain import Plan
from plan_manager.config import PLAN_FILE_PATH, ARCHIVE_PLAN_FILE_PATH


logger = logging.getLogger(__name__)


def ensure_initialized(file_path: str = PLAN_FILE_PATH) -> None:
    """Ensure the main plan file exists on disk.

    Creates parent directory and writes an empty plan structure if missing.
    """
    plan_dir = os.path.dirname(file_path)
    os.makedirs(plan_dir, exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"stories": []}, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Initialized new plan file at {file_path}")


def load() -> Plan:
    """Load the main plan from YAML and validate it into a Plan model."""
    ensure_initialized()
    with open(PLAN_FILE_PATH, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}
    try:
        return Plan.model_validate(raw)
    except ValidationError as e:
        logger.exception(f"Plan file {PLAN_FILE_PATH} failed schema validation: {e}")
        raise


def save(plan: Plan) -> None:
    """Persist a validated Plan model to the main plan YAML file."""
    data = plan.model_dump(mode='json', exclude_none=True)
    os.makedirs(os.path.dirname(PLAN_FILE_PATH), exist_ok=True)
    with open(PLAN_FILE_PATH, 'w', encoding='utf-8') as f:
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


