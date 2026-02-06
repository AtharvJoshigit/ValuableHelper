# Task: Develop and Integrate Coder Agent

## Phase 1: Foundation & Persona
- [x] Create `me/my_agents/coder_agent.md` with high-standard coding persona.
    - [x] Include requirement for permission/summary before any file modification.
    - [x] Define standards for clean code, documentation, and error handling.
- [x] Enhance `src/engine/registry/library/filesystem_tools.py` with a `SearchAndReplaceTool` for surgical code edits.

## Phase 2: Coder Agent Implementation
- [x] Update `src/agents/coder_agent.py`:
    - [x] Set to high-performance model (e.g., `gemini-2.0-flash-exp`).
    - [x] Integrate `SystemOperatorAgent` as a tool for complex ops.
    - [x] Add direct `ReadFileTool`, `ListDirectoryTool`, `CreateFileTool`, and `SearchAndReplaceTool` for efficiency.
    - [x] Ensure it uses the `coder_agent.md` system prompt.

## Phase 3: Main Agent Integration
- [x] Update `src/agents/main_agent.py` to register `CoderAgent` as a tool.
- [x] Update `me/whoami.md` (Main Agent persona) to recognize the Coder Agent as the primary specialist for code generation and review.

## Phase 4: Validation
- [x] Run a test task: "Create a simple python utility to calculate fibonacci sequences and write it to src/utils/math.py".
- [x] Verify the Coder Agent provides a summary and asks for permission before writing.
