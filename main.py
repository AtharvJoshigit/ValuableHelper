import sys
import os
import logging
import asyncio
import uvicorn
from dotenv import load_dotenv

# Ensure 'src' is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from infrastructure.command_bus import CommandBus
from services.telegram_bot.bot import TelegramBotService
from services.plan_director import PlanDirector
from agents.main_agent import MainAgent
from engine.core.provide import auto_register_providers
from server import app  # Import FastAPI app

# --- Setup Logging ---
LOG_FILE = "valh.log"

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # File Handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

async def main_async():
    """
    Async entry point for the application.
    """
    # Initialize Logger
    logger = logging.getLogger("ValuableHelper")
    
    # 1. Initialize Infrastructure
    bus = CommandBus()
    auto_register_providers()

    # INITIALIZE PLAN DIRECTOR HERE
    plan_director = PlanDirector()
    plan_director.ensure_started() 
    
    # 2. Configuration
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.critical("❌ TELEGRAM_BOT_TOKEN not found in environment variables.")
        return

    # 3. Instantiate Services
    bot_service = TelegramBotService(token, bus)
    main_agent = MainAgent(bot_service, bus)
    
    # 4. Start Background Tasks
    # Start the Main Agent's event loop
    agent_task = asyncio.create_task(main_agent.run())
    
    # Start FastAPI Server (The Face)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="error")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    logger.info("🎭 Interface running at http://localhost:8000")
    
    # 5. Start Telegram Bot (Blocking Polling)
    logger.info("🚀 Starting Telegram Bot Service...")
    
    # Keep track of the stop event to allow graceful exit
    stop_event = asyncio.Event()

    try:
        await bot_service.start() # This initializes the app
        
        # Keep the process alive
        await stop_event.wait()
        
    except asyncio.CancelledError:
        logger.info("Main task cancelled")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}", exc_info=True)
    finally:
        logger.info("🔻 Shutting down...")
        
        # Stop Server
        server.should_exit = True
        await server_task
        
        # Stop Bot
        await bot_service.stop()
        
        # Stop Agent
        await main_agent.stop()
        if not agent_task.done():
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass
        
        logger.info("✅ Shutdown complete.")

def main():
    load_dotenv(override=True)
    setup_logging() # Initialize global logging before anything else
    
    if sys.platform == 'win32':
        # Windows specific event loop policy
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        # Expected exit on Ctrl+C
        pass 

if __name__ == "__main__":
    main()
