import os
import logging
import asyncio
import time
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

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global State (In-Memory)
# In production, use Redis or a database
user_sessions: Dict[int, object] = {} # ChatID -> Agent Instance
user_locks: Dict[int, asyncio.Lock] = {} # ChatID -> Lock

def get_or_create_agent(chat_id: int):
    if chat_id not in user_sessions:
        # Initialize a new agent for this user
        # You can customize the config/prompt here
        logger.info(f"Creating new agent for chat_id={chat_id}")
        user_sessions[chat_id] = main_agent.create_main_agent()
    return user_sessions[chat_id]

def format_response(chunks: List[StreamChunk]) -> str:
    """
    Reconstructs the message from the stream of chunks.
    Separates 'Execution Log' from 'Final Answer'.
    """
    tool_logs = []
    final_content = []
    
    # Track tool status: ID -> (Name, StatusString)
    # We iterate through all chunks to build the current state
    tool_states = {} 
    
    for chunk in chunks:
        # 1. Tool Calls (Started)
        if chunk.tool_call:
            t_id = chunk.tool_call.id
            name = chunk.tool_call.name
            args = str(chunk.tool_call.arguments)
            if len(args) > 50: args = args[:50] + "..."
            tool_states[t_id] = f"⚙️ {name}({args})..."
            
        # 2. Tool Results (Finished)
        if chunk.tool_result:
            t_id = chunk.tool_result.tool_call_id
            name = chunk.tool_result.name
            result = str(chunk.tool_result.result)
            
            status_icon = "✅"
            if chunk.tool_result.error:
                status_icon = "❌"
                result = chunk.tool_result.error
            
            # Truncate long results for display
            if len(result) > 100: result = result[:100] + "..."
            
            # Update the state line
            tool_states[t_id] = f"{status_icon} {name}: {result}"

        # 3. Text Content (The Assistant's reasoning or answer)
        if chunk.content:
            final_content.append(chunk.content)

    # Build the Tool Log Section
    log_section = ""
    if tool_states:
        log_section = "<b>🛠️ Execution Log:</b>\n"
        for _, line in tool_states.items():
            log_section += f"• {line}\n"
        log_section += "----------------------------------\n"

    # Build Final Message
    full_text = log_section + "".join(final_content)
    
    return full_text.strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi!.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_sessions:
        del user_sessions[chat_id]
    await update.message.reply_text("Memory wiped. Starting fresh.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    
    if chat_id not in user_locks:
        user_locks[chat_id] = asyncio.Lock()
        
    async with user_locks[chat_id]:
        agent = get_or_create_agent(chat_id)
        
        # Initial status message
        status_msg = await update.message.reply_text("Thinking...")
        
        received_chunks = []
        last_update_time = 0
        
        try:
            async for chunk in agent.stream(text):
                received_chunks.append(chunk)
                
                # Activity Logging
                if chunk.tool_call:
                    logger.info(f"🛠️ Tool Call: {chunk.tool_call.name} (ID: {chunk.tool_call.id})")
                if chunk.tool_result:
                    logger.info(f"✅ Tool Result: {chunk.tool_result.name} (ID: {chunk.tool_result.tool_call_id})")
                
                # Check for Permission Request (HITL)
                if chunk.permission_request:
                    tool_names = ", ".join([t.name for t in chunk.permission_request])
                    await status_msg.edit_text(
                        format_response(received_chunks) + 
                        f"\n\n⚠️ <b>Permission Required</b>\nI need to run: <code>{tool_names}</code>\n"
                        "Reply 'yes' to proceed, or anything else to deny.",
                        parse_mode=constants.ParseMode.HTML
                    )
                    return # Stop processing, wait for user reply

                # Smart Update: Throttle edits to max 1 per second
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
            final_text = format_response(received_chunks)
            if not final_text: final_text = "✅ Task completed (no output)."
            await status_msg.edit_text(final_text, parse_mode=constants.ParseMode.HTML)

        except Exception as e:
            logger.error(f"Error in stream: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ Critical Error: {str(e)}")

def run():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment.")
        return

    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    run()
