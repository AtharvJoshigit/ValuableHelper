# main.py (UPDATED with database initialization)

print("MAIN FILE LOADED")
import argparse
print("AFTER IMPORT 1")
import sys
print("AFTER IMPORT 2")
import os
import logging
import asyncio
print("AFTER IMPORT 3")
import signal
from typing import Optional
from pathlib import Path

from app.app_context import AppContext, set_app_context
from services.observability_service import ObservabilityService
import uvicorn
from dotenv import load_dotenv

# Database imports
print("AFTER IMPORT 4")
from database.db_manager import DatabaseManager
print("AFTER IMPORT 5")
from database.base import DatabaseType
print("AFTER IMPORT 5.1")
from engine.core.agent_factory import set_global_database
print("AFTER IMPORT 5.2")
from engine.core.agent_instance_manager import get_agent_manager
print("AFTER IMPORT 5.3")
RUN_BOT_ONLY = "--bot" in sys.argv

# Ensure 'src' is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
print("AFTER IMPORT 6")
from services.telegram_bot.bot import TelegramBotService
print("AFTER IMPORT 7")
from services.plan_director import PlanDirector
from agents.main_agent import MainAgent
from engine.core.provide import auto_register_providers
# from engine.registry.tool_manager import ToolManager
from server import app  # Import FastAPI app


class AFCToDebugFilter(logging.Filter):
    def filter(self, record):
        if "AFC" in record.getMessage():
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
        return True

# --- Setup Logging ---
LOG_FILE = "valh.log"
print(LOG_FILE)
def setup_logging():
    """Configure logging for the application"""
    logging.root.handlers.clear()
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    for noisy in (
        "httpx", "httpcore", "telegram", "httpcore.http11", "aiosqlite"
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
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/agent_memory.db",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable database-backed memory (use in-memory only)",
    )
    return parser.parse_args()


class ApplicationManager:
    """Manages the lifecycle of all application components"""
    
    def __init__(self, bot_only: bool = False, db_path: str = "data/agent_memory.db", enable_memory: bool = True):
        self.logger = logging.getLogger("ValuableHelper")
        self.bot_only = bot_only
        self.db_path = db_path
        self.enable_memory = enable_memory
        
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
        # self.tool_manager = ToolManager()
        self.database = None
        
    async def initialize(self):
        """Initialize all application components"""
        try:
            self.logger.info("🚀 Initializing Application...")
            
            # 1. Initialize Database (NEW)
            if self.enable_memory:
                await self._initialize_database()
            else:
                self.logger.warning("⚠️ Database-backed memory disabled, using in-memory only")
            
            # 2. Initialize Infrastructure
            self.app_context = AppContext()
            set_app_context(self.app_context)
            auto_register_providers()
            
            # 3. Sync Tools to Registry/DB
            self.logger.info("🛠️ Syncing Tools to Registry...")
            try:
                # self.tool_manager.sync_tools()
                self.logger.info("✅ Tools Synced")
            except Exception as e:
                self.logger.error(f"❌ Tool Sync Failed: {e}", exc_info=True)

            self.logger.info("✅ Infrastructure initialized")
            
            # 4. Initialize Plan Director & Observability
            # self.plan_director = PlanDirector()
            # self.plan_director.ensure_started()
            if not self.bot_only:
                self.obs_service = ObservabilityService()
                self.obs_service.start()
            self.logger.info("✅ Plan Director & Observability initialized")
            
            # 5. Configuration
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            if not token:
                raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
            
            # 6. Instantiate Services
            self.bot_service = TelegramBotService(token)

            config = {
                'top_k': 7,
                'top_p': 0.5,
                'max_tokens': 3000,
                'temperature': 1.0,
                "model_id": "gemini-3-pro-preview",
                "provider": "google",
                "max_steps": 15,
                "additional_params": {
                    "include_thoughts": False,
                },
                # Memory settings (NEW)
                "enable_memory_summarization": self.enable_memory,
                "agent_name": "ValH Main Agent",
                "memory_recent_k": 10,  # More context for main agent
                "memory_summarization_threshold": 10,
                "session_timeout_hours": 48,  # 2 days for main conversations
            }

            self.main_agent = MainAgent(self.bot_service, config)
            self.logger.info("✅ Services instantiated")
            
            # 7. Setup FastAPI Server (Optional)
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
    
    async def _initialize_database(self):
        """Initialize database for agent memory"""
        try:
            self.logger.info(f"📊 Initializing database: {self.db_path}")
            
            # Ensure data directory exists
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize database manager
            self.database = await DatabaseManager.initialize(
                db_type=DatabaseType.SQLITE,
                db_path=self.db_path
            )
            
            # Set global database for agent factory
            set_global_database(self.database)
            
            # Set database in agent manager
            agent_manager = get_agent_manager()
            agent_manager.set_database(self.database)
            
            self.logger.info("✅ Database initialized successfully")
            
            # Log database info
            db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            self.logger.info(f"📊 Database size: {db_size / 1024:.2f} KB")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize database: {e}", exc_info=True)
            self.logger.warning("⚠️ Continuing without database-backed memory")
            self.enable_memory = False
    
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
                if self.enable_memory:
                    self.logger.info("💾 Database-backed memory: ENABLED")
                    self.logger.info(f"📁 Database location: {self.db_path}")
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
        
        # 1. Clear tool RAG
        try:
            # self.tool_manager.delete_collection()
            self.logger.info("✅ Tool collection cleared")
        except Exception as e:
            self.logger.error(f"Error clearing tool collection: {e}")
        
        # 2. Stop FastAPI Server
        if self.server and not self.bot_only:
            self.logger.info("Stopping FastAPI server...")
            self.server.should_exit = True
            if self.server_task and not self.server_task.done():
                shutdown_tasks.append(self._cancel_task(self.server_task, "FastAPI server"))
        
        # 3. Stop Telegram Bot
        if self.bot_service:
            self.logger.info("Stopping Telegram bot...")
            shutdown_tasks.append(self._safe_shutdown(self.bot_service.stop(), "Telegram bot"))
            # if self.bot_task and not self.bot_task.done():
            #     shutdown_tasks.append(self._cancel_task(self.bot_task, "Telegram bot task"))
        
        # 4. Stop Main Agent
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
        
        # 5. Close database connection (NEW)
        if self.database:
            self.logger.info("Closing database connection...")
            try:
                await DatabaseManager.close()
                self.logger.info("✅ Database closed")
            except Exception as e:
                self.logger.error(f"Error closing database: {e}")
        
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


async def main_async(bot_only: bool, db_path: str, enable_memory: bool):
    """
    Async entry point for the application with proper signal handling
    """
    logger = logging.getLogger("ValuableHelper")
    app_manager = ApplicationManager(
        bot_only=bot_only,
        db_path=db_path,
        enable_memory=enable_memory
    )
    
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
        logger.info(f"Mode: {'Bot Only' if args.bot else 'Full Stack'}")
        logger.info(f"Database: {args.db_path}")
        logger.info(f"Memory: {'Enabled' if not args.no_memory else 'Disabled'}")
        logger.info("=" * 60)
        
        # Run the async application
        asyncio.run(main_async(
            bot_only=args.bot,
            db_path=args.db_path,
            enable_memory=not args.no_memory
        ))
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.critical(f"Application failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Application terminated")


if __name__ == "__main__":
    main()