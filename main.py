
import os
from dotenv import load_dotenv

from tele_bot import bot

if __name__ == '__main__':
    load_dotenv(override=True)
    bot.run()
