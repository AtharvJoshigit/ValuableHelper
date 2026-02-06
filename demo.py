import asyncio
import logging
from dotenv import load_dotenv

import me
from src import me

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    # 1. Load Environment Variables (Ensure GOOGLE_API_KEY is set)
    load_dotenv()
    
    await me.chat()

if __name__ == "__main__":
    asyncio.run(main())
