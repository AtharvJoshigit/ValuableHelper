import os
import html
import logging
import asyncio
import time
import json
from typing import Dict, List, Optional
from agents import main_agent
from infrastructure.singleton import Singleton
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from engine.core.types import StreamChunk, ToolResult
from agents.base_agent import BaseAgent
from services.plan_director import PlanDirector

# Imports for authorization
from functools import wraps
from services.telegram_bot.config import AUTHORIZED_USERS

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global State (In-Memory)
# In production, use Redis or a database
user_sessions: Dict[int, object] = {} # ChatID -> Agent Instance
user_locks: Dict[int, asyncio.Lock] = {} # ChatID -> Lock
last_active_chat_id: Optional[int] = None
_application = None
_task_store = Singleton.get_task_store()

# Authorization decorator
def authorized_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            logger.warning(f"Unauthorized access attempt by user_id={user_id}")
            await update.message.reply_text("🚫 You are not authorized to use this bot.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def get_or_create_agent(chat_id: int):
    if chat_id not in user_sessions:
        # Initialize a new agent for this user
        logger.info(f"Creating new agent for chat_id={chat_id}")
        user_sessions[chat_id] = main_agent.create_main_agent()
    return user_sessions[chat_id]

async def send_telegram_notification(chat_id: int, message: str):
    """
    Sends a notification message to the specified Telegram chat.
    """
    if _application is None:
        logger.warning("Telegram application is not initialized. Cannot send notification.")
        return

    try:
        await _application.bot.send_message(
            chat_id=chat_id, 
            text=message, 
            parse_mode=constants.ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to send Telegram notification to {chat_id}: {e}")

def format_tool_log(tool_name: str, tool_args: str | dict, tool_result: str | None) -> str:
    """
    Returns a clean, summarized log line for a completed tool call.
    Escapes dynamic content to prevent HTML errors.
    """
    # 1. Parse arguments into a dict if possible
    args_dict = {}
    if isinstance(tool_args, dict):
        args_dict = tool_args
    elif isinstance(tool_args, str):
        try:
            args_dict = json.loads(tool_args)
        except:
            pass

    # 2. Determine Summary based on Tool Name, escaping dynamic parts
    summary = ""
    
    if tool_name == "read_file":
        path = html.escape(args_dict.get("path") or args_dict.get("file_path") or "?")
        summary = f"📄 <b>Read:</b> <code>{path}</code>"
    
    elif tool_name == "list_directory":
        path = html.escape(args_dict.get("path") or ".")
        summary = f"📂 <b>Ls:</b> <code>{path}</code>"

    elif tool_name == "create_file":
        path = html.escape(args_dict.get("file_path") or args_dict.get("path") or "?")
        summary = f"📝 <b>Create:</b> <code>{path}</code>"

    elif tool_name == "str_replace":
        path = html.escape(args_dict.get("path") or "?")
        summary = f"✏️ <b>Edit:</b> <code>{path}</code>"

    elif tool_name == "run_command":
        cmd = html.escape(args_dict.get("command") or "?")
        summary = f"💻 <b>Run:</b> <code>{cmd}</code>"
        
    else:
        # Default fallback, escape the tool name itself
        safe_tool_name = html.escape(tool_name)
        summary = f"🔧 <b>{safe_tool_name}</b>"

    return summary

def format_response(chunks: List[StreamChunk], status_override: str = None) -> str:
    """
    Reconstructs the message from the stream of chunks, escaping content for HTML.
    Structure:
    1. Status Header (Thinking / Running / Done)
    2. Activity Log (Collapsible/List of completed tools)
    3. Main Content
    """
    tool_map = {} # ID -> {'name': str, 'args': any, 'result': str|None, 'error': str|None}
    final_content = []
    
    # Process chunks to build state
    for chunk in chunks:
        if chunk.tool_call:
            tool_map[chunk.tool_call.id] = {
                'name': chunk.tool_call.name,
                'args': chunk.tool_call.arguments,
                'result': None,
                'error': None
            }
        
        if chunk.tool_result:
            t_id = chunk.tool_result.tool_call_id
            if t_id in tool_map:
                tool_map[t_id]['result'] = str(chunk.tool_result.result)
                tool_map[t_id]['error'] = chunk.tool_result.error

        if chunk.content:
            final_content.append(chunk.content)

    # --- 1. Determine Status Header ---
    if status_override:
        header = status_override
    else:
        # Infer status
        active_tools = [t['name'] for t in tool_map.values() if t['result'] is None and t['error'] is None]
        if active_tools:
            # Show the first active tool, ensuring its name is safe for HTML
            safe_tool_name = html.escape(active_tools[0])
            header = f"⚙️ <b>Running:</b> {safe_tool_name}"
        else:
            header = "🤖 <b>Thinking...</b>"

    # --- 2. Build Activity Log (Completed Tools Only) ---
    log_lines = []
    for t_id, data in tool_map.items():
        if data['result'] is not None or data['error'] is not None:
            # Tool is done
            icon = "✅" if not data['error'] else "❌"
            line = format_tool_log(data['name'], data['args'], data['result'])
            log_lines.append(f"{icon} {line}")
            
            # Optional: Add error detail if failed
            if data['error']:
                # Escape the error message before formatting
                err_short = html.escape(str(data['error'])[:50])
                log_lines.append(f"   <i>Error: {err_short}...</i>")

    log_section = ""
    if log_lines:
        log_section = "\n".join(log_lines) + "\n\n"

    # --- 3. Main Content ---
    # Escape the raw agent content before combining with other HTML tags
    text_body = html.escape("".join(final_content).strip())
    if not text_body and not log_lines:
        text_body = "..."
    # If there is no agent text but there is a log, don't show the ellipsis
    elif not text_body and log_lines:
        text_body = ""

    return f"{header}\n\n{log_section}{text_body}"

async def run_agent_loop(chat_id: int, user_input: str, context: ContextTypes.DEFAULT_TYPE, status_msg=None, retain_history: bool = False):
    """
    Common logic to run the agent stream, update Telegram UI, and handle HITL.
    """
    if chat_id not in user_locks:
        user_locks[chat_id] = asyncio.Lock()
        
    async with user_locks[chat_id]:
        agent = get_or_create_agent(chat_id)
        
        # Initialize or retrieve chunk history to persist logs across pauses
        if not retain_history:
             context.user_data['chunks'] = []
        
        received_chunks = context.user_data.setdefault('chunks', [])

        # Send initial status if needed
        if status_msg is None:
             status_msg = await context.bot.send_message(
                 chat_id=chat_id, 
                 text="🤖 <b>Thinking...</b>", 
                 parse_mode=constants.ParseMode.HTML
             )
        
        last_update_time = 0
        
        try:
            async for chunk in agent.stream(user_input):
                received_chunks.append(chunk)
                
                # Activity Logging to Console
                if chunk.tool_call:
                    logger.info(f"🛠️ Tool Call: {chunk.tool_call.name}")
                if chunk.tool_result:
                    logger.info(f"✅ Tool Result: {chunk.tool_result.name}")
                
                # Check for Permission Request (HITL)
                if chunk.permission_request:
                    tool_names = ", ".join([t.name for t in chunk.permission_request])
                    current_view = format_response(received_chunks, status_override="⚠️ <b>Permission Required</b>")
                    
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Approve", callback_data="approve"),
                            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await status_msg.edit_text(
                        f"{current_view}\n\n<b>Tools waiting:</b> {html.escape(tool_names)}",
                        parse_mode=constants.ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                    return # Stop processing, wait for button click

                # Smart Update: Throttle edits
                current_time = time.time()
                if current_time - last_update_time > 1.0:
                    formatted_text = format_response(received_chunks)
                    if formatted_text and formatted_text != status_msg.text:
                        try:
                            await status_msg.edit_text(
                                formatted_text, 
                                parse_mode=constants.ParseMode.HTML
                            )
                            last_update_time = current_time
                        except Exception as e:
                            logger.warning(f"Telegram edit failed (minor): {e}")

            # Final update
            final_text = format_response(received_chunks, status_override="✅ <b>Done</b>")
            await status_msg.edit_text(final_text, parse_mode=constants.ParseMode.HTML)

        except Exception as e:
            logger.error(f"Error in stream: {e}", exc_info=True)
            
            # Categorize error type
            error_msg = "❌ <b>Oops, hit a snag!</b>\n\n"
            if "timeout" in str(e).lower():
                error_msg += "Took too long. Try breaking this into smaller steps?"
            elif "permission" in str(e).lower():
                error_msg += "Permission issue. Check file/folder access?"
            elif "not found" in str(e).lower():
                error_msg += "Couldn't find that file/resource."
            else:
                error_msg += f"Error: {html.escape(str(e)[:100])}"
            
            error_msg += "\n\n💡 Try rephrasing or use /reset if things are stuck."
            
            await status_msg.edit_text(error_msg, parse_mode=constants.ParseMode.HTML)


@authorized_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! I'm your engineering partner. Let's get to work.")

@authorized_only
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_sessions:
        del user_sessions[chat_id]
    
    # Also clear history
    if 'chunks' in context.user_data:
        del context.user_data['chunks']
        
    await update.message.reply_text("Memory wiped. Starting fresh.")

@authorized_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_active_chat_id
    chat_id = update.effective_chat.id
    last_active_chat_id = chat_id
    
    text = update.message.text
    
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
    
    # Delegate to agent loop, resetting history for new message
    await run_agent_loop(chat_id, text, context, retain_history=False)

@authorized_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows session statistics."""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_sessions:
        await update.message.reply_text("No active session. Send me a message to start!", parse_mode=constants.ParseMode.HTML)
        return
    
    agent = get_or_create_agent(chat_id)
    
    # Get stats from agent
    stats_text = f"""
📊 <b>Session Stats</b>

💬 Messages: {agent.message_count if hasattr(agent, 'message_count') else 'N/A'}
🛠️ Tools used: {agent.tool_call_count if hasattr(agent, 'tool_call_count') else 'N/A'}
✅ Tasks completed: {agent.completed_tasks if hasattr(agent, 'completed_tasks') else 'N/A'}
⏱️ Session started: {agent.session_start if hasattr(agent, 'session_start') else 'N/A'}
"""
    
    await update.message.reply_text(stats_text, parse_mode=constants.ParseMode.HTML)


@authorized_only
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks for approvals."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = update.effective_chat.id
    
    if data.startswith("approve_"):
        # Legacy Chat Approval
        if ":" not in data:
            agent = get_or_create_agent(chat_id)
            await query.edit_message_text(
                text="✅ <b>Approved!</b> Continuing execution...",
                parse_mode=constants.ParseMode.HTML
            )
            return

        # Task Approval
        # Format: approve_task:{task_id}
        action, task_id = data.split(":")
        
        if action == "approve_task":
            # Get current context to preserve other fields if needed, 
            # but update_task merges top-level fields. 
            # We need to merge 'context' dict ideally, but TaskStore.update_task replaces it?
            # Let's check TaskStore. It sets the field. 
            # So we should probably read, update dict, write.
            # For now, simplistic approach:
            
            task = _task_store.get_task(task_id)
            if task:
                new_context = task.context or {}
                new_context["approved_tools"] = ["all"]
                
                await _task_store.update_task(task_id, {
                    "status": "todo",
                    "context": new_context
                })
                await query.edit_message_text(
                    text=f"✅ <b>Approved Task</b>\nID: {task_id}\nQueued for execution.",
                    parse_mode=constants.ParseMode.HTML
                )
            else:
                await query.edit_message_text("❌ Task not found.")

    elif data.startswith("deny_task:"):
        _, task_id = data.split(":")
        await _task_store.update_task(task_id, {
            "status": "blocked",
            "context": {"blocked_reason": "User denied permission via Telegram"}
        })
        await query.edit_message_text(
            text=f"🚫 <b>Denied Task</b>\nID: {task_id}\nMarked as blocked.",
            parse_mode=constants.ParseMode.HTML
        )
        
    elif data.startswith("cancel_"):
        # Legacy Chat Cancel
        agent = get_or_create_agent(chat_id)
        await query.edit_message_text(
            text="❌ <b>Cancelled</b>",
            parse_mode=constants.ParseMode.HTML
        )


@authorized_only
async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows current task status in a clean format."""
    chat_id = update.effective_chat.id
    
    # Using global task store
    try:
        pending_tasks = _task_store.list_tasks(status=["todo", "in_progress", "blocked", "waiting_approval"])
        
        if not pending_tasks:
            await update.message.reply_text("✅ All clear! No pending tasks.", parse_mode=constants.ParseMode.HTML)
            return
        
        response = "📋 <b>Current Tasks</b>\n\n"
        for task in pending_tasks:
            emoji = {
                "todo": "⏳",
                "in_progress": "🔄",
                "blocked": "⚠️",
                "waiting_approval": "👀"
            }.get(task.status, "•")
            
            response += f"{emoji} <b>{html.escape(task.title)}</b>\n"
            response += f"   Status: {task.status}\n"
            if task.assigned_to:
                response += f"   Agent: {task.assigned_to}\n"
            response += "\n"
        
        await update.message.reply_text(response, parse_mode=constants.ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        await update.message.reply_text("❌ Couldn't fetch tasks right now.", parse_mode=constants.ParseMode.HTML)


def run():
    global _application
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment.")
        return

    app = ApplicationBuilder().token(token).build()
    _application = app
    
    from src.services.notification_service import notification_service
    notification_service.set_application(app)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    run()
