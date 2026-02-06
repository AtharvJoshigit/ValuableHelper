# Lessons Learned

## Provider Specifics: Google Gemini
- **Strict Messaging Order**: Gemini requires a specific sequence when using tools. If a model response contains 3 tool calls, the very next messages in the history must be exactly 3 tool results. You cannot "skip" a result or insert a user message in between.
- **Null Arguments**: Sometimes Gemini sends `null` or empty objects for tools with no parameters. The framework must handle this gracefully during parsing.

## Execution Engine
- **The Sync/Async Mix**: Many standard library tools (like `os` operations) are synchronous. Running them directly in an `async` loop blocks the orchestrator.
- **Pattern**: Use `functools.partial` and `loop.run_in_executor` to offload sync tools to a thread pool while keeping the orchestrator async-native.

## Tool Design
- **Docstrings as Metadata**: The LLM's performance is directly tied to the quality of the tool's docstring. We use the docstring as the `description` field in the JSON Schema. Clear, imperative language works best.
- **Pydantic Validation**: Validating tool arguments using Pydantic *before* execution prevents unhandled crashes and allows the agent to see a structured error message it can potentially fix.

## Multi-Agent Nesting
- **The "Agent as Tool" Pattern**: When an agent is wrapped as a tool, it needs its own isolated memory and provider instance. This prevents the sub-agent's conversation from leaking into the parent's context.
