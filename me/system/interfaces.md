# Interfaces & Services

The framework is designed to be accessible via multiple interfaces. The primary implementation currently is Telegram.

## Telegram Bot (`src/services/telegram_bot/`)
A secure, private bot interface using `python-telegram-bot`.

### Architecture
- **`bot.py`**: Main entry point.
- **State**: Maintains a persistent `Agent` instance per user session in `context.user_data["agent"]`.
- **Security**:
    - `PRIVACY_MODE`: configurable (User ID, Username, Password, Hybrid).
    - `@require_auth`: Decorator protecting sensitive handlers.

### Key Commands
- `/start`: Initializes a new `MainAgent` for the user.
- `/research <topic>`: Spawns a dedicated research task (uses `AIResearchHandler`).
- `/auth <password>`: For password-based access.

### Message Handling
- **Text Messages**: routed to `agent.chat()` (or `agent.run()`).
- **Long Responses**: Automatically chunked into 4096-character blocks to respect Telegram limits.
- **Formatting**: Uses Markdown parsing for rich text output.