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
    N1([Start]) --> N2["User runs list_<items>"];
    N2 --> N3{Desired <Item> exists?};
    N3 -- No --> N4["User runs create_<item>"];
    N4 --> N2;
    N3 -- Yes --> N5["User runs set_current_<item> [id]"];
    N5 --> N6["Current <Item> is set"];
    N6 --> N7([End]);
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
    N1([Start]) --> N2{How?};
    N2 -- Manual --> N3[User guides the agent in the chat] --> N5;
    N2 -- Assisted --> N4["User runs /create_<children> prompt"] --> N5;
    N5["Agent follows the prompts to propose children"];
    N5 --> N6["User reviews the proposals"];
    N6 --> N7{"Changes required?"};
    N7 -- Yes --> N3;
    N7 -- No --> N8["User types approve"] --> N9;
    N9["Agent runs create_<child> for each item in the approved proposal"];
    N9 --> N10[Children Created];
    N10 --> N11([End]);
```

---

### Task Execution

The task execution lifecycle begins with selecting a task to work on. If a task is not already set as the current work item, the agent will proactively list the available tasks and suggest the next one. Once a task is selected, it follows a strict, two-gate review lifecycle:

1.  **Pre-Execution Approval (Gate 1):** The user approves the proposed steps (or fast-tracks the task) before work begins.
2.  **Code Review Approval (Gate 2):** After the agent submits its work, the user performs a final review to mark the task as done.

The diagrams below illustrate this process.

```mermaid
graph TD
    N1([Start]) --> N2{Current task set?};
    
    subgraph Select Current Task
        N2 -- No --> N3["Agent runs list_tasks"];
        N3 --> N4["Agent proposes next task"];
        N4 --> N5{User confirms?};
        N5 -- Yes --> N6["Agent runs set_current_task"];
        N5 -- No --> N7["User runs set_current_task [id]"];
        N6 --> N8[Current Task is set];
        N7 --> N8;
    end

    N2 -- Yes --> N8;

    N8 --> N9[Agent asks the user: What would you like to do?];
    N9 --> N10{What does the user do?};
    
    subgraph Gate 1: Pre-Execution Approval
        N10 -- Plan First (Assisted) --> N11["User runs /create_steps prompt"];
        N11 --> N12["Agent saves proposed steps to todo/temp/steps.json"];
        N12 --> N13["User reviews/edits the steps.json file"];
        N13 --> N14["User says 'approve steps' in chat"];
        N14 --> N15["Agent runs create_task_steps with final steps.json"];
        N15 --> N16["Agent runs approve_task"];
        N16 --> N17[Task is in **IN_PROGRESS** state];

        N10 -- Fast-Track --> N18["User says 'approve steps' in chat"];
        N18 --> N19["Agent runs create_task_steps (no proposal UI)"];
        N19 --> N16;
    end
        
    N17 --> N20["User says 'execute' in chat"];
    N20 --> N21["Agent executes the task"];
    N21 --> N22["Agent runs submit_for_review (non-empty execution_summary)"];
    
    subgraph Gate 2: Code Review Approval
        N22 --> N23["Agent displays execution_summary and asks user to approve or request changes"]
        N23 --> N24[Task is in PENDING_REVIEW state];
        N24 --> N25{User reviews the code};
        N25 -- Approve --> N26["User says 'approve review' in chat"] --> N26a["Agent runs approve_task"] --> N27[Task is in DONE state];
        N25 -- Request Changes --> N28["User provides feedback in natural language"] --> N29;
        N29["Agent runs request_changes"] --> N17;
    end
    
    N27 --> N30["Changelog snippet is returned"];
    N30 --> N31([End]);

```

---

### Plan and Story Statuses

It is important to note that only `Task` items have a direct, manageable lifecycle. The status of a `Story` or a `Plan` is a **rolled-up property** that is a calculated based on the statuses of its children.

-   A **Story's status** is a summary of its `Task` statuses (e.g., if any task is `IN_PROGRESS`, the story is `IN_PROGRESS`).
-   A **Plan's status** is a summary of its `Story` statuses.

Because their statuses are not managed directly, there are no state diagrams for `Plan` or `Story` items. The `Task` lifecycle is the core driver of the entire system's state.
