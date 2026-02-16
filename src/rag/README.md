# RAG System Architecture

This module (`src/rag`) implements the Retrieval-Augmented Generation layer using **ChromaDB**. It provides persistent storage for Agent Memory (long-term) and Semantic Tool Definitions.

## Directory Structure

```text
src/rag/
├── config.py           # Configuration (Paths, Embedding Model selection)
├── client.py           # Singleton ChromaDB client (connection management)
├── embeddings.py       # Factory pattern for Embedding Providers (OpenAI, Gemini, Local)
├── schema.py           # Pydantic data models for Type Safety
└── stores/
    ├── base.py         # Abstract Base Class for Vector Stores
    ├── memory.py       # Episodic/Semantic Memory logic (handles Agent Isolation)
    └── tools.py        # Tool Indexing logic (handles Semantic Search)
```

## Key Components

### 1. Embedding Factory (`embeddings.py`)
Abstracts the underlying embedding model.
- **Default**: `all-MiniLM-L6-v2` (Local, Free, Fast).
- **Supported**: OpenAI (`text-embedding-3-small`), Google Gemini (`models/embedding-001`).
- **Configuration**: Change `EMBEDDING_PROVIDER` in `src/rag/config.py` or via Environment Variable.

### 2. Memory Store (`stores/memory.py`)
Handles long-term agent memory with strict isolation.
- **Scoping**: All queries require an `agent_id`. Agent A cannot see Agent B's memories unless explicitly allowed.
- **Metadata**: Stores `role` (user/assistant), `timestamp`, and `importance`.

### 3. Tool Store (`stores/tools.py`)
Enables "Intent-Based" tool discovery.
- **Indexing**: Embeds the tool's `description` and `docstring`.
- **Retrieval**: Agents query with natural language (e.g., "I need to calculate a date"), and the system returns the JSON Schema for the `DateCalculator` tool.

## Usage Example

```python
from src.rag.stores.tools import ToolVectorStore
from src.rag.stores.memory import MemoryVectorStore

# 1. Tool Search
tool_store = ToolVectorStore()
tools = tool_store.find_tools("check weather in NY")

# 2. Memory Recall
mem_store = MemoryVectorStore()
context = mem_store.retrieve_memory(agent_id="agent_007", query="mission details")
```
