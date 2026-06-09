import os
import time
from dotenv import load_dotenv

load_dotenv()

from XisobchiAI import bot

if __name__ == "__main__":
    # 409 Conflict: eski container to'liq o'lishiga vaqt beramiz.
    # Deploy vaqtida ikki instance bir vaqtda ishlashi mumkin — 5 soniya kutish yetarli.
    time.sleep(5)
    bot.infinity_polling(logger_level=20, skip_pending=True)
