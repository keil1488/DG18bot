TEXTS = {
    "ru": {
        "welcome": (
            "Привет! Я твой личный бот продуктивности.\n\n"
            "Каждое утро буду задавать один простой вопрос, "
            "а вечером — проверять как прошёл твой день.\n\n"
            "Выбери язык:"
        ),
        "choose_lang": "Выбери язык / Choose language:",
        "ask_morning_time": (
            "Во сколько тебе присылать утренний вопрос?\n"
            "Напиши время в формате ЧЧ:ММ, например: 08:00"
        ),
        "ask_evening_time": (
            "Отлично! Во сколько присылать вечерний чекин?\n"
            "Напиши время в формате ЧЧ:ММ, например: 21:00"
        ),
        "setup_done": (
            "Готово! Настройка завершена.\n\n"
            "Утренний вопрос: {morning}\n"
            "Вечерний чекин: {evening}\n\n"
            "Увидимся утром!"
        ),
        "invalid_time": "Неверный формат. Попробуй ещё раз, например: 08:30",
        "morning_question": (
            "Доброе утро!\n\n"
            "Какое ОДНО дело сделает твой день успешным?\n\n"
            "Напиши одним предложением:"
        ),
        "morning_saved": (
            "Записал! Сегодня твоя задача:\n\n"
            "«{task}»\n\n"
            "{motivation}\n\n"
            "Удачи!"
        ),
        "midday_reminder": (
            "Привет! Середина дня.\n\n"
            "Напоминаю о твоей задаче:\n«{task}»\n\n"
            "Как идут дела?"
        ),
        "no_task_midday": "Ты ещё не записал задачу на сегодня. Напиши /start чтобы начать.",
        "evening_question": (
            "Добрый вечер!\n\n"
            "Твоя задача на сегодня была:\n«{task}»\n\n"
            "Ты выполнил её? Ответь «Да» или «Нет», и кратко — что получилось:"
        ),
        "no_task_evening": "Сегодня ты не записывал задачу. Увидимся завтра утром!",
        "evening_done": (
            "Отлично! Задача выполнена.\n\n"
            "Твоя серия: {streak} дн. подряд\n\n"
            "Так держать! Увидимся завтра."
        ),
        "evening_not_done": (
            "Ничего страшного. Завтра — новый день.\n\n"
            "Главное — не сдаваться. Увидимся утром!"
        ),
        "cancelled": "Окей, отменено.",
        "motivations": [
            "Начни — и станет легче.",
            "Одно дело, сделанное хорошо — лучше десяти сделанных плохо.",
            "Фокус — твой главный инструмент сегодня.",
            "Маленький шаг каждый день — большой результат через год.",
            "Ты уже молодец, что начал день с плана.",
        ],
    },
    "en": {
        "welcome": (
            "Hey! I'm your personal productivity bot.\n\n"
            "Every morning I'll ask you one simple question, "
            "and every evening I'll check how your day went.\n\n"
            "Choose your language:"
        ),
        "choose_lang": "Choose language / Выбери язык:",
        "ask_morning_time": (
            "What time should I send your morning question?\n"
            "Write in HH:MM format, e.g.: 08:00"
        ),
        "ask_evening_time": (
            "Great! What time should I send the evening check-in?\n"
            "Write in HH:MM format, e.g.: 21:00"
        ),
        "setup_done": (
            "All set!\n\n"
            "Morning question: {morning}\n"
            "Evening check-in: {evening}\n\n"
            "See you tomorrow morning!"
        ),
        "invalid_time": "Invalid format. Try again, e.g.: 08:30",
        "morning_question": (
            "Good morning!\n\n"
            "What ONE thing will make today a success?\n\n"
            "Write it in one sentence:"
        ),
        "morning_saved": (
            "Got it! Today's task:\n\n"
            "«{task}»\n\n"
            "{motivation}\n\n"
            "Good luck!"
        ),
        "midday_reminder": (
            "Hey! It's midday.\n\n"
            "Just a reminder of your task:\n«{task}»\n\n"
            "How's it going?"
        ),
        "no_task_midday": "You haven't set a task for today. Type /start to begin.",
        "evening_question": (
            "Good evening!\n\n"
            "Your task for today was:\n«{task}»\n\n"
            "Did you complete it? Reply 'Yes' or 'No' and briefly — what happened:"
        ),
        "no_task_evening": "You didn't set a task today. See you tomorrow morning!",
        "evening_done": (
            "Amazing! Task completed.\n\n"
            "Your streak: {streak} days in a row\n\n"
            "Keep it up! See you tomorrow."
        ),
        "evening_not_done": (
            "No worries. Tomorrow is a new day.\n\n"
            "The important thing is to keep going. See you in the morning!"
        ),
        "cancelled": "Okay, cancelled.",
        "motivations": [
            "Start — and it gets easier.",
            "One thing done well beats ten done poorly.",
            "Focus is your main tool today.",
            "A small step every day — a big result in a year.",
            "You're already ahead just by planning your day.",
        ],
    }
}


def t(lang: str, key: str, **kwargs) -> str:
    text = TEXTS.get(lang, TEXTS["ru"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def random_motivation(lang: str) -> str:
    import random
    return random.choice(TEXTS.get(lang, TEXTS["ru"])["motivations"])
