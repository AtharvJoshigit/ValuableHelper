# Universal Agent Framework - Upcoming Work

## Documentation & Knowledge Base (me/)
- [ ] Populate `me/overview.md` with the project vision.
- [ ] Populate `me/skills.md` with current technical capabilities.
- [ ] Initialize `me/lessons.md` with initial development patterns.

## Goal: advanced Provider & Tool Capabilities

## Phase 6: Streaming Support
- [ ] **Advanced Stream Parsing**
    - [ ] Handle partial JSON parsing for tools in `providers/google/provider.py`
    - [ ] Aggregated tool call reconstruction from stream chunks

## Phase 7: Standard Tool Library (`registry/library/`)
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
