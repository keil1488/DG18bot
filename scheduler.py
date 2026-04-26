import time
import logging
from apscheduler.triggers.interval import IntervalTrigger
from db import get_active_goals_with_deadline, was_notified, mark_notified

logger = logging.getLogger(__name__)

async def check_deadlines(bot):
    now_ms = int(time.time() * 1000)
    goals = await get_active_goals_with_deadline()

    for goal in goals:
        g_id, user_id, text, deadline = goal["id"], goal["user_id"], goal["text"], goal["deadline"]
        sec_left = (deadline - now_ms) / 1000

        # 1. Просрочено
        if sec_left <= 0:
            if not await was_notified(g_id, "expired"):
                await bot.send_message(user_id, f"⌛ **ВРЕМЯ ВЫШЛО!**\n\n🎯 Цель: *{text}*", parse_mode="Markdown")
                await mark_notified(g_id, "expired")
            continue

        # 2. 10 минут до конца
        if sec_left <= 600:
            if not await was_notified(g_id, "10m"):
                await bot.send_message(user_id, f"⏰ Осталось 10 минут!\n\n🎯 Цель: *{text}*", parse_mode="Markdown")
                await mark_notified(g_id, "10m")

        # 3. 1 час до конца
        if sec_left <= 3600:
            if not await was_notified(g_id, "1h"):
                await bot.send_message(user_id, f"🔥 Остался 1 час!\n\n🎯 Цель: *{text}*", parse_mode="Markdown")
                await mark_notified(g_id, "1h")

def schedule_deadline_checker(scheduler, bot):
    scheduler.add_job(
        check_deadlines,
        IntervalTrigger(seconds=30),
        args=[bot],
        id="deadline_checker",
        replace_existing=True
    )