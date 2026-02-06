# Agent Archetypes

Agents (`src/agents/`) are specific configurations of the Core Engine, tailored with specific Prompts, Tools, and Models.

## Base Agent (`base_agent.py`)
- Factory class.
- Loads system prompts from `me/` directory.
- Configures the Provider (defaulting to Google).
- Subclasses override `_get_registry()` to equip tools.

## Main Agent (`main_agent.py`)
- **Role**: Orchestrator / Project Manager.
- **Model**: High reasoning capability (e.g., `gemini-1.5-pro`).
- **Tools**:
    - `SystemOperator`: For file/shell ops.
    - `CoderAgent`: For software engineering tasks.
- **Persona**: Defined in `me/whoami.md`.

## Coder Agent (`coder_agent.py`)
- **Role**: Senior Software Engineer.
- **Model**: High performance/coding capability (e.g., `gemini-1.5-pro`).
- **Tools**: Direct access to `ReadFile`, `ListDirectory`, `CreateFile`, `SearchAndReplace`, `RunCommand`.
- **Persona**: Defined in `me/my_agents/coder_agent.md`.
- **Safety**: Strictly mandated to plan and ask permission before file modifications in the first turn.

## System Operator (`system_operator_agent.py`)
- **Role**: DevOps / SysAdmin.
- **Tools**: `RunCommandTool`, Filesystem tools.
- **Purpose**: Handles low-level execution details so the Main Agent can stay strategic.
