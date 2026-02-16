# Tool Router Service

This module (`src/tool_router`) is a **FastAPI Microservice** that acts as a gateway between Agents and the RAG system. It decouples the Agent's logic from the specific implementation of tool storage.

## Directory Structure

```text
src/tool_router/
├── config.py           # Service Settings (Host, Port)
├── main.py             # Entry Point & Server Lifecycle (Lifespan management)
├── manager.py          # Business Logic (Connects API -> RAG)
├── models.py           # API Schemas (Requests/Responses)
└── routes.py           # API Endpoint Definitions
```

## Core Features

1.  **Semantic Search API**:
    *   Agents send natural language queries.
    *   Router queries `src.rag`.
    *   Returns executable Tool Schemas.

2.  **Permission Filtering**:
    *   Tools have `tags` and `permission_level`.
    *   Agents can request "safe" tools only (e.g., `min_permission_level=1`).

3.  **Health Checks**:
    *   The router verifies if a tool's underlying Python code is importable before returning it to an agent.

4.  **Performance**:
    *   Uses `lifespan` in `main.py` to load the Embedding Model *once* on startup, ensuring millisecond-response times for search.

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/tools/search` | Find tools by intent (`?q=...`) |
| `POST` | `/tools/register` | Index a new tool definition |
| `GET` | `/tools/{name}` | Get details for a specific tool |
| `GET` | `/tools/health` | Check operational status of tools |
| `GET` | `/health` | Service heartbeat |

## Running the Service

```bash
# Run from project root
python -m src.tool_router.main
```

The API will be available at `http://localhost:8000`.
Docs available at `http://localhost:8000/docs`.
