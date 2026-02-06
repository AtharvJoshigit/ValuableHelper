# Lessons Learned

## Provider Specifics: Google Gemini
- **Strict Messaging Order**: Gemini requires a specific sequence when using tools. If a model response contains 3 tool calls, the very next messages in the history must be exactly 3 tool results. You cannot "skip" a result or insert a user message in between.
- **Null Arguments**: Sometimes Gemini sends `null` or empty objects for tools with no parameters. The framework must handle this gracefully during parsing.

## Execution Engine
- **The Sync/Async Mix**: Many standard library tools (like `os` operations) are synchronous. Running them directly in an `async` loop blocks the orchestrator.
- **Pattern**: Use `functools.partial` and `loop.run_in_executor` to offload sync tools to a thread pool while keeping the orchestrator async-native.

<h2>Tool Design</h2>
- **Docstrings as Metadata**: The LLM's performance is directly tied to the quality of the tool's docstring. We use the docstring as the `description` field in the JSON Schema. Clear, imperative language works best.
- **Pydantic Validation**: Validating tool arguments using Pydantic *before* execution prevents unhandled crashes and allows the agent to see a structured error message it can potentially fix.

<h2>Multi-Agent Nesting</h2>
- **The "Agent as Tool" Pattern**: When an agent is wrapped as a tool, it needs its own isolated memory and provider instance. This prevents the sub-agent's conversation from leaking into the parent's context.

<h2>Self-Documentation Clarity</h2>
- **Differentiate Capabilities from Prompts**: When documenting my skills, I must clearly differentiate between describing *my* capability to *use* a tool (for my `me/knowledge/` files) and the internal system prompt or operational instructions for a sub-agent (which would typically reside elsewhere, like `me/my_agents`). My `me/knowledge/` documentation should focus on *my* function, interactions with a tool, its parameters, and expected outputs, in a descriptive and informative tone.

<h2>Workflow Efficiency</h2>
- **Batch Confirmations for Chained Steps**: When a sequence of logical, interconnected actions is clear and intended, I should summarize *all* upcoming changes and seek a single confirmation for the entire batch, rather than requesting confirmation for each individual step. This streamlines the workflow, reduces unnecessary back-and-forth, and maintains efficiency while still adhering to the principle of user approval before state changes.

## Quality Assurance & Verification
- **Trust but Verify (Code Generation)**: When a sub-agent (like `coder_agent`) generates code, do not assume it is syntactically correct just because the logic looks sound. Always verify code changes, especially string formatting and multi-line strings, by running a syntax check (e.g., `python -m py_compile <file>`) before confirming the task is complete. Blindly writing code to disk without verification leads to simple but breaking errors.