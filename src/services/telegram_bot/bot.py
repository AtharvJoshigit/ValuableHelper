import os
import logging
import asyncio
import time
import json
from typing import Dict, List, Optional
from agents import main_agent
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from engine.core.types import StreamChunk, ToolResult
from agents.base_agent import BaseAgent
from services.plan_director import PlanDirector

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
    """
    # 1. Parse arguments into a dict if possible
    args_dict = {}
    if isinstance(tool_args, dict):
        args_dict = tool_args
    elif isinstance(tool_args, str):
        try:
            args_dict = json.loads(tool_args)
        except:
            pass # Keep empty if parsing fails, or handle raw string

    # 2. Determine Summary based on Tool Name
    summary = ""
    
    if tool_name == "read_file":
        path = args_dict.get("path") or args_dict.get("file_path") or "?"
        summary = f"📄 <b>Read:</b> <code>{path}</code>"
    
    elif tool_name == "list_directory":
        path = args_dict.get("path") or "."
        summary = f"📂 <b>Ls:</b> <code>{path}</code>"

    elif tool_name == "create_file":
        path = args_dict.get("file_path") or args_dict.get("path") or "?"
        summary = f"📝 <b>Create:</b> <code>{path}</code>"

    elif tool_name == "str_replace":
        path = args_dict.get("path") or "?"
        summary = f"✏️ <b>Edit:</b> <code>{path}</code>"

    elif tool_name == "run_command":
        cmd = args_dict.get("command") or "?"
        summary = f"💻 <b>Run:</b> <code>{cmd}</code>"
        
    else:
        # Default fallback
        summary = f"🔧 <b>{tool_name}</b>"

    return summary

def format_response(chunks: List[StreamChunk], status_override: str = None) -> str:
    """
    Reconstructs the message from the stream of chunks.
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
            # Show the first active tool
            header = f"⚙️ <b>Running:</b> {active_tools[0]}"
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
                err_short = str(data['error'])[:50]
                log_lines.append(f"   <i>Error: {err_short}...</i>")

    log_section = ""
    if log_lines:
        log_section = "\n".join(log_lines) + "\n\n"

    # --- 3. Main Content ---
    text_body = "".join(final_content).strip()
    if not text_body and not log_lines:
        text_body = "..."

    return f"{header}\n\n{log_section}{text_body}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! I'm your engineering partner. Let's get to work.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_sessions:
        del user_sessions[chat_id]
    await update.message.reply_text("Memory wiped. Starting fresh.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_active_chat_id
    chat_id = update.effective_chat.id
    last_active_chat_id = chat_id
    
    text = update.message.text
    
    if chat_id not in user_locks:
        user_locks[chat_id] = asyncio.Lock()
        
    async with user_locks[chat_id]:
        agent = get_or_create_agent(chat_id)
        
        # Initial status message
        status_msg = await update.message.reply_text("🤖 <b>Thinking...</b>", parse_mode=constants.ParseMode.HTML)
        
        received_chunks = []
        last_update_time = 0
        
        try:
            async for chunk in agent.stream(text):
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
                    await status_msg.edit_text(
                        f"{current_view}\n\nReply 'yes' to proceed.",
                        parse_mode=constants.ParseMode.HTML
                    )
                    return # Stop processing, wait for user reply

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
            await status_msg.edit_text(f"❌ <b>Critical Error:</b> {str(e)}", parse_mode=constants.ParseMode.HTML)

def run():
    global _application
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment.")
        return

    app = ApplicationBuilder().token(token).build()
    _application = app
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    run()
