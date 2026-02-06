# Providers System

Providers (`src/engine/providers/`) act as the translation layer between the Framework's standard types and specific LLM APIs.

## Base Provider (`base_provider.py`)
Abstract Base Class enforcing the interface:
- `generate(history, tools) -> AgentResponse`
- `stream(history, tools) -> Iterator[StreamChunk]`

## Google Provider (`google/`)
Implementation for Gemini models (using `google-genai` SDK).

### Key Components
- **`provider.py`**:
    - Manages the `genai.Client`.
    - **Schema Conversion**: Dynamically converts Pydantic-generated JSON Schemas into Google's `FunctionDeclaration` format.
    - **Streaming**: Handles Google's specific chunk structure to yield standard `StreamChunk` objects.
- **`adapter.py`**:
    - **History Conversion**: Maps Framework `Message` objects to Google `Content` objects.
    - **Response Conversion**: Maps Google `GenerateContentResponse` back to `AgentResponse`.

### Tool Calling Implementation
Google requires tools to be passed in a `tools` configuration object. The provider automatically:
1.  Extracts schemas from `BaseTool` instances.
2.  Converts types (e.g., `array`, `object`) to Google's strict type system.
3.  Wraps them in a `genai_types.Tool`.

### Streaming Details
The `stream` method listens for both text chunks and function call chunks. It constructs `ToolCall` objects on the fly as the model emits them.
