from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from db import upsert_user, get_user, save_task, get_today_task, save_evening_log, get_streak
from texts import t, random_motivation
from telegram import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# Conversation states
CHOOSING_LANG = 0
SETTING_TIME = 1
SETTING_EVENING_TIME = 2
WAITING_MORNING_TASK = 3
WAITING_EVENING = 4


def main_menu_keyboard(lang: str):
    # Замени этот URL на адрес, где будет лежать твой index.html (например, GitHub Pages)
    WEB_APP_URL = "https://your-username.github.io/checklist-repo/"

    if lang == "ru":
        keyboard = [
            [
                KeyboardButton("📝 Задачи на сегодня", web_app=WebAppInfo(url=WEB_APP_URL)),
                KeyboardButton("✅ Вечерний чекин")
            ],
            ["ℹ️ Помощь", "⚙️ Настройки"],
        ]
    else:
        keyboard = [
            [
                KeyboardButton("📝 Today's tasks", web_app=WebAppInfo(url=WEB_APP_URL)),
                KeyboardButton("✅ Evening check-in")
            ],
            ["ℹ️ Help", "⚙️ Settings"],
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def yes_no_keyboard(lang: str):
    if lang == "ru":
        keyboard = [["✅ Да, выполнил!", "❌ Нет, не получилось"]]
    else:
        keyboard = [["✅ Yes, done!", "❌ No, didn't make it"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def time_suggestions_keyboard():
    keyboard = [
        ["07:00", "08:00", "09:00"],
        ["10:00", "11:00", "12:00"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def evening_time_suggestions_keyboard():
    keyboard = [
        ["19:00", "20:00", "21:00"],
        ["22:00", "23:00"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🇷🇺 Русский", "🇬🇧 English"]]
    await update.message.reply_text(
        "Привет! / Hello!\n\nВыбери язык / Choose language:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return CHOOSING_LANG


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = "ru" if "Русский" in update.message.text else "en"
    context.user_data["lang"] = lang
    context.user_data["setup_step"] = "morning"
    await update.message.reply_text(
        t(lang, "ask_morning_time"),
        reply_markup=time_suggestions_keyboard()
    )
    return SETTING_TIME


async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    text = update.message.text.strip()

    try:
        parts = text.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        assert 0 <= hour <= 23 and 0 <= minute <= 59
    except Exception:
        await update.message.reply_text(
            t(lang, "invalid_time"),
            reply_markup=time_suggestions_keyboard()
        )
        return SETTING_TIME

    step = context.user_data.get("setup_step", "morning")

    if step == "morning":
        context.user_data["morning_hour"] = hour
        context.user_data["morning_minute"] = minute
        context.user_data["setup_step"] = "evening"
        await update.message.reply_text(
            t(lang, "ask_evening_time"),
            reply_markup=evening_time_suggestions_keyboard()
        )
        return SETTING_TIME
    else:
        morning_h = context.user_data["morning_hour"]
        morning_m = context.user_data["morning_minute"]
        user_id = update.effective_user.id

        await upsert_user(
            user_id=user_id,
            language=lang,
            morning_hour=morning_h,
            morning_minute=morning_m,
            evening_hour=hour,
            evening_minute=minute,
        )

        from scheduler import schedule_user
        user = await get_user(user_id)
        schedule_user(context.application.scheduler, context.application.bot, user)

        morning_str = f"{morning_h:02d}:{morning_m:02d}"
        evening_str = f"{hour:02d}:{minute:02d}"

        await update.message.reply_text(
            t(lang, "setup_done", morning=morning_str, evening=evening_str),
            reply_markup=main_menu_keyboard(lang)
        )
        return ConversationHandler.END


async def handle_morning_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    task = update.message.text.strip()

    menu_buttons = {
        "📝 Задача на сегодня", "✅ Вечерний чекин", "ℹ️ Помощь", "⚙️ Настройки",
        "📝 Today's task", "✅ Evening check-in", "ℹ️ Help", "⚙️ Settings"
    }
    if task in menu_buttons:
        return WAITING_MORNING_TASK

    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    await save_task(user_id, task)
    motivation = random_motivation(lang)

    await update.message.reply_text(
        t(lang, "morning_saved", task=task, motivation=motivation),
        reply_markup=main_menu_keyboard(lang)
    )
    return ConversationHandler.END


async def handle_evening_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    yes_words = {"да", "yes", "д", "y", "yep", "конечно", "сделал", "done",
                 "выполнил", "✅ да, выполнил!", "✅ yes, done!"}
    completed = any(w in text.lower() for w in yes_words)

    await save_evening_log(user_id, completed, note=text)

    if completed:
        streak = await get_streak(user_id)
        await update.message.reply_text(
            t(lang, "evening_done", streak=streak),
            reply_markup=main_menu_keyboard(lang)
        )
    else:
        await update.message.reply_text(
            t(lang, "evening_not_done"),
            reply_markup=main_menu_keyboard(lang)
        )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    if lang == "ru":
        text = (
            "Вот что я умею:\n\n"
            "📝 *Задача на сегодня* — записать главную задачу дня\n"
            "✅ *Вечерний чекин* — отметить выполнена ли задача\n"
            "⚙️ *Настройки* — изменить время уведомлений\n\n"
            "Команды:\n"
            "/start — перезапустить настройку\n"
            "/restart — сбросить диалог если бот завис\n"
            "/help — показать это сообщение\n"
            "/cancel — отменить текущее действие"
        )
    else:
        text = (
            "Here's what I can do:\n\n"
            "📝 *Today's task* — set your main task for the day\n"
            "✅ *Evening check-in* — mark whether you completed it\n"
            "⚙️ *Settings* — change notification times\n\n"
            "Commands:\n"
            "/start — restart setup\n"
            "/restart — reset if the bot is stuck\n"
            "/help — show this message\n"
            "/cancel — cancel current action"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(lang)
    )


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    context.user_data.clear()

    if lang == "ru":
        text = "Готово! Бот перезапущен. Выбери что хочешь сделать:"
    else:
        text = "Done! Bot restarted. Choose what you want to do:"

    await update.message.reply_text(text, reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    context.user_data["lang"] = lang
    context.user_data["setup_step"] = "morning"

    await update.message.reply_text(
        t(lang, "ask_morning_time"),
        reply_markup=time_suggestions_keyboard()
    )
    return SETTING_TIME


async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    text = update.message.text

    task_buttons = {"📝 Задача на сегодня", "📝 Today's task"}
    evening_buttons = {"✅ Вечерний чекин", "✅ Evening check-in"}
    help_buttons = {"ℹ️ Помощь", "ℹ️ Help"}
    settings_buttons = {"⚙️ Настройки", "⚙️ Settings"}

    if text in task_buttons:
        await update.message.reply_text(
            t(lang, "morning_question"),
            reply_markup=ReplyKeyboardRemove()
        )
        return WAITING_MORNING_TASK

    elif text in evening_buttons:
        task = await get_today_task(user_id)
        if task:
            await update.message.reply_text(
                t(lang, "evening_question", task=task),
                reply_markup=yes_no_keyboard(lang)
            )
            return WAITING_EVENING
        else:
            await update.message.reply_text(
                t(lang, "no_task_evening"),
                reply_markup=main_menu_keyboard(lang)
            )

    elif text in help_buttons:
        await help_command(update, context)

    elif text in settings_buttons:
        return await settings_command(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"
    await update.message.reply_text(
        t(lang, "cancelled"),
        reply_markup=main_menu_keyboard(lang)
    )
    return ConversationHandler.END
