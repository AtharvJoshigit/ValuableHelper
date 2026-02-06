# Project Overview: Universal Agent Framework & ValuableHelper

## The Vision
The goal is to build a highly modular, provider-agnostic framework for AI agents that excels at tool-use, multi-agent orchestration, and robust execution. This isn't just a library; it's the foundation for "ValuableHelper" – an autonomous orchestrator capable of managing complex engineering tasks.

## Why This Exists
- **Vendor Independence**: Switching from Google to OpenAI or Anthropic should be a configuration change, not a rewrite.
- **Hierarchical Intelligence**: Agents should be able to delegate tasks to specialized sub-agents seamlessly.
- **Reliability**: Built-in support for parallel execution, proper error handling, and structured tool definitions.

## Core Pillars
1. **Universal Tools**: Write Python/Pydantic code; the framework handles the JSON Schema and calling logic.
2. **Stateless Logic**: The core engine remains decoupled from specific LLM providers.
3. **Advanced Execution**: Native support for async, sync, and parallel tool calls.
4. **Autonomous Memory**: Sophisticated history management that maintains context through complex multi-turn tool interactions.
