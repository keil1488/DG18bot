import time
import logging
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from db import get_user, get_today_task, get_active_goals_with_deadline, mark_notified, was_notified
from texts import t

logger = logging.getLogger(__name__)

# Метки напоминаний: (название, секунды до дедлайна)
REMINDER_THRESHOLDS = [
    ("1mo",  30 * 24 * 3600),   # 1 месяц
    ("2w",   14 * 24 * 3600),   # 2 недели
    ("1w",    7 * 24 * 3600),   # 1 неделя
    ("3d",    3 * 24 * 3600),   # 3 дня
    ("1d",    1 * 24 * 3600),   # 1 день
    ("1h",    1 * 3600),        # 1 час
    ("30m",   30 * 60),         # 30 минут
    ("10m",   10 * 60),         # 10 минут
]

REMINDER_TEXTS = {
    "1mo":  "📅 До дедлайна *1 месяц*",
    "2w":   "📅 До дедлайна *2 недели*",
    "1w":   "⚠️ До дедлайна *1 неделя*",
    "3d":   "⚠️ До дедлайна *3 дня*",
    "1d":   "🔥 До дедлайна *1 день*",
    "1h":   "🔥 До дедлайна *1 час*",
    "30m":  "💀 До дедлайна *30 минут*",
    "10m":  "💀 До дедлайна *10 минут*",
}


def schedule_user(scheduler, bot, user):
    """Запланировать утренние/дневные/вечерние сообщения для пользователя."""
    user_id = user["user_id"]
    mh = user["morning_hour"]
    mm = user["morning_minute"]
    eh = user["evening_hour"]
    em = user["evening_minute"]

    morning_mins = mh * 60 + mm
    evening_mins = eh * 60 + em
    midday_mins = (morning_mins + evening_mins) // 2
    mid_h = midday_mins // 60
    mid_m = midday_mins % 60

    scheduler.add_job(
        send_morning_question,
        CronTrigger(hour=mh, minute=mm),
        args=[bot, user_id],
        id=f"morning_{user_id}",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        send_midday_reminder,
        CronTrigger(hour=mid_h, minute=mid_m),
        args=[bot, user_id],
        id=f"midday_{user_id}",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        send_evening_checkin,
        CronTrigger(hour=eh, minute=em),
        args=[bot, user_id],
        id=f"evening_{user_id}",
        replace_existing=True,
        misfire_grace_time=300,
    )


def schedule_deadline_checker(scheduler, bot):
    """Запустить глобальную проверку дедлайнов каждую минуту."""
    scheduler.add_job(
        check_deadlines,
        IntervalTrigger(minutes=1),
        args=[bot],
        id="deadline_checker",
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("Deadline checker scheduled (every 1 min)")


async def check_deadlines(bot):
    """Проверить все активные цели и отправить напоминания при необходимости."""
    now_ms = int(time.time() * 1000)  # текущее время в миллисекундах (как в JS)
    goals = await get_active_goals_with_deadline()

    for goal in goals:
        goal_id  = goal["id"]
        user_id  = goal["user_id"]
        text     = goal["text"]
        deadline = goal["deadline"]  # timestamp в мс (из JS Date.getTime())

        if deadline is None:
            continue

        ms_left = deadline - now_ms
        sec_left = ms_left / 1000

        # Уже просрочено — пропускаем (можно добавить отдельное уведомление)
        if sec_left < 0:
            continue

        for label, threshold_sec in REMINDER_THRESHOLDS:
            # Попадаем в окно: осталось меньше порога, но не меньше порога - 90 сек
            # (проверяем каждую минуту, окно 90 сек чтобы не пропустить)
            if sec_left <= threshold_sec and sec_left > threshold_sec - 90:
                already_sent = await was_notified(goal_id, label)
                if not already_sent:
                    reminder_line = REMINDER_TEXTS.get(label, f"⏳ Скоро дедлайн")
                    message = (
                        f"{reminder_line}\n\n"
                        f"🎯 Цель: *{text}*\n\n"
                        f"Не забудь — время идёт!"
                    )
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode="Markdown"
                        )
                        await mark_notified(goal_id, label)
                        logger.info(f"Reminder [{label}] sent to user {user_id} for goal '{text}'")
                    except Exception as e:
                        logger.error(f"Failed to send reminder to {user_id}: {e}")


async def send_morning_question(bot, user_id: int):
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    await bot.send_message(chat_id=user_id, text=t(lang, "morning_question"))


async def send_midday_reminder(bot, user_id: int):
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    task = await get_today_task(user_id)
    if task:
        await bot.send_message(chat_id=user_id, text=t(lang, "midday_reminder", task=task))
    else:
        await bot.send_message(chat_id=user_id, text=t(lang, "no_task_midday"))


async def send_evening_checkin(bot, user_id: int):
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    task = await get_today_task(user_id)
    if task:
        await bot.send_message(chat_id=user_id, text=t(lang, "evening_question", task=task))
    else:
        await bot.send_message(chat_id=user_id, text=t(lang, "no_task_evening"))
