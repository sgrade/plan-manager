# Ideas for LangGraph-based automation

A LangGraph orchestrator mostly adds control, not new capability.

If I redesigned Task Execution with LangGraph (simple, maintainable):
- Keep Plan Manager unchanged. The orchestrator lives on the client side (proxy MCP or sidecar), calling the same tools.
- Model the same gates with minimal nodes and hard guards:
    - Per-task graph (client/orchestrator)
        - require_current_task → ensures context is set; else return a clear error
        - require_approval(mode) → blocks until user chat approval is present in context
        - ensure_steps(mode)
            = plan_first: require steps be provided/confirmed by user; no generation
            = fast_track: generate steps once (no proposal UI) or accept provided steps
        - attach_steps → calls create_task_steps; idempotent (no-op if identical)
        - dependency_check → if BLOCKED, stop with actionable error
        - start_work → calls approve_task (agent tool call, distinct from user chat approval)
        - execute (free-form agent work, outside of MCP)
        - ensure_summary → require execution_summary
        = submit_for_review → calls submit_for_review(execution_summary)
        - wait_review → user chooses approve_task or request_changes; loop until DONE

Guards and idempotency (why fewer mistakes)
- Guards are code, not prose: nodes verify “approval present,” “steps exist,” “unblocked,” “summary present” before making each call.
- Each node is idempotent: it checks current status/snapshot (via get_task) and skips if already satisfied, so retries/resumes don’t reorder calls.

Minimal interface to Cursor (unchanged or one addition)
- Keep existing tools and wiring exactly the same, or optionally add one convenience in the proxy:
    - orchestrate_gate1(task_id, mode, steps?, approved?) → internally runs create_task_steps (if needed) then approve_task, with guards and idempotency, only after user chat approval is present.
- Everything else (approve_task, submit_for_review, request_changes) remains pass-through.

Why stop here
- You preserve today’s user interaction (draft → review/approve → attach → approve).
- You gain stronger sequencing and simple retries without complicating the server or the public tool API.
