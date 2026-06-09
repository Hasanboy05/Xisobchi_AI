import os
import time
from dotenv import load_dotenv

load_dotenv()

from XisobchiAI import bot

if __name__ == "__main__":
    # 409 Conflict uchun to'g'ri yechim:
    # delete_webhook() — Telegram serverida bu token uchun barcha aktiv
    # polling/webhook sessiyalarni majburiy o'chiradi.
    # sleep(2) — o'chirish Telegram tomonida kuchga kirguncha kutish.
    bot.delete_webhook(drop_pending_updates=True)
    time.sleep(2)

    print("✅ Xisobchi AI v3.0 ishga tushdi")
    print("   Onboarding | Multi-lang | Subscription system")
    bot.infinity_polling(logger_level=20, skip_pending=True)
