# Nexus Task Lifecycle (Specialist Swarm Architecture)

The system operates on a hierarchical delegation model designed for precision and accountability.

## 1. Task Lifecycle Stages
1. **Creation**: High-level **Parent Tasks** are created via `add_task`.
2. **Planning**: The **Planner Agent** decomposes the Parent into atomic **Subtasks**. 
3. **Approval Gate**: The Parent is automatically moved to `WAITING_APPROVAL`. No subtasks can run yet.
4. **Activation**: Upon User Approval, the Parent moves to `APPROVED`. The **Priority Queue** now releases subtasks.
5. **Execution**: The **Plan Director** routes subtasks to assigned specialists (Coder, Researcher, SysOp).
6. **Handover**: Specialists execute, write evidence to `result_summary`, and set status to `WAITING_REVIEW`.
7. **Review**: The **Planner Agent** validates the evidence.
    - **Pass**: Status -> `DONE`.
    - **Fail**: Status -> `TODO` with feedback in `context`.
8. **Consolidation**: Once all children are `DONE`, the **Plan Director** auto-completes the Parent with a consolidated summary.

## 2. Core Constraints
- **Absolute Authority**: The Task **Title** and **Description** are the only source of truth.
- **Privacy**: God-mode tools (Gmail, Dynamic Creator) are reserved for the **Main Agent**.
- **Evidence-Based**: No task is closed without verifiable output in the `result_summary`.
- **Gated Workflow**: The `PriorityQueue` strictly prevents "ghost runs" of subtasks until the user approves the plan.

In this system all the Test files should be stored in /test dir
no projected realted files shoudl be stored under /dump dir
