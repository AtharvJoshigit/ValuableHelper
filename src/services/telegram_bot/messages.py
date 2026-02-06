"""
This file centralizes all user-facing messages for the bot.
"""

# Access Control
ACCESS_DENIED_MESSAGE = """🚫 **Access Denied**

This bot is private.
Your User ID: `{user_id}`
Your Username: @{username}

Contact the administrator for access."""

# Start Command
START_INITIALIZING_MESSAGE = """👋 **Hello!**

I am your private AI assistant.
🔄 Initializing system..."""

AGENT_READY_MESSAGE = """✅ **System Online.**

How can I help you today?"""

AGENT_ALREADY_INITIALIZED_MESSAGE = "✅ Agent is already active and listening."

# Help Command
HELP_MESSAGE = """🔒 **Bot Commands**

/start - Wake up the AI agent
/help - Show this message
/myinfo - Show your user details

**Admin Only:**
/adduser <id> - Whitelist a user
/removeuser <id> - Revoke user access
/listusers - Show all authorized users"""

# Agent Status & Permissions
PERMISSION_REQUEST = """⚠️ **Permission Required**

Agent wants to execute: `{tool_name}`
Arguments: `{args}`

Type 'yes' to approve, or 'no' to deny."""

PERMISSION_GRANTED = "✅ Permission granted."
PERMISSION_DENIED = "❌ Permission denied."
AGENT_THINKING = "🤔 Thinking..."

# Admin User Management
ADD_USER_ADMIN_ONLY = "❌ Only admins can add users."
ADD_USER_USAGE = "Usage: /adduser <user_id>"
USER_ALREADY_AUTHORIZED = "User `{user_id}` is already in the whitelist."
USER_ADDED_SUCCESS = "✅ User `{user_id}` added successfully."
INVALID_USER_ID = "❌ Invalid ID. Must be numeric."

REMOVE_USER_ADMIN_ONLY = "❌ Only admins can remove users."
REMOVE_USER_USAGE = "Usage: /removeuser <user_id>"
CANNOT_REMOVE_MAIN_ADMIN = "❌ Cannot remove the primary admin."
USER_REMOVED_SUCCESS = "✅ User `{user_id}` removed successfully."
USER_NOT_IN_WHITELIST = "User `{user_id}` is not found in the whitelist."

NO_AUTHORIZED_USERS = "No authorized users found."
AUTHORIZED_USERS_HEADER = """🔐 **Authorized Users:**

"""
ADMIN_TAG = " (Admin)"

# General Agent Interactions
AGENT_NOT_INITIALIZED = "⚠️ Agent sleeping. Type /start to wake it up."
AGENT_PROCESSING_MESSAGE = "🔍 Processing..."
AGENT_ERROR_RESPONSE = "❌ Agent Error: {error_message}"