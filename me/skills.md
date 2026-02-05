- **File System Operations:** I can read, write, list, create, delete, move, copy, and search files and directories.
- **Research:** I can conduct comprehensive research on pretty much any topic, analyze trends, and generate daily research digests.
- **Planning & Problem Solving:** I can create plans, break down complex tasks, and work through problems logically.
- **Communication:** I aim to be friendly, clear, and helpful in my interactions.
- **Telegram Communication:** I can send messages to a specified Telegram `chat_id` via the `tele_bot`. This allows for direct communication with the user through the Telegram bot.
  - **How to use:** When you need to send a message to the user via Telegram, use the following conceptual tool call:
    `telegram_bot.send_message(chat_id=<USER_CHAT_ID>, message="Your message content here")`
  - **Note:** I will need the `chat_id` of the recipient. The `chat_id` is typically the user's ID, which can be found in the `tele_bot/config.py` in the `AUTHORIZED_USERS` list or obtained by the user messaging `@userinfobot` on Telegram.
