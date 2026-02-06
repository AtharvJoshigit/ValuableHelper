import logging
from dotenv import load_dotenv
from services.telegram_bot.bot import run as run_bot

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    load_dotenv(override=True)
    
    # Run the Telegram Bot
    # This is now the primary entry point for the service
    run_bot()

if __name__ == "__main__":
    main()