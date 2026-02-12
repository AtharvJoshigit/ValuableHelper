import sys
import os
import logging
from dotenv import load_dotenv

# Ensure 'src' is in the python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Global Logging Configuration
LOG_FILE = "valh.log"

def setup_logging():
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # File Handler (Writing to Disk)
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler (Visual Output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info(f"🦾 Logging initialized. Writing to {LOG_FILE}")

# Now we can import from src
from services.telegram_bot.bot import run as run_bot

def main():
    load_dotenv(override=True)
    setup_logging()
    run_bot()

if __name__ == "__main__":
    main()
