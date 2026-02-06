# Universal Agent Framework - Implementation Plan

## Project Goal
Create a unified, provider-agnostic framework for building AI agents with:
- **Universal Tool Definition**: Define tools once (Pydantic), use anywhere.
- **Stateless Providers**: Plug-and-play LLM backends (Google, OpenAI, etc.).
- **Robust Execution**: Parallel tool calls, guardrails, and isolated sub-agents.
- **Streaming Support**: Unified streaming interface.

## Phase 1: Core Foundation & Types
- [x] **Define Data Types (`core/types.py`)**
- [x] **Define Interfaces (`providers/base_provider.py`)**
- [x] **Define Base Tool (`registry/base_tool.py`)**

## Phase 2: The Registry (Tool Store)
- [x] **Implement Pydantic Tool Logic**
- [x] **Create Tool Registry**

## Phase 3: Google Provider Implementation
- [x] **Implement Adapter (`providers/google/adapter.py`)**
- [x] **Implement Provider (`providers/google/provider.py`)**

## Phase 4: Execution Engine
- [x] **Local Executor (`executors/execution_engine.py`)**
- [x] **Parallel Execution**
- [x] **Support for Async Tools**

## Phase 5: Agent Orchestrator
- [x] **Memory Manager (`core/memory.py`)**
- [x] **The Agent Loop (`core/agent.py`)**
- [x] **Sub-Agent Wrapper (`registry/agent_wrapper.py`)**

## Phase 6: Streaming Support
- [x] **Agent Stream Handler**
    - [x] `agent.stream()` implementation in `core/agent.py`
- [x] **Basic Provider Streaming**
    - [x] Text streaming in `providers/google/provider.py`
- [ ] **Advanced Stream Parsing**
    - [ ] Handle partial JSON parsing for tools in `providers/google/provider.py`
    - [ ] Aggregated tool call reconstruction from stream chunks

## Phase 7: Standard Tool Library (`registry/library/`)
- [x] **Filesystem Tools**: `list_directory`, `read_file`, `create_file`
- [ ] **Web Search Tool**: Integration with Tavily or DuckDuckGo
- [ ] **Shell Execution Tool**: Secure sandboxed command execution
- [ ] **Request Tool**: Generic HTTP requests tool

## Phase 8: Provider Expansion
- [ ] **OpenAI Provider**: Implementation for GPT-4o/o1 models
- [ ] **Anthropic Provider**: Implementation for Claude 3.5 Sonnet
- [ ] **Ollama Provider**: Local model support

## Phase 9: Multi-Agent Patterns
- [ ] **Supervisor Pattern**: Dedicated agent to coordinate multiple specialized sub-agents
- [ ] **Sequential Chain**: Pre-defined sequence of agent tasks
- [ ] **State Shared Memory**: Allowing agents to share a common blackboard/state

## Phase 10: Observability & Production Ready
- [ ] **Tracing**: Integration with LangSmith or Phoenix
- [ ] **Advanced Guardrails**: Input/Output PII scrubbing and safety checks
- [ ] **Persistence**: Database-backed memory for long-running conversations
- [ ] **CLI Interface**: A robust terminal UI for interacting with framework agents
