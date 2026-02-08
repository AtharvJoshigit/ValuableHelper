# Implementation Plan: Plan Manager & Task Architecture

## Phase 1: Domain & Tools Refinement
- [ ] **Update Domain Model** (`src/domain/task.py`)
    - Add `PAUSED` to `TaskStatus` enum.
    - Ensure `priority` field is robust.
- [ ] **Enhance TaskStoreTool** (`src/tools/task_store_tool.py`)
    - Uncomment and fix existing code.
    - Add `create_subtask` method (handles `parent_id`).
    - Add `add_dependency` and `remove_dependency` methods.
    - Add `list_tasks` with filtering by priority and status.

## Phase 2: Plan Manager Logic (The Brain)
- [ ] **Create System Prompt** (`me/my_agents/plan_manager_prompt.md`)
    - Define role: Strategic Project Manager.
    - **Protocol: Approval** - Set complex tasks to `WAITING_APPROVAL`. Wait for Main Agent/User `APPROVED`.
    - **Protocol: Priority** - If Critical/High task arrives, set current `IN_PROGRESS` to `PAUSED`.
    - **Protocol: Dependencies** - Do not start tasks with uncleared dependencies.
- [ ] **Activate Plan Manager Agent** (`src/agents/plan_manager_agent.py`)
    - Uncomment code.
    - Register `TaskStoreTool`.
    - Register `CoderAgent` and `SystemOperator` as tools (delegation).

## Phase 3: Integration & Event Wiring
- [ ] **Update Main Agent** (`src/agents/main_agent.py`)
    - Initialize a shared `TaskStore` instance.
    - Register `TaskStoreTool` so Main Agent can view/approve tasks.
- [ ] **Event Bus Integration** (`src/services/event_listener.py` - New)
    - Create a listener for `TASK_CREATED`.
    - Logic: When `TASK_CREATED`, trigger `PlanManager` to analyze/breakdown.
    - Logic: When `TASK_STATUS_CHANGED` (to `APPROVED`), trigger `PlanManager` to execute.

## Phase 4: Validation
- [ ] **Test Workflow**
    - Create a complex task via Main Agent.
    - Verify Plan Manager breaks it down.
    - Verify Approval flow.
    - Verify Priority interruption.