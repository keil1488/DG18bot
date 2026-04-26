import time
import logging
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from db import get_user, get_active_goals_with_deadline, was_notified, mark_notified
from texts import t

logger = logging.getLogger(__name__)


# ── Утреннее/дневное/вечернее расписание ────────────────────────────────────

def schedule_user(scheduler, bot, user):
    """Добавляет или обновляет все задания для пользователя."""
    user_id = user["user_id"]
    mh = user["morning_hour"]
    mm = user["morning_minute"]
    eh = user["evening_hour"]
    em = user["evening_minute"]

    # Середина дня — между утром и вечером
    mid_mins = (mh * 60 + mm + eh * 60 + em) // 2
    mid_h = mid_mins // 60
    mid_m = mid_mins % 60

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


async def send_morning_question(bot, user_id: int):
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    await bot.send_message(chat_id=user_id, text=t(lang, "morning_question"))


async def send_midday_reminder(bot, user_id: int):
    from db import get_today_task
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    task = await get_today_task(user_id)
    if task:
        await bot.send_message(chat_id=user_id, text=t(lang, "midday_reminder", task=task))
    else:
        await bot.send_message(chat_id=user_id, text=t(lang, "no_task_midday"))


async def send_evening_checkin(bot, user_id: int):
    from db import get_today_task
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    task = await get_today_task(user_id)
    if task:
        await bot.send_message(chat_id=user_id, text=t(lang, "evening_question", task=task))
    else:
        await bot.send_message(chat_id=user_id, text=t(lang, "no_task_evening"))


# ── Проверка дедлайнов целей ─────────────────────────────────────────────────

async def check_deadlines(bot):
    now_ms = int(time.time() * 1000)
    goals = await get_active_goals_with_deadline()

    for goal in goals:
        g_id = goal["id"]
        user_id = goal["user_id"]
        text = goal["text"]
        deadline = goal["deadline"]
        sec_left = (deadline - now_ms) / 1000

        if sec_left <= 0:
            if not await was_notified(g_id, "expired"):
                await bot.send_message(
                    user_id,
                    f"⌛ *ВРЕМЯ ВЫШЛО!*\n\n🎯 Цель: *{text}*",
                    parse_mode="Markdown"
                )
                await mark_notified(g_id, "expired")
            continue

        if sec_left <= 600 and not await was_notified(g_id, "10m"):
            await bot.send_message(
                user_id,
                f"⏰ Осталось 10 минут!\n\n🎯 Цель: *{text}*",
                parse_mode="Markdown"
            )
            await mark_notified(g_id, "10m")

        if sec_left <= 3600 and not await was_notified(g_id, "1h"):
            await bot.send_message(
                user_id,
                f"🔥 Остался 1 час!\n\n🎯 Цель: *{text}*",
                parse_mode="Markdown"
            )
            await mark_notified(g_id, "1h")


def schedule_deadline_checker(scheduler, bot):
    scheduler.add_job(
        check_deadlines,
        IntervalTrigger(seconds=30),
        args=[bot],
        id="deadline_checker",
        replace_existing=True,
    )
