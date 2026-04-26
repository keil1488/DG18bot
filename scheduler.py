import time
import logging
from apscheduler.triggers.interval import IntervalTrigger
from db import get_active_goals_with_deadline, mark_notified, was_notified

logger = logging.getLogger(__name__)

# Пороги уведомлений
REMINDER_THRESHOLDS = [
    ("expired", 0),      # Ровно в момент дедлайна
    ("10m", 10 * 60),    # За 10 минут
    ("1h", 3600),        # За 1 час
    ("1d", 86400),       # За 1 день
]

REMINDER_TEXTS = {
    "expired": "⌛ **ВРЕМЯ ИСТЕКЛО!**",
    "10m": "⏰ До дедлайна осталось *10 минут*!",
    "1h": "🔥 До дедлайна *1 час*. Поднажми!",
    "1d": "📅 До дедлайна *1 день*.",
}

def schedule_deadline_checker(scheduler, bot):
    scheduler.add_job(
        check_deadlines,
        IntervalTrigger(seconds=30), # Проверяем каждые 30 сек
        args=[bot],
        id="deadline_checker",
        replace_existing=True
    )

async def check_deadlines(bot):
    now_ms = int(time.time() * 1000)
    goals = await get_active_goals_with_deadline()

    for goal in goals:
        goal_id = goal["id"]
        user_id = goal["user_id"]
        text = goal["text"]
        deadline = goal["deadline"] # в мс

        sec_left = (deadline - now_ms) / 1000

        for label, threshold_sec in REMINDER_THRESHOLDS:
            # Если время до дедлайна меньше порога (но не больше чем на 1 минуту меньше)
            if sec_left <= threshold_sec and sec_left > (threshold_sec - 60):
                if not await was_notified(goal_id, label):
                    prefix = REMINDER_TEXTS.get(label, "⏳ Напоминание")
                    msg = f"{prefix}\n\n🎯 Цель: *{text}*"
                    try:
                        await bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
                        await mark_notified(goal_id, label)
                    except Exception as e:
                        logger.error(f"Send error to {user_id}: {e}")