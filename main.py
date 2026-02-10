import sys
import os
import logging
import argparse
import asyncio
from agents.main_agent import MainAgent
from dotenv import load_dotenv
from infrastructure.command_bus import CommandBus
from services.telegram_bot import bot

# Add the 'src' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from engine.core.provide import auto_register_providers
from agents.all_agents import ALLFixedAgents
from agents.agent_id import AGENT_ID
from engine.core.agent_instance_manager import get_agent_manager
from services.plan_director import PlanDirector
from services.telegram_bot.bot import TelegramBotService
from console_chat import run_console_chat

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def main_async(args):
    """
    Async entry point for the application.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # 1. Initialize Infrastructure
    bus = CommandBus()
    auto_register_providers()
    # agent_manager = get_agent_manager()
    
    # 2. Register Agents
    # ALLFixedAgents.start()
    
    # 3. Start Plan Director (Background Task)
    PlanDirector().ensure_started()

    bot_gatway = TelegramBotService(token,bus)
    main_agent = MainAgent(bot_gatway, bus)
    asyncio.create_task(main_agent.run())

    # Start telegram bot (blocks)
    await bot_gatway.start()

    await asyncio.Event().wait()


    # 4. Run Interface (Console or Bot)
    # if args.console:
    #     logging.info("🚀 Starting application in Console mode...")
    #     await run_console_chat()
    # else:
    #     logging.info("🚀 Starting application in Telegram Bot mode...")
    #     token = os.getenv("TELEGRAM_BOT_TOKEN")
    #     if not token:
    #         logging.critical("❌ TELEGRAM_BOT_TOKEN not found in environment variables.")
    #         return

    #     bot_service = TelegramBotService(token)
    #     await bot_service.start()
        
    #     logging.info("✅ System is running. Press Ctrl+C to stop.")
        
    #     # Keep the main loop alive to allow background tasks to run
    #     try:
    #         stop_event = asyncio.Event()
    #         await stop_event.wait()
    #     except asyncio.CancelledError:
    #         logging.info("Stopping services...")
    #         await bot_service.stop()

def main():
    load_dotenv(override=True)

    parser = argparse.ArgumentParser(
        description="Run the ValuableHelper assistant."
    )
    parser.add_argument(
        '--console',
        action='store_true',
        help="Run in interactive console mode."
    )
    args = parser.parse_args()

    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logging.info("Application terminated by user.")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    main()