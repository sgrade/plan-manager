# Refactoring & Improvement Proposals

### Assisted Planning Workflow

**Problem:** Decomposing high-level work items (like Plans or Stories) into their constituent children (Stories or Tasks) is a manual, repetitive process. The user must manually create each child item one by one.

**Proposal:** Introduce a new, prompt-driven "Assisted Creation" workflow to automate the planning and decomposition of work items. This will be a user-controlled feature that complements the existing manual creation process.

**Key Features:**

1.  **Fractal Planning Prompts:**
    *   Introduce a set of generative prompts that can decompose a parent work item into a structured list of proposed children.
    *   `propose_stories_for_plan`: Takes a Plan's context and suggests a list of Stories.
    *   `propose_tasks_for_story`: Takes a Story's context and suggests a list of Tasks.

2.  **Schema-Driven Output:**
    *   The generative prompts will use Pydantic schemas (`ProposeStoriesOut`, `ProposeTasksOut`) to ensure their output is reliable, structured JSON.
    *   These schemas will be located in a new `src/plan_manager/schemas/prompts.py` file.

3.  **Conversational Review & Approval:**
    *   The output of the generative prompts will be presented to the user as a list of **proposals**.
    *   The user will review this list and give approval via a natural language command to the agent.
    *   The agent will be responsible for iterating through the approved proposals and calling the existing, singular `create_*` tools. No new "bulk create" server logic is needed.

4.  **Optional Review Checklists (New Prompts):**
    *   To support the user's review process, introduce simple, static, informational prompts.
    *   `review_story_proposals_checklist`: Provides a checklist for evaluating Story proposals.
    *   `review_task_proposals_checklist`: Provides a checklist for evaluating Task proposals.
    *   These prompts will not use schemas as their output is for human consumption only.

**Implementation Plan:**

1.  Create `src/plan_manager/schemas/prompts.py` with the necessary Pydantic models.
2.  In `src/plan_manager/prompts/workflow_prompts.py`:
    *   Implement the two generative prompts (`propose_stories_for_plan`, `propose_tasks_for_story`) using the new schemas.
    *   Implement the two static review checklist prompts.
    *   Register all four new prompts with the MCP server.

