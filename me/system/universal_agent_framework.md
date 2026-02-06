# Universal Agent Framework - Architecture Documentation

## Overview
The Universal Agent Framework is a provider-agnostic, modular system designed to build complex AI agents with a focus on tool-use, multi-agent nesting, and robust execution.

## Core Design Principles
- **Universal Tool Definition**: Tools are defined once using Pydantic models. The framework automatically generates the required JSON Schema for any provider (Google, OpenAI, etc.).
- **Nested Autonomy**: Through the `AgentWrapper`, any agent can be treated as a tool by another agent, allowing for hierarchical multi-agent systems (e.g., a "Manager" agent calling a "Researcher" sub-agent).
- **Execution Flexibility**: Support for synchronous, asynchronous, and parallel tool execution.
- **Stateless Providers**: Providers (LLM connectors) are thin adapters, keeping the logic inside the core framework.

## Architecture Components

### 1. Core (`core/`)
- **`types.py`**: Defines the "Standard Language" of the framework. Contains Pydantic models for `Message`, `ToolCall`, `ToolResult`, `AgentResponse`, and `StreamChunk`.
- **`memory.py`**: Manages the conversation history. It ensures strict role alternation and handles the complex state of tool interactions.
- **`agent.py`**: The Orchestrator. Implements the main `run()` and `stream()` loops. It manages the handoffs between the Provider, the Memory, and the Execution Engine.

### 2. Registry (`registry/`)
- **`base_tool.py`**: The abstract base class for all tools. It utilizes Pydantic to convert Python type hints into JSON Schemas for the LLM.
- **`tool_registry.py`**: A centralized store for tools. It handles tool lookups and exports schemas formatted for specific providers.
- **`agent_wrapper.py`**: A specialized tool that wraps an `Agent` instance. This enables the creation of "Sub-Agents" that can be invoked by a parent LLM.

### 3. Executors (`executors/`)
- **`execution_engine.py`**: The engine responsible for calling tools. It supports `asyncio.gather` for parallel execution and intelligently detects whether a tool should be run in a thread pool (sync) or awaited (async).

### 4. Providers (`providers/`)
- **`base_provider.py`**: An interface defining how a provider must implement `generate()` and `stream()`.
- **`google/`**: Gemini 1.5 Pro/Flash implementation. Includes an `adapter.py` that translates framework types to Google's `Content` and `FunctionDeclaration` types.

## Key Workflow
1. **Input**: User provides text to the `Agent`.
2. **Retrieve**: Agent pulls full history from `Memory` and schemas from `Registry`.
3. **Generate**: `Provider` sends the data to the LLM.
4. **Decide**: 
    - If **Text**: The Agent returns the content (or streams it).
    - If **Tool Call**: The Agent passes the calls to the `Execution Engine`.
5. **Execute**: The engine runs tools (potentially in parallel) and returns `ToolResults`.
6. **Repeat**: Results are added to `Memory`, and the Agent calls the LLM again for a final summary.

## File Map
```text
universal_agent_framework/
├── core/
│   ├── types.py          # Framework models
│   ├── memory.py         # History management
│   └── agent.py          # Main orchestrator
├── registry/
│   ├── base_tool.py      # Base class for tools
│   ├── tool_registry.py  # Storage and export
│   └── agent_wrapper.py  # Agent-as-a-tool logic
├── executors/
│   ├── execution_engine.py # Async/Parallel runner
│   └── guardrails.py     # (Planned) Validation
└── providers/
    ├── base_provider.py  # Interface
    └── google/           # Gemini implementation
```
