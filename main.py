from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import logging
from aiohttp import web
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
from scheduler import schedule_user, schedule_deadline_checker
from api import create_app

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("TOKEN", "8743923345:AAFdorSDswkdEAGz9Wp0Q6-3hZaAtDizjcY")

# Порт для HTTP API (веб-приложение отправляет сюда цели)
API_PORT = int(os.getenv("API_PORT", "8080"))

MENU_PATTERN = (
    "^(📝 Задача на сегодня|✅ Вечерний чекин|ℹ️ Помощь|⚙️ Настройки"
    "|📝 Today's task|✅ Evening check-in|ℹ️ Help|⚙️ Settings)$"
)


async def on_startup(app):
    await init_db()

    scheduler = AsyncIOScheduler()

    # Планируем утро/день/вечер для всех пользователей
    users = await get_all_users()
    for user in users:
        schedule_user(scheduler, app.bot, user)

    # Запускаем проверку дедлайнов каждую минуту
    schedule_deadline_checker(scheduler, app.bot)

    scheduler.start()
    app.scheduler = scheduler


def main():
    if not TOKEN:
        raise RuntimeError("TOKEN is not set!")

    # ── Telegram bot ──────────────────────────────────────────────────────────
    tg_app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

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

    tg_app.add_handler(conv)
    tg_app.add_handler(CommandHandler("help", help_command))
    tg_app.add_handler(CommandHandler("restart", restart_command))

    # ── HTTP API (aiohttp) ────────────────────────────────────────────────────
    api_app = create_app()

    async def run_all():
        # Запускаем aiohttp-сервер
        runner = web.AppRunner(api_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", API_PORT)
        await site.start()
        logging.info(f"API server started on port {API_PORT}")

        # Запускаем бота (polling)
        async with tg_app:
            await tg_app.initialize()
            await tg_app.start()
            await tg_app.updater.start_polling()
            logging.info("Bot is running...")

            # Держим процесс живым
            try:
                await asyncio.Event().wait()
            finally:
                await tg_app.updater.stop()
                await tg_app.stop()
                await runner.cleanup()

    asyncio.run(run_all())


if __name__ == "__main__":
    main()
я