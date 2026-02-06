import logging
import asyncio
import time
from typing import Dict

from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Local imports
from . import config, messages
# Absolute import from src root
from agents.main_agent import create_main_agent

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global state: Stores agent instances per user_id
user_agents: Dict[int, object] = {}

# ================= AUTHENTICATION =================

def is_authorized(user_id: int) -> bool:
    return user_id in config.AUTHORIZED_USERS

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_USER_IDS

async def check_auth(update: Update) -> bool:
    """Returns True if authorized, else sends rejection message."""
    user = update.effective_user
    if not is_authorized(user.id):
        logger.warning(f"Unauthorized access: {user.username} ({user.id})")
        await update.message.reply_text(
            messages.ACCESS_DENIED_MESSAGE.format(
                user_id=user.id,
                username=user.username or "Unknown"
            ),
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return False
    return True

# ================= COMMAND HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return

    user_id = update.effective_user.id
    
    if user_id in user_agents:
        await update.message.reply_text(messages.AGENT_ALREADY_INITIALIZED_MESSAGE)
        return

    msg = await update.message.reply_text(messages.START_INITIALIZING_MESSAGE, parse_mode=constants.ParseMode.MARKDOWN)
    
    # Initialize the MainAgent
    try:
        agent = create_main_agent()
        user_agents[user_id] = agent
        await msg.edit_text(messages.AGENT_READY_MESSAGE, parse_mode=constants.ParseMode.MARKDOWN)
        logger.info(f"Agent initialized for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to init agent: {e}")
        await msg.edit_text(f"❌ Initialization failed: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    await update.message.reply_text(messages.HELP_MESSAGE, parse_mode=constants.ParseMode.MARKDOWN)

async def myinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(
        f"""👤 **User Info**
ID: `{u.id}`
Username: @{u.username}
Admin: {is_admin(u.id)}""",
        parse_mode=constants.ParseMode.MARKDOWN
    )

# ================= ADMIN HANDLERs =================

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(messages.ADD_USER_ADMIN_ONLY)
        return

    if not context.args:
        await update.message.reply_text(messages.ADD_USER_USAGE)
        return

    try:
        new_id = int(context.args[0])
        if new_id in config.AUTHORIZED_USERS:
            await update.message.reply_text(messages.USER_ALREADY_AUTHORIZED.format(user_id=new_id), parse_mode=constants.ParseMode.MARKDOWN)
        else:
            config.AUTHORIZED_USERS.append(new_id)
            await update.message.reply_text(messages.USER_ADDED_SUCCESS.format(user_id=new_id), parse_mode=constants.ParseMode.MARKDOWN)
            logger.info(f"Admin {update.effective_user.id} added user {new_id}")
    except ValueError:
        await update.message.reply_text(messages.INVALID_USER_ID)

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(messages.REMOVE_USER_ADMIN_ONLY)
        return

    if not context.args:
        await update.message.reply_text(messages.REMOVE_USER_USAGE)
        return

    try:
        rem_id = int(context.args[0])
        if rem_id in config.ADMIN_USER_IDS:
            await update.message.reply_text(messages.CANNOT_REMOVE_MAIN_ADMIN)
            return

        if rem_id in config.AUTHORIZED_USERS:
            config.AUTHORIZED_USERS.remove(rem_id)
            if rem_id in user_agents:
                del user_agents[rem_id] # Kill their session
            await update.message.reply_text(messages.USER_REMOVED_SUCCESS.format(user_id=rem_id), parse_mode=constants.ParseMode.MARKDOWN)
            logger.info(f"Admin {update.effective_user.id} removed user {rem_id}")
        else:
            await update.message.reply_text(messages.USER_NOT_IN_WHITELIST.format(user_id=rem_id), parse_mode=constants.ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text(messages.INVALID_USER_ID)

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    if not is_admin(update.effective_user.id):
        return

    text = messages.AUTHORIZED_USERS_HEADER
    for uid in config.AUTHORIZED_USERS:
        tag = messages.ADMIN_TAG if uid in config.ADMIN_USER_IDS else ""
        text += f"- `{uid}`{tag}\n"
    
    await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)

# ================= CHAT HANDLER =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return

    user_id = update.effective_user.id
    agent = user_agents.get(user_id)

    if not agent:
        await update.message.reply_text(messages.AGENT_NOT_INITIALIZED)
        return

    user_text = update.message.text
    status_msg = await update.message.reply_text(messages.AGENT_THINKING)

    full_response = ""
    last_update_time = time.time()
    
    try:
        # Stream response from agent
        async for chunk in agent.stream(user_text):
            if hasattr(chunk, 'content') and chunk.content:
                full_response += chunk.content
                
                # Update message every 1.5 seconds to avoid API limits
                if time.time() - last_update_time > 1.5:
                    if full_response.strip():
                        try:
                            await status_msg.edit_text(full_response + " ▌")
                        except Exception:
                            pass
                        last_update_time = time.time()
        
        # Final update
        if full_response.strip():
            try:
                await status_msg.edit_text(full_response, parse_mode=constants.ParseMode.MARKDOWN)
            except Exception:
                # Fallback if markdown parsing fails
                await status_msg.edit_text(full_response)
        else:
            await status_msg.edit_text("✅ Done (No text output)")

    except Exception as e:
        logger.error(f"Error in chat handler: {e}")
        await status_msg.edit_text(messages.AGENT_ERROR_RESPONSE.format(error_message=str(e)))

# ================= RUNNER =================

def run():
    """Build and run the bot application."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("No token found! Set TELEGRAM_BOT_TOKEN in .env")
        return

    logger.info("Starting Bot...")
    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myinfo", myinfo))
    
    # Admin
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("listusers", list_users))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    run()