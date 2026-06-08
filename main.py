import os
from dotenv import load_dotenv

load_dotenv()

from XisobchiAI import bot

if __name__ == "__main__":
    bot.infinity_polling(logger_level=20)
