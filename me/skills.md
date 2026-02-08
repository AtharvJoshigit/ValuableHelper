
# Skills & Capabilities

## Framework Core
- **Universal Tool Registry**: Defining tools using Pydantic models with automatic JSON Schema generation.
- **Provider-Agnostic Interface**: Unified interface for LLM interaction (supports `generate` and `stream`).
- **Parallel Tool Execution**: Capability to run multiple tool calls concurrently using `asyncio.gather`.
- **Hybrid Sync/Async Execution**: Automatic detection and execution of sync tools in threads and async tools in the main event loop.
- **Hierarchical Agents**: Wrapping full agents as tools to allow for complex, nested multi-agent systems.
- **Context Management**: Robust handling of conversation history, ensuring valid message sequences (system, user, assistant, tool).

## Core Capabilities (Implemented Tools)

- **Directory Listing**: The ability to inspect and list the contents (files and subdirectories) of any specified directory or the current working directory within the file system.
    *   *Knowledge File:* `me/knowledge/filesystem/directory_listing.md`

- **File Reading**: The capability to access and retrieve the textual content of any file located at a given path within the file system.
    *   *Knowledge File:* `me/knowledge/filesystem/file_reading.md`

- **Advanced System Operations**: The capacity to delegate complex system-level tasks to a specialized sub-agent. This includes performing advanced file manipulations (such as creating, modifying, or deleting files), as well as executing arbitrary shell commands to interact directly with the operating system.
    *   *Knowledge File:* `me/knowledge/system_operations/advanced_system_operations.md`

- **Gmail Search and Read**: The ability to search, read, and process emails from a Gmail inbox, including filtering and extracting information from message bodies and headers.
    *   *Knowledge File:* `me/knowledge/communication/gmail_search_read.md`

## Supported Providers
- **Google (Gemini)**: Full integration with Gemini 1.5 Pro and Flash models, including tool-calling support.

## Engineering Standards
- **Modular Design**: Separation of concerns between core logic, registry, providers, and executors.
- **Type Safety**: Extensive use of Pydantic and type hinting throughout the codebase.

- **Email Sending (Gmail)**: The ability to compose and send emails to any recipient via the Gmail API, handling authentication automatically.
    *   *Knowledge File:* `me/knowledge/communication/gmail.md`