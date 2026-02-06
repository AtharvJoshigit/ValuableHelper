# Engine Core

The Engine Core is the central orchestration layer of the Universal Agent Framework. It manages the interaction between the LLM providers, tool execution, and conversation state.

## Core Components

### 1. Agent (`src/engine/core/agent.py`)
The `Agent` class is the main orchestrator. It manages the iterative loop of:
1.  **Input Processing**: Receives user input and adds it to memory.
2.  **LLM Generation**: Calls the configured `BaseProvider` with the current history and available tools.
3.  **Response Handling**:
    *   If the LLM provides a direct response, it's returned to the user.
    *   If the LLM makes tool calls, the agent hands them off to the `ExecutionEngine`.
4.  **Tool Execution**: Executes tools and adds the results back into memory as `TOOL` messages.
5.  **Iteration**: Repeats the loop until a final answer is generated or `max_steps` is reached.

The `Agent` supports both `run()` (standard async) and `stream()` (async generator for real-time feedback).

### 2. Memory (`src/engine/core/memory.py`)
Handles conversation history.
- **Persistence**: Currently held in-memory within the `Memory` object.
- **Context Management**: Supports `max_messages` to prevent context window overflow, while preserving the critical `SYSTEM` message.

### 3. Types (`src/engine/core/types.py`)
Strongly typed Pydantic models used throughout the framework:
- `Message`: Represents an entry in the conversation (System, User, Assistant, Tool).
- `ToolCall` / `ToolResult`: Define the structure for calling functions and receiving their outputs.
- `StreamChunk`: The data structure used for streaming responses.

## Execution Flow
1. `Agent.run(input)`
2. `Memory.add_user_message(input)`
3. `while step < max_steps:`
4.   `provider.generate(history, tools)`
5.   `Memory.add_message(assistant_response)`
6.   `if not tool_calls: return response`
7.   `execution_engine.execute_tool_calls(tool_calls)`
8.   `Memory.add_message(tool_results)`