# Universal Agent Framework - Upcoming Work

## Recent Wins
- [x] **Coder Agent Integrated**: Dedicated agent for code generation/review is fully operational and integrated into `MainAgent`.
- [x] **System Documentation**: Full architecture mapped in `me/system/`.

## Phase 0: System Documentation & Architecture Mapping (Complete)
- [x] **Engine Core Exploration**: Documented in `me/system/engine.md`
- [x] **Providers & Models Exploration**: Documented in `me/system/providers.md`
- [x] **Registry & Tools Exploration**: Documented in `me/system/tools.md`
- [x] **Agent Archetypes Exploration**: Documented in `me/system/agents.md`
- [x] **Services Exploration**: Documented in `me/system/interfaces.md`
- [x] **System Synthesis**: Updated `me/overview.md`

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
- [ ] **Context Management Tool**: Tool for MainAgent to explicitly clear/manage sub-agent memory ("wipe slate").
- [ ] **Supervisor Pattern**: Dedicated agent to coordinate multiple specialized sub-agents
- [ ] **Sequential Chain**: Pre-defined sequence of agent tasks
- [ ] **State Shared Memory**: Allowing agents to share a common blackboard/state

## Phase 10: Observability & Production Ready
- [ ] **Tracing**: Integration with LangSmith or Phoenix
- [ ] **Advanced Guardrails**: Input/Output PII scrubbing and safety checks
- [ ] **Persistence**: Database-backed memory for long-running conversations
- [ ] **CLI Interface**: A robust terminal UI for interacting with framework agents
- [ ] **Coder Agent Hardening**: Increase timeouts and implement partial file reading to prevent stalls.

## Phase 11: Telegram Interface Modernization
- [ ] [Telegram Bot Modernization Plan](tasks/modernize_telegram_bot.md)

## Completed
- [x] **Agent Archetypes Exploration**