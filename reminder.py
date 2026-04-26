from datetime import date
import aiosqlite

async def send_reminder_if_no_answer(bot, user_id: int):
    today = date.today().isoformat()
    async with aiosqlite.connect("bot.db") as db:
        # ИСПРАВЛЕНО: Таблица называется daily_tasks, а не morning_tasks
        cursor = await db.execute(
            "SELECT id FROM daily_tasks WHERE user_id=? AND date=?",
            (user_id, today)
        )
        row = await cursor.fetchone()

    if not row:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "Привет! Ты ещё не записал задачу на сегодня.\n"
                "Напиши одним предложением — что сделает день успешным?"
            )
        )