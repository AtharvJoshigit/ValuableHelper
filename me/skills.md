# Skills & Capabilities

## Framework Core
- **Universal Tool Registry**: Defining tools using Pydantic models with automatic JSON Schema generation.
- **Provider-Agnostic Interface**: Unified interface for LLM interaction (supports `generate` and `stream`).
- **Parallel Tool Execution**: Capability to run multiple tool calls concurrently using `asyncio.gather`.
- **Hybrid Sync/Async Execution**: Automatic detection and execution of sync tools in threads and async tools in the main event loop.
- **Hierarchical Agents**: Wrapping full agents as tools to allow for complex, nested multi-agent systems.
- **Context Management**: Robust handling of conversation history, ensuring valid message sequences (system, user, assistant, tool).

## Implemented Tools
- **Filesystem Tools**: 
  - `list_directory`: Explore the workspace.
  - `read_file`: Access file contents.
  - `create_file`: Write new files (with path creation).
  - `delete_file`: Remove files.
- **System Operator**: Sub-agent capable of performing multi-step file operations and shell commands.

## Supported Providers
- **Google (Gemini)**: Full integration with Gemini 1.5 Pro and Flash models, including tool-calling support.

## Engineering Standards
- **Modular Design**: Separation of concerns between core logic, registry, providers, and executors.
- **Type Safety**: Extensive use of Pydantic and type hinting throughout the codebase.