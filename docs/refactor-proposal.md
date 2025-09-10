# Refactoring & Improvement Proposals (Post v0.5.4)

This document outlines a series of proposed enhancements to the Plan Manager CLI to improve usability, consistency, and robustness. These proposals are based on feedback and observations gathered during the testing of the v0.5 workflow.

---

### 1. Scoped Reporting

**Problem:** The current `report` command only provides a detailed view of the active story. There is no easy way to get a high-level overview of the entire plan's progress.

**Proposal:** Enhance the `report` command to support different scopes.

-   **`report`**: (Default behavior) Shows a detailed summary of the **current story**, including task statuses and the next actionable step. This remains the "ground-level" view.
-   **`report plan`**: Provides a "10,000-foot view" of the **entire plan**, summarizing the status of all stories within it (e.g., `Story 1: 3/5 tasks DONE`, `Story 2: 0/4 tasks DONE`).

---

### 2. Command Name Consistency

**Problem:** The CLI has inconsistencies in command naming conventions. For instance, `create_plan` and `create_story` exist, but creating a task is handled implicitly by the `update_story` service, which is not intuitive.

**Proposal:** Introduce a dedicated `create_task` command to align with the existing `create_plan` and `create_story` commands. This will make the CLI more predictable and easier to learn.

---

### 3. Proactive Blocker Detection

**Problem:** A task's status does not automatically update to `BLOCKED` if its dependencies are not met. A user might not realize a task is blocked until they attempt to start it (`approve_task`).

**Proposal:** Implement a service that proactively updates the status of tasks. When a task is completed, the system should re-evaluate the dependencies of other tasks. Any `TODO` task whose dependencies are not fully met should have its status automatically set to `BLOCKED`. This provides immediate visibility into project dependencies and blockers.

---

### 4. Interactive `set_current` Commands

**Problem:** Using the `set_current_plan`, `set_current_story`, and `set_current_task` commands requires the user to first list the items to find their exact IDs. This is a multi-step, manual process.

**Proposal:** Make the `set_current_*` commands interactive. If a command is run without an ID, the tool should:
1.  Fetch the list of available items (e.g., `set_current_story` would call `list_stories`).
2.  Present the list to the user as a set of choices.
3.  Allow the user to select an item from the list to set it as the current context.

---

### 5. Improved Error Messages

**Problem:** Some error messages are generic or unhelpful, making it difficult to diagnose issues. For example, a `KeyError` in the service layer might be caught and replaced with a generic message like "There is no tasks to approve."

**Proposal:** Conduct a systematic review of the error handling in the service and tool layers. Replace generic exceptions and messages with specific, actionable feedback that helps the user understand what went wrong and how to fix it.


