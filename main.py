import sys
import os
import logging
import argparse
import asyncio
from dotenv import load_dotenv

# Add the 'src' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Now imports from 'src' will work
from services.telegram_bot.bot import run as run_bot
from console_chat import run_console_chat

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    """
    Main entry point for the application.
    Parses command-line arguments to decide whether to run the
    Telegram bot or the console-based chat.
    """
    load_dotenv(override=True) # Load environment variables from .env file

    parser = argparse.ArgumentParser(
        description="Run the ValuableHelper assistant in different modes."
    )
    parser.add_argument(
        '--console',
        action='store_true',
        help="Run in interactive console mode."
    )
    # The default behavior will be the telegram bot
    args = parser.parse_args()

    if args.console:
        logging.info("Starting application in console mode...")
        try:
            asyncio.run(run_console_chat())
        except KeyboardInterrupt:
            logging.info("Console chat terminated by user.")
    else:
        logging.info("Starting application in Telegram bot mode...")
        run_bot()

if __name__ == "__main__":
    main()