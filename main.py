import argparse
import sys
import os
import logging
import asyncio
import signal
from typing import Optional
from app.app_context import AppContext, set_app_context
from services.observability_service import ObservabilityService
import uvicorn
from dotenv import load_dotenv


RUN_BOT_ONLY = "--bot" in sys.argv

# Ensure 'src' is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from infrastructure.command_bus import CommandBus
from services.telegram_bot.bot import TelegramBotService
from services.plan_director import PlanDirector
from agents.main_agent import MainAgent
from engine.core.provide import auto_register_providers
from server import app  # Import FastAPI app



class AFCToDebugFilter(logging.Filter):
    def filter(self, record):
        if "AFC" in record.getMessage():
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
        return True

# --- Setup Logging ---
LOG_FILE = "valh.log"

def setup_logging():
    """Configure logging for the application"""
    logging.root.handlers.clear()
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    for noisy in (
        "httpx", "httpcore", "telegram", "httpcore.http11"
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(AFCToDebugFilter())
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(AFCToDebugFilter())
    logger.addHandler(console_handler)

    return logger

# --- CLI ARGUMENTS ---
def parse_args():
    parser = argparse.ArgumentParser(description="ValH Application Runner")
    parser.add_argument(
        "--bot",
        action="store_true",
        help="Run in bot-only mode (disable UI services)",
    )
    return parser.parse_args()


class ApplicationManager:
    """Manages the lifecycle of all application components"""
    
    def __init__(self, bot_only: bool = False):
        self.logger = logging.getLogger("ValuableHelper")
        self.bot_only = bot_only
        self.app_context: Optional[AppContext] = None
        self.plan_director: Optional[PlanDirector] = None
        self.obs_service: Optional[ObservabilityService] = None
        self.bot_service: Optional[TelegramBotService] = None
        self.main_agent: Optional[MainAgent] = None
        self.shutdown_event = asyncio.Event()
        self.agent_task: Optional[asyncio.Task] = None
        self.bot_task: Optional[asyncio.Task] = None
        self.server: Optional[uvicorn.Server] = None
        self.server_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """Initialize all application components"""
        try:
            self.logger.info("🚀 Initializing Application...")
            
            # 1. Initialize Infrastructure
            self.app_context = AppContext()
            set_app_context(self.app_context)
            auto_register_providers()
            self.logger.info("✅ Infrastructure initialized")
            
            # 2. Initialize Plan Director & Observability
            self.plan_director = PlanDirector()
            self.plan_director.ensure_started()
            if not self.bot_only:
                self.obs_service = ObservabilityService()
                self.obs_service.start()
            self.logger.info("✅ Plan Director & Observability initialized")
            
            # 3. Configuration
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            if not token:
                raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
            
            # 4. Instantiate Services
            self.bot_service = TelegramBotService(token)
            self.main_agent = MainAgent(self.bot_service)
            self.logger.info("✅ Services instantiated")
            
            # 5. Setup FastAPI Server (Optional - commented out by default)
            if not self.bot_only:
                config = uvicorn.Config(
                    app,
                    host="0.0.0.0",
                    port=8000,
                    log_level="error",
                    access_log=False,
                )
                self.server = uvicorn.Server(config)
                self.logger.info("✅ FastAPI server configured")
            
            self.logger.info("✅ Application initialization complete")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize application: {e}", exc_info=True)
            raise
    
    async def start(self):
        """Start all application components"""
        try:
            self.logger.info("🔥 Starting Application Components...")
            
            # 1. Start Main Agent's event loop
            self.agent_task = asyncio.create_task(
                self.main_agent.run(),
                name="main_agent"
            )
            self.logger.info("✅ Main Agent started")
            
            # 2. Start FastAPI Server (Optional)
            if self.server and not self.bot_only:
                self.server_task = asyncio.create_task(
                    self.server.serve(), name="fastapi_server"
                )
                self.logger.info("🎭 UI running at http://localhost:8000")
            
            # 3. Start Telegram Bot (runs in its own task)
            self.bot_task = asyncio.create_task(
                self.bot_service.start(),
                name="telegram_bot"
            )
            self.logger.info("🤖 Telegram Bot starting...")
            
            # Give the bot a moment to initialize
            await asyncio.sleep(2)
            
            if self.bot_service.is_running():
                self.logger.info("✅ All components started successfully")
            else:
                raise RuntimeError("Telegram bot failed to start")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to start application: {e}", exc_info=True)
            raise
    
    async def wait_for_shutdown(self):
        """Wait for shutdown signal"""
        try:
            await self.shutdown_event.wait()
        except asyncio.CancelledError:
            self.logger.info("Shutdown event cancelled")
    
    async def shutdown(self):
        """Gracefully shutdown all application components"""
        if self.shutdown_event.is_set():
            return  # Already shutting down
            
        self.shutdown_event.set()
        self.logger.info("🔻 Initiating graceful shutdown...")
        
        shutdown_tasks = []
        
        # 1. Stop FastAPI Server
        if self.server and not self.bot_only:
            self.logger.info("Stopping FastAPI server...")
            self.server.should_exit = True
            if self.server_task and not self.server_task.done():
                shutdown_tasks.append(self._cancel_task(self.server_task, "FastAPI server"))
        
        # 2. Stop Telegram Bot
        if self.bot_service:
            self.logger.info("Stopping Telegram bot...")
            shutdown_tasks.append(self._safe_shutdown(self.bot_service.stop(), "Telegram bot"))
            if self.bot_task and not self.bot_task.done():
                shutdown_tasks.append(self._cancel_task(self.bot_task, "Telegram bot task"))
        
        # 3. Stop Main Agent
        if self.main_agent:
            self.logger.info("Stopping Main Agent...")
            shutdown_tasks.append(self._safe_shutdown(self.main_agent.stop(), "Main Agent"))
            if self.agent_task and not self.agent_task.done():
                shutdown_tasks.append(self._cancel_task(self.agent_task, "Main Agent task"))
        
        # Wait for all shutdowns to complete with timeout
        if shutdown_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                self.logger.warning("Shutdown timeout exceeded, forcing exit")
        
        self.logger.info("✅ Shutdown complete")
    
    async def _safe_shutdown(self, coro, name: str):
        """Safely execute shutdown coroutine with error handling"""
        try:
            await coro
            self.logger.info(f"✅ {name} stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping {name}: {e}", exc_info=True)
    
    async def _cancel_task(self, task: asyncio.Task, name: str):
        """Cancel a task with proper cleanup"""
        try:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    self.logger.info(f"✅ {name} cancelled")
        except Exception as e:
            self.logger.error(f"Error cancelling {name}: {e}", exc_info=True)


async def main_async(bot_only: bool):
    """
    Async entry point for the application with proper signal handling
    """
    logger = logging.getLogger("ValuableHelper")
    app_manager = ApplicationManager(bot_only=bot_only)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signal.Signals(sig).name}")
        asyncio.create_task(app_manager.shutdown())
    
    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: asyncio.create_task(app_manager.shutdown()))
    
    try:
        # Initialize and start the application
        await app_manager.initialize()
        await app_manager.start()
        
        logger.info("✅ Application is running. Press Ctrl+C to stop.")
        
        # Wait for shutdown signal
        await app_manager.wait_for_shutdown()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await app_manager.shutdown()
    except asyncio.CancelledError:
        logger.info("Main task cancelled")
        await app_manager.shutdown()
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        await app_manager.shutdown()
        raise
    finally:
        # Ensure cleanup even if shutdown wasn't called
        if not app_manager.shutdown_event.is_set():
            await app_manager.shutdown()


def main():
    """Entry point for the application"""
    # Load environment variables
    load_dotenv(override=True)
    args = parse_args()
    # Setup logging
    setup_logging()
    logger = logging.getLogger("ValuableHelper")
    
    # Windows specific event loop policy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        logger.info("=" * 60)
        logger.info("Starting ValH Application")
        logger.info("=" * 60)
        
        # Run the async application
        asyncio.run(main_async(bot_only=args.bot))
        
    except KeyboardInterrupt:
        # Expected exit on Ctrl+C - already handled in main_async
        logger.info("Application stopped by user")
    except Exception as e:
        logger.critical(f"Application failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Application terminated")


if __name__ == "__main__":
    main()