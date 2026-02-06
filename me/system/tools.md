# Tooling & Registry

The framework's extensibility heavily relies on its tool system, allowing agents to interact with external environments.

## Base Tool (`src/tools/base_tool.py`)
Abstract Base Class for all tools:
- **`name`**: Unique identifier (snake_case).
- **`description`**: Human-readable explanation for the LLM.
- **`parameters`**: Pydantic `BaseModel` defining input schema.
- **`_run(**kwargs)`**: Abstract method for tool's logic.
- **`run(**kwargs)`**: Wrapper for `_run` with error handling and logging.

## Tool Registry (`src/registry.py`)
Central component for managing available tools.

### Key Features
- **Singleton Pattern**: Ensures a single, accessible instance.
- **`register_tool(tool_instance)`**: Adds a tool to the registry.
- **`get_tool(name)`**: Retrieves a tool by its name.
- **`get_all_tools()`**: Returns a list of all registered tools.
- **Dynamic Registration**: Tools can be registered at runtime, allowing for context-specific toolsets.

### Tool Loading
- `CoreTools`: Core framework tools (e.g., `ReadFile`, `CreateFile`).
- `CustomTools`: Project-specific or user-defined tools.

## Core Tool Examples (`src/tools/core_tools/`)
- **`ReadFileTool`**: Reads content from a specified file path.
- **`CreateFileTool`**: Creates or overwrites a file with given content.
- **`ListDirectoryTool`**: Lists contents of a directory.
- **`RunCommandTool`**: Executes shell commands (with safety mechanisms).
- **`SearchAndReplaceTool`**: Modifies file content via string replacement.

## Tool Integration
- **Agent Configuration**: Agents receive a `ToolRegistry` instance.
- **Provider Conversion**: Providers convert tool schemas into LLM-specific function declarations (e.g., OpenAI functions, Google Gemini tools).
