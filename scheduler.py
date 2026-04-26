from apscheduler.triggers.cron import CronTrigger
from db import get_user, get_today_task
from texts import t


def schedule_user(scheduler, bot, user):
    """Add or replace all scheduled jobs for a user."""
    user_id = user["user_id"]
    lang = user["language"]
    mh = user["morning_hour"]
    mm = user["morning_minute"]
    eh = user["evening_hour"]
    em = user["evening_minute"]

    # Calculate midday: halfway between morning and evening
    morning_mins = mh * 60 + mm
    evening_mins = eh * 60 + em
    midday_mins = (morning_mins + evening_mins) // 2
    mid_h = midday_mins // 60
    mid_m = midday_mins % 60

    # Morning job
    scheduler.add_job(
        send_morning_question,
        CronTrigger(hour=mh, minute=mm),
        args=[bot, user_id],
        id=f"morning_{user_id}",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Midday reminder
    scheduler.add_job(
        send_midday_reminder,
        CronTrigger(hour=mid_h, minute=mid_m),
        args=[bot, user_id],
        id=f"midday_{user_id}",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Evening check-in
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
    await bot.send_message(
        chat_id=user_id,
        text=t(lang, "morning_question")
    )


async def send_midday_reminder(bot, user_id: int):
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    task = await get_today_task(user_id)

    if task:
        await bot.send_message(
            chat_id=user_id,
            text=t(lang, "midday_reminder", task=task)
        )
    else:
        await bot.send_message(
            chat_id=user_id,
            text=t(lang, "no_task_midday")
        )


async def send_evening_checkin(bot, user_id: int):
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    task = await get_today_task(user_id)

    if task:
        await bot.send_message(
            chat_id=user_id,
            text=t(lang, "evening_question", task=task)
        )
    else:
        await bot.send_message(
            chat_id=user_id,
            text=t(lang, "no_task_evening")
        )
