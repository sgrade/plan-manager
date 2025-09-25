## Project Workflow Diagrams

This document outlines the command workflows for the Plan Manager.

### Overview

The user journey follows a logical progression from high-level planning to task execution:

1.  **[Unified Planning (Plans and Stories)](#unified-planning-plans-and-stories):** The workflow for defining and selecting high-level work items (plans and stories).
2.  **[Work Breakdown (Refinement)](#work-breakdown-refinement):** The process for decomposing a story into concrete tasks.
3.  **[Task Execution](#task-execution):** The guided lifecycle for selecting a task, getting it approved, and marking it as `DONE`.

---

### Unified Planning (Plans and Stories)

The following diagram illustrates the single, consistent workflow used for the creation and selection of high-level work items (plans, stories). This process is typically driven by the user in natural language.

```mermaid
graph TD
    A([Start]) --> B["User runs list_<items>"];
    B --> C{Desired <Item> exists?};
    C -- No --> D["User runs create_<item>"];
    D --> B;
    C -- Yes --> E["User runs set_current_<item> [id]"];
    E --> F["Current <Item> is set"];
    F --> Z([End]);
```

---

### Work Breakdown (Refinement)

The following diagram illustrates how a higher-level work item (a Story) is decomposed into children (Tasks). It includes paths for both manual creation and prompt-assisted ("Assisted") creation of child work items.

A key concept in this workflow is that newly suggested items are considered **proposals**, not final work items. The user must give an explicit approval before the agent proceeds to formally create them in the system. 

Assisted prompts used in this workflow:
- **create_plan**: draft a plan (epic) JSON, stage for review, then create the plan upon approval.
- **create_stories**: propose stories for a plan, stage for review, then create stories upon approval.
- **create_tasks**: propose tasks for a story, stage for review, then create tasks upon approval.
- **create_steps**: propose implementation steps for a task, stage for review, then attach steps upon approval.

```mermaid
graph TD
    A([Start]) --> B{How?};
    B -- Manual --> C[User guides the agent in the chat] --> E;
    B -- Assisted --> D["User runs /create_<children> prompt"] --> E;
    E["Agent follows the prompts to propose children"];
    E --> F["User reviews the proposals"];
    F --> G{"Changes required?"};
    G -- Yes --> C;
    G -- No --> H["User types approve"] --> I;
    I["Agent runs create_<child> for each item in the approved proposal"];
    I --> J[Children Created];
    J --> L([End]);
```

---

### Task Execution

The task execution lifecycle begins with selecting a task to work on. If a task is not already set as the current work item, the agent will proactively list the available tasks and suggest the next one. Once a task is selected, it follows a strict, two-gate review lifecycle:

1.  **Pre-Execution Approval (Gate 1):** The user approves the proposed steps (or fast-tracks the task) before work begins.
2.  **Code Review Approval (Gate 2):** After the agent submits its work, the user performs a final review to mark the task as done.

The diagrams below illustrate this process.

```mermaid
graph TD
    A([Start]) --> B{Current task set?};
    
    subgraph Select Current Task
        B -- No --> C["Agent runs list_tasks"];
        C --> D["Agent proposes next task"];
        D --> E{User confirms?};
        E -- Yes --> F["Agent runs set_current_task"];
        E -- No --> G["User runs set_current_task [id]"];
        F --> H[Current Task is set];
        G --> H;
    end

    B -- Yes --> H;

    H --> C1[Agent asks the user: What would you like to do?];
    C1 --> C2{What does the user do?};
    
    subgraph Gate 1: Pre-Execution Approval
        C2 -- Plan First --> D2["User runs /create_steps prompt"];
        D2 --> E2["Agent saves proposed steps to todo/temp/steps.json"];
        E2 --> F2["User reviews/edits the steps.json file"];
        F2 --> G2["user says 'approve_task' in chat"];
        G2 --> G3["Agent runs create_task_steps with final steps.json"];
        
        G3 --> G4["Agent runs approve_task"];
        G4 --> J[Task is in **IN_PROGRESS** state];

        C2 -- Fast-Track --> C3["user says 'approve_task' in chat"];
        C3 --> H2["Agent runs create_task_steps (no proposal UI)"];
        H2 --> G4;
    end
        
    J --> J2["User says 'execute' in chat"];
    J2 --> J3["Agent executes the task"];
    J3 --> K["Agent runs submit_for_review(execution_summary)"];
    
    subgraph Gate 2: Code Review Approval
        K --> L["Agent displays execution_summary and asks user to approve or request changes"]
        L --> M[Task is in PENDING_REVIEW state];
        M --> M1{User reviews the code};
        M1 -- Approve --> Q["User runs approve_task"] --> N[Task is in DONE state];
        M1 -- Request Changes --> M2["User provides feedback in natural language"] --> M3;
        M3["Agent runs request_changes"] --> J;
    end
    
    N --> N2["Changelog snippet is returned"];
    N2 --> Z([End]);

```

---

### Plan and Story Statuses

It is important to note that only `Task` items have a direct, manageable lifecycle. The status of a `Story` or a `Plan` is a **rolled-up property** that is a calculated based on the statuses of its children.

-   A **Story's status** is a summary of its `Task` statuses (e.g., if any task is `IN_PROGRESS`, the story is `IN_PROGRESS`).
-   A **Plan's status** is a summary of its `Story` statuses.

Because their statuses are not managed directly, there are no state diagrams for `Plan` or `Story` items. The `Task` lifecycle is the core driver of the entire system's state.
