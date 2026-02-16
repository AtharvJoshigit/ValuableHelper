# Telegram Bot Integration Documentation

This document outlines the Telegram bot's functionality and how the AI (me!) can integrate with it for direct communication with authorized users.

## 1. Purpose of the Telegram Bot (`tele_bot`)

The `tele_bot` serves as a private communication channel, allowing authorized users to interact with the AI agent (me!) directly through Telegram. It handles user authentication, command processing, and message exchange.

## 2. Core Components

*   **`tele_bot/bot.py`**:
    *   **Role:** The main bot application. It initializes the `python-telegram-bot` `Application`, registers command handlers (`/start`, `/help`, `/research_topic`, `/adduser`, `/removeuser`, `/listusers`, `/auth`), and a general message handler (`handle_message`).
    *   **Key Functions:**
        *   `is_authorized(user)`: Checks if a user is whitelisted based on `PRIVACY_MODE` settings.
        *   `require_auth(func)`: A decorator to ensure commands are only executed by authorized users.
        *   `authenticate(update, context)`: Handles password-based authentication.
        *   `start(update, context)`: Initializes the AI agent for the user session.
        *   `handle_message(update, context)`: Processes incoming text messages, feeds them to the AI agent, and sends back the agent's response. It also manages status messages and splits long responses into multiple Telegram messages.
        *   `researchTopic(update, context)`: A command handler to trigger research tasks, leveraging the `AIResearchHandler`.
        *   `run()`: Starts the Telegram bot's polling loop.

*   **`tele_bot/config.py`**:
    *   **Role:** Manages privacy settings and user authorization.
    *   **Key Variables:**
        *   `AUTHORIZED_USERS` (list of int): Contains a whitelist of Telegram user IDs authorized to use the bot. The first ID is considered the `ADMIN_USER_ID`.
        *   `AUTHORIZED_USERNAMES` (list of str): (Optional) Whitelist of Telegram usernames.
        *   `SECRET_PASSWORD` (str): Password for `PASSWORD` or `HYBRID` privacy modes.
        *   `PRIVACY_MODE` (str): Defines the authentication method ("USER_ID", "USERNAME", "PASSWORD", "HYBRID").

*   **`tele_bot/messages.py`**: (Not detailed in `bot.py` or `config.py` in terms of explicit usage for sending messages, but likely contains predefined message strings or templates.)

## 3. AI (My) Integration with Telegram Bot

My primary method for communicating directly with the user via Telegram is through a conceptual `send_telegram_message` tool. This tool will directly leverage the underlying Telegram bot's `context.bot.send_message` capability.

### 3.1. `send_telegram_message` (Conceptual Tool)

*   **Purpose:** To send a text message to a specified Telegram `chat_id`.
*   **Parameters:**
    *   `chat_id` (int): The unique identifier of the Telegram user or chat to send the message to. This will typically be the user's `user.id`.
    *   `message` (str): The text content of the message to be sent.
*   **Usage Context:** I can call this tool when I need to provide updates, ask clarifying questions, deliver results, or generally communicate with the user through the Telegram interface. When the user interacts with the Telegram bot, their `chat_id` is available within the `Update` object handled by the bot.
*   **Example (Conceptual Tool Call):**
    ```python
    # When the AI wants to send a message to the user:
    telegram_bot.send_message(
        chat_id=user_telegram_id, 
        message="Hello! I've completed your task."
    )
    ```

### 3.2. Obtaining `chat_id`

*   The `chat_id` for direct communication can be found in `tele_bot/config.py` within the `AUTHORIZED_USERS` list.
*   Users can also obtain their `chat_id` by messaging `@userinfobot` on Telegram.

### 3.3. Interaction Flow for the AI

1.  **Incoming Message:** User sends a message to the Telegram bot.
2.  **`handle_message` in `bot.py`:** The bot receives the message, extracts the `chat_id` (from `update.effective_chat.id` or `update.effective_user.id`), and passes the `user_message` to the AI agent (me!).
3.  **AI Processing:** I process the `user_message` and determine if a response is needed back to Telegram.
4.  **AI Sending Message:** If I need to respond, I will formulate the `message` content and use my conceptual `send_telegram_message` tool, providing the `chat_id` I received from the incoming message.
5.  **Bot Sending Message:** The `tele_bot` (specifically `context.bot.send_message`) then dispatches my message to the user's Telegram chat.

## 4. Considerations for AI (Me!)

*   **Authorization:** I must always assume I am interacting with an authorized user through the Telegram bot. The `tele_bot` itself handles the initial authorization.
*   **Message Length:** Telegram has a message length limit (4096 characters). The `handle_message` function in `bot.py` already implements logic to split long messages, so I can send longer content, and the bot will manage the splitting.
*   **Error Handling:** If there are issues sending a message, the `tele_bot`'s error handling (`error_handler` function) will log the issue.

This documentation ensures that I have a clear understanding of how to effectively use the Telegram bot for communication, enabling a more interactive and direct experience with you!