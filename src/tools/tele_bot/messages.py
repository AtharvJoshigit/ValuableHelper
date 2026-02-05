# tele_bot/messages.py
"""
This file centralizes all user-facing messages for the bot,
making it easier to manage and update bot responses.
"""

# Access Control Messages
ACCESS_DENIED_MESSAGE = (
    "🚫 Access Denied!\n\n"
    "This bot is private and only available to authorized users.\n"
    "Your User ID: `{user_id}`\n"
    "Your Username: @{username}\n\n"
    "If you should have access, contact the bot owner."
)

PASSWORD_AUTH_NOT_ENABLED = "Password authentication is not enabled for this bot."
PASSWORD_PROMPT_MESSAGE = (
    "🔐 Please provide the password.\n"
    "Usage: /auth <password>"
)
AUTH_SUCCESS_MESSAGE = (
    "✅ Authentication successful!\n"
    "You now have access to the bot.\n"
    "Type /start to begin."
)
INVALID_PASSWORD_MESSAGE = (
    "❌ Invalid password!\n"
    "Access denied."
)

# Start Command Messages
START_INITIALIZING_MESSAGE = (
    "Hi There! 👋\n\n"
    "I am your private AI agent.\n"
    "🔄 Initializing AI agent...\n"
    "Provider: Google\n"
    "Model: gemini-3-pro-preview\n" # Changed to reflect the actual model used
)
AGENT_READY_MESSAGE = "✅ Agent is ready.\n\n" \
                      "You can now have a chat. Try asking me something!"
AGENT_ALREADY_INITIALIZED_MESSAGE = "Agent is already initialized and ready to chat!"


# Help Command Messages
HELP_MESSAGE = (
    "🔒 **Private Bot Help**\n\n"
    "This bot is configured for private use only.\n\n"
    "**Commands:**\n"
    "/start - Initialize your AI agent and start a chat\n"
    "/help - Show this help message\n"
    "/research_general <topic> - Conduct general research on a topic\n"
    "/research_trends <topic> - Analyze current trends for a topic\n"
    "/daily_digest <category1, category2...> - Get a daily research digest\n"
    "/myinfo - Get your user information\n"
    "/adduser <user_id> - Add user to whitelist (Admin only)\n"
    "/removeuser <user_id> - Remove user from whitelist (Admin only)\n"
    "/listusers - List all authorized users (Admin only)"
)

# Research Command Messages
RESEARCH_GENERAL_USAGE_MESSAGE = "Usage: /research_general <topic>"
RESEARCH_TRENDS_USAGE_MESSAGE = "Usage: /research_trends <topic>"
DAILY_DIGEST_USAGE_MESSAGE = "Usage: /daily_digest <category1, category2, ...>"
RESEARCH_STATUS_MESSAGE = "🔍 Researching **{topic}**… please wait"
TRENDS_STATUS_MESSAGE = "📈 Analyzing trends for **{topic}**… please wait"
DIGEST_STATUS_MESSAGE = "📰 Generating daily digest for categories: **{categories}**… please wait"
RESEARCH_ERROR_MESSAGE = "❌ An error occurred during the research operation."
RESEARCH_SUCCESS_HEADER = "✅ **Research Results for '{topic}':**\n\n"
TRENDS_SUCCESS_HEADER = "✅ **Trend Analysis for '{topic}':**\n\n"
DIGEST_SUCCESS_HEADER = "✅ **Daily Research Digest ({categories}):**\n\n"

# User Management Messages (Admin Only)
ADD_USER_ADMIN_ONLY = "❌ Only the main admin can add users."
ADD_USER_USAGE = (
    "Usage: /adduser <user_id>\n\n"
    "To get someone's user ID, ask them to message @userinfobot"
)
USER_ALREADY_AUTHORIZED = "User `{user_id}` is already authorized."
USER_ADDED_SUCCESS = (
    "✅ User `{user_id}` has been added to the whitelist!\n"
    "They can now use the bot."
)
INVALID_USER_ID = "❌ Invalid user ID. Please provide a numeric user ID."

REMOVE_USER_ADMIN_ONLY = "❌ Only the main admin can remove users."
REMOVE_USER_USAGE = "Usage: /removeuser <user_id>"
CANNOT_REMOVE_MAIN_ADMIN = "❌ You cannot remove the main admin!"
USER_REMOVED_SUCCESS = "✅ User `{user_id}` has been removed from the whitelist."
USER_NOT_IN_WHITELIST = "User `{user_id}` is not in the whitelist."

NO_AUTHORIZED_USERS = "No authorized users found."
AUTHORIZED_USERS_HEADER = "🔐 **Authorized Users:**\n\n"
ADMIN_TAG = " (Main Admin)"

# Handle Message (Agent Interaction) Messages
AGENT_NOT_INITIALIZED = (
    "⚠️ Agent not initialized.\n"
    "Please type /start first."
)
AGENT_PROCESSING_MESSAGE = "🔍 Processing your request… please wait" # Changed to be more generic
AGENT_ERROR_RESPONSE = "❌ An error occurred with the agent: {error_message}" # Improved clarity
AGENT_SUCCESS_HEADER = "✅ **Response from Agent :**\n\n"
AGENT_CALLS_INFO = "Agent calls: \n\n{agent_calls}"
UNABLE_TO_GET_RESPONSE = "❌ Unable to get a response from the agent. Error: {error_message}"

# My Info Command Messages
MYINFO_MESSAGE = (\
    "👤 **Your Information:**\n\n"
    "Name: {first_name} {last_name}\n"
    "Username: @{username}\n"
    "User ID: `{user_id}`\n"
    "Language: {language_code}\n\n"
    "💬 **Chat Info:**\n"
    "Chat Type: {chat_type}\n"
    "Chat ID: `{chat_id}`\n\n"
    "🔐 **Access Status:** Authorized ✅"
)
