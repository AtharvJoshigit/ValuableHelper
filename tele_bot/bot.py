"""
PRIVATE Telegram Bot - Only for authorized users
This bot will only respond to whitelisted user IDs

"""

import asyncio
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import logging

from tele_bot import config
from src.agents.research_agent.ai_research_handler import AIResearchHandler
from src.handler.main_agent_handler import create_main_agent

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========================================

def is_authorized(user) -> bool:
    """Check if user is authorized to use the bot."""
    if config.PRIVACY_MODE == "USER_ID":
        return user.id in config.AUTHORIZED_USERS
    
    elif config.PRIVACY_MODE == "USERNAME":
        return user.username in config.AUTHORIZED_USERNAMES
    
    elif config.PRIVACY_MODE == "PASSWORD":
        return user.id in config.authenticated_users
    
    elif config.PRIVACY_MODE == "HYBRID":
        return user.id in config.AUTHORIZED_USERS and user.id in config.authenticated_users
    
    return False

def require_auth(func):
    """Decorator to check authorization before executing commands."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        # Special case for authenticate command
        if func.__name__ == 'authenticate':
            return await func(update, context)
        
        # Check authorization
        if not is_authorized(user):
            logger.warning(f"Unauthorized access attempt by {user.username} (ID: {user.id})")
            await update.message.reply_text(
                "🚫 Access Denied!\n\n"
                "This bot is private and only available to authorized users.\n"
                f"Your User ID: {user.id}\n"
                f"Your Username: @{user.username or 'Not set'}\n\n"
                "If you should have access, contact the bot owner."
            )
            return
        
        # User is authorized, execute the function
        return await func(update, context)
    
    return wrapper

async def authenticate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Authenticate with password (only for PASSWORD or HYBRID mode)."""
    user = update.effective_user
    
    if config.PRIVACY_MODE not in ["PASSWORD", "HYBRID"]:
        await update.message.reply_text("Password authentication is not enabled for this bot.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "🔐 Please provide the password.\n"
            "Usage: /auth <password>"
        )
        return
    
    password = context.args[0]
    
    if password == config.SECRET_PASSWORD:
        config.authenticated_users.add(user.id)
        logger.info(f"User {user.username} (ID: {user.id}) authenticated successfully")
        await update.message.reply_text(
            "✅ Authentication successful!\n"
            "You now have access to the bot.\n"
            "Type /start to begin."
        )
    else:
        logger.warning(f"Failed authentication attempt by {user.username} (ID: {user.id})")
        await update.message.reply_text(
            "❌ Invalid password!\n"
            "Access denied."
        )

@require_auth
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - only for authorized users."""
    await update.message.reply_text(
        "Hi There! 👋\n\n"
        "I am your private AI agent.\n"
        "🔄 Initializing AI agent...\n"
        "Provider: Google\n"
        "Model: gemini-3-flash-preview\n"
    )

    agent = create_main_agent(
        provider="google",
        model="gemini-3-pro-preview",
    )

    # Store agent in user session
    context.user_data["agent"] = agent

    await update.message.reply_text(
        "✅ Agent is ready.\n\n"
        "You can now have chat."
    )

@require_auth
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command."""
    await update.message.reply_text(
        "🔒 **Private Bot Help**\n\n"
        "This bot is configured for private use only.\n\n"
        "**Commands:**\n"
        "/start - Start the bot\n"
        "/help - Show this help\n"
        "/myinfo - Get your user information\n"
        "/adduser <user_id> - Add user to whitelist\n"
        "/removeuser <user_id> - Remove user from whitelist\n"
        "/listusers - List all authorized users",
        parse_mode='Markdown'
    )

# @require_auth
# async def myinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Show user information."""
#     user = update.effective_user
#     chat = update.effective_chat
    
#     info_text = (
#         f"👤 **Your Information:**\n\n"
#         f"Name: {user.first_name} {user.last_name or ''}\n"
#         f"Username: @{user.username or 'Not set'}\n"
#         f"User ID: `{user.id}`\n"
#         f"Language: {user.language_code or 'Unknown'}\n\n"
#         f"💬 **Chat Info:**\n"
#         f"Chat Type: {chat.type}\n"
#         f"Chat ID: {chat.id}\n\n"
#         f"🔐 **Access Status:** Authorized ✅"
#     )
    
#     await update.message.reply_text(info_text, parse_mode='Markdown')


async def researchTopic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Research a topic and provide information."""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: /research <topic>")
        return # Important: Stop execution if no args

    topic = ' '.join(context.args)
    
    # 1. Send the initial status message and store it
    status_message = await update.message.reply_text(f"🔍 Researching **{topic}**… please wait")
    
    try:
        research_handler = AIResearchHandler()
        
        # 2. Correct way to run a blocking function in an async handler
        loop = asyncio.get_running_loop()
        researchResult = await loop.run_in_executor(
            None, 
            research_handler.handle_research, 
            topic
        )

        # 3. Format the final output
        # final_text = f"✅ **Research Results for '{topic}':**\n\n{researchResult.text}"
        
        # 4. Update the "Researching..." message with actual results
        # await status_message.edit_text(final_text, parse_mode='Markdown')
        
        # 1. Get the text content
        extracted_text = getattr(researchResult, 'text', str(researchResult))
        final_text = f"✅ **Research Results for '{topic}':**\n\n{extracted_text}"

        # 2. Check if it's too long for a single message
        if len(final_text) <= 4096:
            await status_message.edit_text(final_text, parse_mode=ParseMode.MARKDOWN)
        else:
            # Delete the "Researching..." message and send multiple messages
            await status_message.delete()
            
            # Split by chunks of 4000 to be safe
            for i in range(0, len(final_text), 4000):
                chunk = final_text[i:i+4000]
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, 
                    text=chunk
                )

        logger.info(f"Research completed for {user.username} (ID: {user.id})")

    except Exception as e:
        logger.error(f"Error during research: {e}")
        await status_message.edit_text("❌ An error occurred during research.")



@require_auth
async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new user to the whitelist (admin only)."""
    user = update.effective_user
    
    # Check if user is the main admin (first user in the list)
    if user.id != config.AUTHORIZED_USERS[0]:
        await update.message.reply_text("❌ Only the main admin can add users.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: /adduser <user_id>\n\n"
            "To get someone's user ID, ask them to message @userinfobot"
        )
        return
    
    try:
        new_user_id = int(context.args[0])
        
        if new_user_id in config.AUTHORIZED_USERS:
            await update.message.reply_text(f"User {new_user_id} is already authorized.")
            return
        
        config.AUTHORIZED_USERS.append(new_user_id)
        logger.info(f"User {new_user_id} added to whitelist by {user.id}")
        
        await update.message.reply_text(
            f"✅ User {new_user_id} has been added to the whitelist!\n"
            f"They can now use the bot."
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric user ID.")

@require_auth
async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a user from the whitelist (admin only)."""
    user = update.effective_user
    
    # Check if user is the main admin
    if user.id != config.AUTHORIZED_USERS[0]:
        await update.message.reply_text("❌ Only the main admin can remove users.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /removeuser <user_id>")
        return
    
    try:
        user_id_to_remove = int(context.args[0])
        
        if user_id_to_remove == config.AUTHORIZED_USERS[0]:
            await update.message.reply_text("❌ You cannot remove the main admin!")
            return
        
        if user_id_to_remove in config.AUTHORIZED_USERS:
            config.AUTHORIZED_USERS.remove(user_id_to_remove)
            logger.info(f"User {user_id_to_remove} removed from whitelist by {user.id}")
            await update.message.reply_text(f"✅ User {user_id_to_remove} has been removed from the whitelist.")
        else:
            await update.message.reply_text(f"User {user_id_to_remove} is not in the whitelist.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

@require_auth
async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all authorized users."""
    if not config.AUTHORIZED_USERS:
        await update.message.reply_text("No authorized users found.")
        return
    
    users_list = "🔐 **Authorized Users:**\n\n"
    for idx, user_id in enumerate(config.AUTHORIZED_USERS, 1):
        admin_tag = " (Main Admin)" if idx == 1 else ""
        users_list += f"{idx}. User ID: `{user_id}`{admin_tag}\n"
    
    await update.message.reply_text(users_list, parse_mode='Markdown')

@require_auth
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.user_data.get("agent")

    if not agent:
        await update.message.reply_text(
            "⚠️ Agent not initialized.\n"
            "Please type /start first."
        )
        return

    user_message = update.message.text
    status_message = await update.message.reply_text(f"🔍 `00`… please wait")

    try:
        agent.status_message = status_message
        result = agent.chat(user_message)  # or agent.run(...)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return
    print("." * 100)
    print(result)
    print("." * 100)    
    # logger.info(f"Research completed for {user.username} (ID: {user.id})")
    if result is not None and result['status'] == "success":
        extracted_text = result['response']
        final_text = f"✅ **Response from Agent :**\n\n{extracted_text}"

        # 2. Check if it's too long for a single message
        if len(final_text) <= 4096:
            await status_message.edit_text(final_text)
        else:
            # Delete the "Researching..." message and send multiple messages
            await status_message.delete()
            
            # Split by chunks of 4000 to be safe
            for i in range(0, len(final_text), 4000):
                chunk = final_text[i:i+4000]
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, 
                    text=chunk
                )
        await update.message.reply_text(f"Agent calls : \n\n {result['agent_calls']}")
    await status_message.reply_text(f"❌ Unable to get a response from the agent. Error : {result['error']}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

def run():
    """Start the private bot."""
    print("=" * 50)
    print("PRIVATE TELEGRAM BOT")
    print("=" * 50)
    print(f"Privacy Mode: {config.PRIVACY_MODE}")
    print(f"Authorized Users: {config.AUTHORIZED_USERS}")
    print("=" * 50)
    

    # Create the Application
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    # Authentication command (works even without authorization)
    application.add_handler(CommandHandler("auth", authenticate))
    
    # Protected commands (require authorization)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler('research_topic', researchTopic))
    # application.add_handler(CommandHandler("myinfo", myinfo_command))
    application.add_handler(CommandHandler("adduser", add_user_command))
    application.add_handler(CommandHandler("removeuser", remove_user_command))
    application.add_handler(CommandHandler("listusers", list_users_command))
    
    # Protected message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Private bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)