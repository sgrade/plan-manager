# Project Workflow Diagrams

This document outlines the command workflows for the Plan Manager.

---

### Unified Planning

The following diagram illustrates the single, consistent workflow used for planning at every level of the project hierarchy. It includes paths for both manual creation and prompt-assisted ("Assisted") creation of child work items.

```mermaid
graph TD
    A[Start] --> B["User runs <strong>list_&lt;items&gt;</strong>"];
    B --> C{Desired &lt;Item&gt; exists?};
    C -- No --> D["User runs <strong>create_&lt;item&gt;</strong>"];
    D --> B;
    C -- Yes --> E["User runs <strong>set_current_&lt;item&gt; [id]</strong>"];
    E --> F["Current &lt;Item&gt; is set"];
    
    F --> G{Decompose into children?};
    G -- No --> Z([End]);
    
    subgraph "Child Item Creation & Approval"
      G -- Yes --> H{How?};
      
      H -- Manual --> I["User runs <strong>create_&lt;child&gt;</strong> one-by-one"];
      I --> I_approve["(Implicit Approval)"];

      H -- Assisted --> J["User runs <strong>/propose_&lt;children&gt;</strong> prompt"];
      J --> K["System returns a list of proposals (not yet created)"];
      K --> L["User reviews and approves proposals"];
      L --> M["Agent runs <strong>create_&lt;child&gt;</strong> for each approved proposal"];
    end

    I_approve --> N[Children Created];
    M --> N;
```

**The Proposal-Approval Model**

A key concept in this workflow is that newly suggested items (especially from the "Assisted" path) are considered **proposals**, not final work items. The user must give an explicit approval before the agent proceeds to formally create them in the system. For manual creation, this approval is implicit in the act of creating the item.

**Connecting the Workflows**

The "Unified Planning" diagram shows how to select and define work items. When a **Task** is created and approved for the backlog (landing in the `TODO` state), its lifecycle begins, as illustrated in the diagram below.

---

### Task Execution Lifecycle

Once a task is set as the current work item, it follows a strict, two-gate review lifecycle. The state diagram below illustrates this process.

```mermaid
graph TD
    A([Start]) --> B[Task is in <strong>TODO</strong> state];
    B --> C{What does the user do?};
    
    C -- User runs <strong>prepare</strong> --> D[Agent runs <strong>propose_steps</strong>];
    D --> E["Proposed task steps documented <br> (Status is still <strong>TODO</strong>)"];
    E --> F["User runs <strong>approve_task</strong>"];
    
    C -- User runs <strong>approve_task [task_id]</strong> --> G[Fast-Track];
    
    F --> H[Task is in <strong>IN_PROGRESS</strong> state];
    G --> H;
    
    H --> I["Agent runs <strong>submit_for_review</strong>"];
    I --> J[Task is in <strong>PENDING_REVIEW</strong> state];
    
    J --> K{User reviews the code};
    K -- User runs <strong>approve_task</strong> --> L[Task is in <strong>DONE</strong> state];
    K -- User runs <strong>change [instructions]</strong> --> H;
    
    L --> L2["Changelog snippet is returned"];
    L2 --> M([End]);

```

---

### A Note on Plan and Story Statuses

It is important to note that only `Task` items have a direct, manageable lifecycle. The status of a `Story` or a `Plan` is a **rolled-up property** that is automatically calculated based on the statuses of its children.

-   A **Story's status** is a summary of its `Task` statuses (e.g., if any task is `IN_PROGRESS`, the story is `IN_PROGRESS`).
-   A **Plan's status** is a summary of its `Story` statuses.

Because their statuses are not managed directly, there are no state diagrams for `Plan` or `Story` items. The `Task` lifecycle is the core driver of the entire system's state.
