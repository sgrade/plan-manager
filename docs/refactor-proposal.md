# Refactoring Plan: Aligning with the New Workflow

This document outlines the plan to refactor the Plan Manager codebase to align it with the new, task-centric workflow defined in `.cursor/rules/project-management.mdc`.

The primary goal is to shift the application's logic from a story-centric model to a task-centric one, implementing a mandatory two-gate review process for all agent work. Backward compatibility is not a requirement.

---

## **Story 1: Align Data Models and Core Logic**

**Description**: Update the core data models and service logic to match the new task-centric, two-gate review workflow.

**Tasks**:

1.  **Update `Status` Enum**: Add `PENDING_REVIEW` to the `Status` enum in `domain/models.py` to support the new workflow.
2.  **Refactor `Task` Model**: In `domain/models.py`, rename the `execution_intent` field to `implementation_plan` to distinguish it from the durable `description`. The generic `approval` field will be removed.
3.  **Simplify `Story` Model**: In `domain/models.py`, remove all execution-related fields (`implementation_plan`, `execution_summary`, `approval`) from the `Story` model. Stories will now function purely as containers for tasks.
4.  **Deprecate Story Execution Logic**: Remove all status update and approval logic from `services/story_service.py`. The service will be simplified to only manage the lifecycle of stories as containers.
5.  **Implement New Task Workflow**: In `services/task_service.py`, implement the new mandatory two-gate review lifecycle (`TODO` → `IN_PROGRESS` → `PENDING_REVIEW` → `DONE`). This will be the new core of the application's execution logic.

---

## **Story 2: Refactor Commands and UI**

**Description**: Update the user-facing commands to be contextual and dynamic, aligning with the new, more intuitive workflow.

**Tasks**:

1.  **Create `backlog` Command**: To avoid confusion with the `Plan` data model, the user-facing `plan` command will be renamed to `backlog`. New files (`tools/backlog_tools.py` and `services/backlog_service.py`) will be created to house the contextual logic for backlog refinement and task decomposition.
2.  **Refactor `approve` Command**: Update `tools/approval_tools.py` and its underlying service to implement the new contextual approval logic, which handles plan approval, pre-execution review, post-execution review, and the "fast-track" shortcut.
3.  **Refactor `status` Command**: Update the `status` service to provide the new dynamic, state-based output that changes based on the current task's state.
4.  **Update `project-management.mdc`**: Update the rules file to reflect the command rename (`plan` -> `backlog`).
5.  **Clean Up**: Remove any now-unused tools or services to ensure the codebase remains clean.
