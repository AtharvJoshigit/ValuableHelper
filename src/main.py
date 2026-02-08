import sys
import os
import logging
from dotenv import load_dotenv

# Ensure 'src' is in the python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Now we can import from src
from services.telegram_bot.bot import run as run_bot

logging.basicConfig(level=logging.INFO)

def main():
    load_dotenv(override=True)
    run_bot()

if __name__ == "__main__":
    main()