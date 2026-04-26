from dotenv import load_dotenv
load_dotenv()

import os
import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db import init_db, get_all_users
from handlers import (
    start, set_language, set_time,
    handle_morning_task, handle_evening_checkin,
    help_command, restart_command, menu_button_handler, cancel,
    CHOOSING_LANG, SETTING_TIME, WAITING_MORNING_TASK, WAITING_EVENING
)
from scheduler import schedule_user

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = "8743923345:AAFdorSDswkdEAGz9Wp0Q6-3hZaAtDizjcY"

MENU_PATTERN = (
    "^(📝 Задача на сегодня|✅ Вечерний чекин|ℹ️ Помощь|⚙️ Настройки"
    "|📝 Today's task|✅ Evening check-in|ℹ️ Help|⚙️ Settings)$"
)


async def on_startup(app):
    await init_db()
    scheduler = AsyncIOScheduler()

    users = await get_all_users()
    for user in users:
        schedule_user(scheduler, app.bot, user)

    scheduler.start()
    app.scheduler = scheduler


def main():
    if not TOKEN:
        raise RuntimeError("TOKEN environment variable is not set!")

    app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(MENU_PATTERN), menu_button_handler),
        ],
        states={
            CHOOSING_LANG: [
                MessageHandler(filters.Regex("^(🇷🇺 Русский|🇬🇧 English)$"), set_language)
            ],
            SETTING_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_time)
            ],
            WAITING_MORNING_TASK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_morning_task)
            ],
            WAITING_EVENING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_evening_checkin)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("restart", restart_command),
            CommandHandler("help", help_command),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("restart", restart_command))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
