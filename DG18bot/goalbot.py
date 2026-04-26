"""
GoalBot — многофункциональный Telegram-бот
Стек: Python 3.11+, aiogram 3.x, SQLite (aiosqlite), APScheduler
Установка:
    pip install aiogram aiosqlite apscheduler python-dotenv anthropic

Запуск:
    BOT_TOKEN=xxx ANTHROPIC_API_KEY=xxx python goalbot.py

.env пример:
    BOT_TOKEN=your_telegram_bot_token
    ANTHROPIC_API_KEY=your_anthropic_key
    CHANNEL_ID=-100xxxxxxxxx           # ID закрытого канала
    PAYMENT_PROVIDER_TOKEN=your_token  # От @BotFather (Stars или провайдер)
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, date
from typing import Optional

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, PreCheckoutQuery,
    ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiosqlite
import anthropic

# ─────────────────────────────────────────────
# Конфигурация
# ─────────────────────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8743923345:AAFdorSDswkdEAGz9Wp0Q6-3hZaAtDizjcY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003967028455"))
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "1744374395:TEST:1091dd6b4afa3ae12156")
DB_PATH = "goalbot.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DAILY_QUOTES = [
    "Успех — это сумма небольших усилий, повторяемых день за днём. — Р. Коллиер",
    "Не жди идеального момента, возьми момент и сделай его идеальным. — З. Кинг",
    "Дисциплина — это мост между целями и достижениями. — Дж. Рон",
    "Каждый день — это новая возможность изменить свою жизнь. — Неизвестный",
    "Великие дела делаются серией маленьких шагов. — В. Гюго",
    "Сделай сегодня то, что другие не хотят, и завтра будешь жить так, как другие не могут. — Д. Фуллер",
    "Движение к цели важнее самой цели. — Б. Трейси",
]

# ─────────────────────────────────────────────
# База данных
# ─────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_subscribed INTEGER DEFAULT 0,
                subscription_until TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                due_date TEXT,
                category TEXT DEFAULT 'Общее',
                is_done INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                exercise TEXT,
                sets INTEGER,
                reps INTEGER,
                weight REAL,
                logged_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS nutrition (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                food_name TEXT,
                calories REAL,
                protein REAL,
                fat REAL,
                carbs REAL,
                logged_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                target_count INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER,
                user_id INTEGER,
                logged_date TEXT,
                count INTEGER DEFAULT 1
            );
        """)
        await db.commit()
    log.info("DB initialized")

async def ensure_user(user_id: int, username: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()

async def is_subscribed(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT is_subscribed, subscription_until FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            is_sub, until = row
            if is_sub and until:
                if date.fromisoformat(until) >= date.today():
                    return True
            return False

# ─────────────────────────────────────────────
# Клавиатуры
# ─────────────────────────────────────────────
def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Задачи"), KeyboardButton(text="💪 Тренировки")],
            [KeyboardButton(text="🥗 КБЖУ"), KeyboardButton(text="✅ Привычки")],
            [KeyboardButton(text="🤖 ИИ-ассистент"), KeyboardButton(text="⭐ Подписка")],
            [KeyboardButton(text="💡 Мотивация")],
        ],
        resize_keyboard=True
    )

def tasks_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить задачу", callback_data="task_add")],
        [InlineKeyboardButton(text="📋 Мои задачи", callback_data="task_list")],
        [InlineKeyboardButton(text="✅ Отметить выполненной", callback_data="task_done")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="main_menu")],
    ])

def workout_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Записать упражнение", callback_data="workout_add")],
        [InlineKeyboardButton(text="📊 Мои тренировки", callback_data="workout_list")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="main_menu")],
    ])

def nutrition_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить еду", callback_data="nutrition_add")],
        [InlineKeyboardButton(text="📊 Дневник за сегодня", callback_data="nutrition_today")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="main_menu")],
    ])

def habits_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_add")],
        [InlineKeyboardButton(text="✅ Отметить привычку", callback_data="habit_log")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="habit_stats")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="main_menu")],
    ])

def subscription_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Подписка — 399 ₽/мес", callback_data="pay_monthly")],
        [InlineKeyboardButton(text="💎 Годовая — 2990 ₽/год", callback_data="pay_yearly")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="main_menu")],
    ])

# ─────────────────────────────────────────────
# FSM States
# ─────────────────────────────────────────────
class TaskStates(StatesGroup):
    waiting_title = State()
    waiting_date = State()
    waiting_category = State()
    waiting_done_id = State()

class WorkoutStates(StatesGroup):
    waiting_exercise = State()
    waiting_sets = State()
    waiting_reps = State()
    waiting_weight = State()

class NutritionStates(StatesGroup):
    waiting_food = State()
    waiting_calories = State()
    waiting_protein = State()
    waiting_fat = State()
    waiting_carbs = State()

class HabitStates(StatesGroup):
    waiting_name = State()
    waiting_target = State()
    waiting_log_id = State()

class AIStates(StatesGroup):
    chatting = State()

# ─────────────────────────────────────────────
# Роутер и хэндлеры
# ─────────────────────────────────────────────
router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message):
    await ensure_user(msg.from_user.id, msg.from_user.username or "")
    name = msg.from_user.first_name or "друг"
    quote = DAILY_QUOTES[date.today().toordinal() % len(DAILY_QUOTES)]
    await msg.answer(
        f"Привет, <b>{name}</b>! 👋\n\n"
        f"Я <b>GoalBot</b> — твой персональный помощник для достижения целей.\n\n"
        f"💡 <i>{quote}</i>\n\n"
        f"Выбери раздел в меню ниже 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )

# ── Мотивация ──────────────────────────────
@router.message(F.text == "💡 Мотивация")
async def motivation(msg: Message):
    quote = DAILY_QUOTES[date.today().toordinal() % len(DAILY_QUOTES)]
    await msg.answer(f"✨ <b>Цитата дня:</b>\n\n<i>{quote}</i>", parse_mode="HTML")

# ── Задачи ─────────────────────────────────
@router.message(F.text == "📋 Задачи")
async def tasks_menu(msg: Message):
    await msg.answer("📋 <b>Ежедневник и задачи</b>", parse_mode="HTML", reply_markup=tasks_kb())

@router.callback_query(F.data == "task_add")
async def task_add_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Введи название задачи:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(TaskStates.waiting_title)
    await cb.answer()

@router.message(TaskStates.waiting_title)
async def task_add_title(msg: Message, state: FSMContext):
    await state.update_data(title=msg.text)
    await msg.answer("Укажи дату выполнения (ГГГГ-ММ-ДД) или отправь «сегодня»:")
    await state.set_state(TaskStates.waiting_date)

@router.message(TaskStates.waiting_date)
async def task_add_date(msg: Message, state: FSMContext):
    due = str(date.today()) if msg.text.lower() == "сегодня" else msg.text
    await state.update_data(due_date=due)
    await msg.answer("Категория (Спорт / Работа / Саморазвитие / Другое):")
    await state.set_state(TaskStates.waiting_category)

@router.message(TaskStates.waiting_category)
async def task_add_category(msg: Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO tasks (user_id, title, due_date, category) VALUES (?, ?, ?, ?)",
            (msg.from_user.id, data["title"], data["due_date"], msg.text)
        )
        await db.commit()
    await state.clear()
    await msg.answer(
        f"✅ Задача добавлена!\n\n<b>{data['title']}</b>\n📅 {data['due_date']} · {msg.text}",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "task_list")
async def task_list(cb: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, title, due_date, category, is_done FROM tasks "
            "WHERE user_id = ? AND (due_date >= ? OR is_done = 0) ORDER BY due_date LIMIT 10",
            (cb.from_user.id, str(date.today()))
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        await cb.message.answer("📋 Задач нет. Добавь первую!")
        await cb.answer()
        return
    text = "📋 <b>Твои задачи:</b>\n\n"
    for row in rows:
        tid, title, due, cat, done = row
        icon = "✅" if done else "🔵"
        strike = "<s>" if done else ""
        end_s = "</s>" if done else ""
        text += f"{icon} [{tid}] {strike}{title}{end_s} · {cat} · {due}\n"
    await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "task_done")
async def task_done_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Введи ID задачи для отметки выполненной (число):")
    await state.set_state(TaskStates.waiting_done_id)
    await cb.answer()

@router.message(TaskStates.waiting_done_id)
async def task_done_finish(msg: Message, state: FSMContext):
    try:
        tid = int(msg.text)
    except ValueError:
        await msg.answer("Введи число!")
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET is_done = 1 WHERE id = ? AND user_id = ?",
            (tid, msg.from_user.id)
        )
        await db.commit()
    await state.clear()
    await msg.answer(f"✅ Задача #{tid} выполнена!", reply_markup=main_menu_kb())

# ── Тренировки ─────────────────────────────
@router.message(F.text == "💪 Тренировки")
async def workout_menu(msg: Message):
    await msg.answer("💪 <b>Тренировочный дневник</b>", parse_mode="HTML", reply_markup=workout_kb())

@router.callback_query(F.data == "workout_add")
async def workout_add_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Название упражнения:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(WorkoutStates.waiting_exercise)
    await cb.answer()

@router.message(WorkoutStates.waiting_exercise)
async def w_exercise(msg: Message, state: FSMContext):
    await state.update_data(exercise=msg.text)
    await msg.answer("Количество подходов:")
    await state.set_state(WorkoutStates.waiting_sets)

@router.message(WorkoutStates.waiting_sets)
async def w_sets(msg: Message, state: FSMContext):
    await state.update_data(sets=int(msg.text))
    await msg.answer("Количество повторений:")
    await state.set_state(WorkoutStates.waiting_reps)

@router.message(WorkoutStates.waiting_reps)
async def w_reps(msg: Message, state: FSMContext):
    await state.update_data(reps=int(msg.text))
    await msg.answer("Вес (кг), или 0 если без веса:")
    await state.set_state(WorkoutStates.waiting_weight)

@router.message(WorkoutStates.waiting_weight)
async def w_weight(msg: Message, state: FSMContext):
    data = await state.get_data()
    weight = float(msg.text.replace(",", "."))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO workouts (user_id, exercise, sets, reps, weight) VALUES (?, ?, ?, ?, ?)",
            (msg.from_user.id, data["exercise"], data["sets"], data["reps"], weight)
        )
        await db.commit()
    await state.clear()
    await msg.answer(
        f"💪 Записано!\n\n<b>{data['exercise']}</b>\n"
        f"{data['sets']} подхода × {data['reps']} повторений · {weight} кг",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "workout_list")
async def workout_list(cb: CallbackQuery):
    today = str(date.today())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT exercise, sets, reps, weight FROM workouts "
            "WHERE user_id = ? AND date(logged_at) = ? ORDER BY id",
            (cb.from_user.id, today)
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        await cb.message.answer("Тренировок сегодня нет. Самое время начать! 💪")
        await cb.answer()
        return
    text = f"💪 <b>Тренировка {today}:</b>\n\n"
    for ex, s, r, w in rows:
        text += f"• {ex}: {s}×{r} · {w} кг\n"
    await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()

# ── КБЖУ ───────────────────────────────────
@router.message(F.text == "🥗 КБЖУ")
async def nutrition_menu(msg: Message):
    await msg.answer("🥗 <b>Дневник КБЖУ</b>", parse_mode="HTML", reply_markup=nutrition_kb())

@router.callback_query(F.data == "nutrition_add")
async def nutrition_add_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Название продукта/блюда:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(NutritionStates.waiting_food)
    await cb.answer()

@router.message(NutritionStates.waiting_food)
async def n_food(msg: Message, state: FSMContext):
    await state.update_data(food=msg.text)
    await msg.answer("Калорий (ккал):")
    await state.set_state(NutritionStates.waiting_calories)

@router.message(NutritionStates.waiting_calories)
async def n_cal(msg: Message, state: FSMContext):
    await state.update_data(cal=float(msg.text))
    await msg.answer("Белки (г):")
    await state.set_state(NutritionStates.waiting_protein)

@router.message(NutritionStates.waiting_protein)
async def n_prot(msg: Message, state: FSMContext):
    await state.update_data(prot=float(msg.text))
    await msg.answer("Жиры (г):")
    await state.set_state(NutritionStates.waiting_fat)

@router.message(NutritionStates.waiting_fat)
async def n_fat(msg: Message, state: FSMContext):
    await state.update_data(fat=float(msg.text))
    await msg.answer("Углеводы (г):")
    await state.set_state(NutritionStates.waiting_carbs)

@router.message(NutritionStates.waiting_carbs)
async def n_carbs(msg: Message, state: FSMContext):
    data = await state.get_data()
    carbs = float(msg.text)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO nutrition (user_id, food_name, calories, protein, fat, carbs) VALUES (?, ?, ?, ?, ?, ?)",
            (msg.from_user.id, data["food"], data["cal"], data["prot"], data["fat"], carbs)
        )
        await db.commit()
    await state.clear()
    await msg.answer(
        f"🥗 Добавлено!\n\n<b>{data['food']}</b>\n"
        f"Калорий: {data['cal']} | Б: {data['prot']} г | Ж: {data['fat']} г | У: {carbs} г",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "nutrition_today")
async def nutrition_today(cb: CallbackQuery):
    today = str(date.today())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT SUM(calories), SUM(protein), SUM(fat), SUM(carbs) "
            "FROM nutrition WHERE user_id = ? AND date(logged_at) = ?",
            (cb.from_user.id, today)
        ) as cur:
            row = await cur.fetchone()
    cal, prot, fat, carbs = row if row and row[0] else (0, 0, 0, 0)
    await cb.message.answer(
        f"🥗 <b>Дневник за {today}:</b>\n\n"
        f"🔥 Калории: <b>{cal:.0f} ккал</b>\n"
        f"🥩 Белки: {prot:.1f} г\n"
        f"🧈 Жиры: {fat:.1f} г\n"
        f"🍞 Углеводы: {carbs:.1f} г",
        parse_mode="HTML"
    )
    await cb.answer()

# ── Привычки ────────────────────────────────
@router.message(F.text == "✅ Привычки")
async def habits_menu(msg: Message):
    await msg.answer("✅ <b>Трекер привычек</b>", parse_mode="HTML", reply_markup=habits_kb())

@router.callback_query(F.data == "habit_add")
async def habit_add_start(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Название привычки (напр. «Вода 8 стаканов»):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(HabitStates.waiting_name)
    await cb.answer()

@router.message(HabitStates.waiting_name)
async def habit_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await msg.answer("Целевое количество в день (напр. 8 для стаканов воды, или 1):")
    await state.set_state(HabitStates.waiting_target)

@router.message(HabitStates.waiting_target)
async def habit_target(msg: Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO habits (user_id, name, target_count) VALUES (?, ?, ?)",
            (msg.from_user.id, data["name"], int(msg.text))
        )
        await db.commit()
    await state.clear()
    await msg.answer(f"✅ Привычка «{data['name']}» создана!", reply_markup=main_menu_kb())

@router.callback_query(F.data == "habit_log")
async def habit_log_start(cb: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, name FROM habits WHERE user_id = ?",
            (cb.from_user.id,)
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        await cb.message.answer("Сначала создай привычку!")
        await cb.answer()
        return
    text = "Введи ID привычки:\n\n" + "\n".join(f"[{r[0]}] {r[1]}" for r in rows)
    await cb.message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(HabitStates.waiting_log_id)
    await cb.answer()

@router.message(HabitStates.waiting_log_id)
async def habit_log_finish(msg: Message, state: FSMContext):
    hid = int(msg.text)
    today = str(date.today())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM habit_logs WHERE habit_id = ? AND logged_date = ?",
            (hid, today)
        ) as cur:
            row = await cur.fetchone()
        if row:
            await db.execute(
                "UPDATE habit_logs SET count = count + 1 WHERE habit_id = ? AND logged_date = ?",
                (hid, today)
            )
        else:
            await db.execute(
                "INSERT INTO habit_logs (habit_id, user_id, logged_date) VALUES (?, ?, ?)",
                (hid, msg.from_user.id, today)
            )
        await db.commit()
    await state.clear()
    await msg.answer(f"✅ Привычка #{hid} отмечена на сегодня!", reply_markup=main_menu_kb())

@router.callback_query(F.data == "habit_stats")
async def habit_stats(cb: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT h.name, h.target_count,
                   COALESCE(SUM(hl.count), 0) as total,
                   COUNT(DISTINCT hl.logged_date) as days
            FROM habits h
            LEFT JOIN habit_logs hl ON h.id = hl.habit_id
            WHERE h.user_id = ?
            GROUP BY h.id
            """,
            (cb.from_user.id,)
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        await cb.message.answer("Нет привычек!")
        await cb.answer()
        return
    text = "📊 <b>Статистика привычек:</b>\n\n"
    for name, target, total, days in rows:
        text += f"• <b>{name}</b>\n  Всего отметок: {total} | Активных дней: {days}\n\n"
    await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()

# ── ИИ-ассистент ────────────────────────────
@router.message(F.text == "🤖 ИИ-ассистент")
async def ai_menu(msg: Message, state: FSMContext):
    sub = await is_subscribed(msg.from_user.id)
    if not sub:
        await msg.answer(
            "🤖 ИИ-ассистент доступен только для подписчиков.\n\n"
            "Оформи подписку через раздел ⭐ Подписка"
        )
        return
    await msg.answer(
        "🤖 <b>ИИ-ассистент активен!</b>\n\n"
        "Задай любой вопрос о здоровье, целях, мотивации или планировании.\n"
        "Для выхода напиши /menu",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AIStates.chatting)

@router.message(AIStates.chatting)
async def ai_chat(msg: Message, state: FSMContext):
    if msg.text == "/menu":
        await state.clear()
        await msg.answer("Главное меню:", reply_markup=main_menu_kb())
        return
    await msg.answer("🤔 Думаю...")
    try:
        response = ai_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=(
                "Ты личный AI-ассистент GoalBot — помогаешь пользователю достигать целей. "
                "Отвечай по-русски. Будь конкретным, мотивирующим и кратким (до 200 слов). "
                "Темы: здоровье, спорт, питание, привычки, продуктивность, личностный рост."
            ),
            messages=[{"role": "user", "content": msg.text}]
        )
        answer = response.content[0].text
    except Exception as e:
        log.error(f"AI error: {e}")
        answer = "Извини, что-то пошло не так. Попробуй позже."
    await msg.answer(f"🤖 {answer}", reply_markup=ReplyKeyboardRemove())

# ── Подписка ────────────────────────────────
@router.message(F.text == "⭐ Подписка")
async def subscription_menu(msg: Message):
    sub = await is_subscribed(msg.from_user.id)
    status = "✅ <b>У тебя активна подписка!</b>" if sub else "❌ Подписка не активна"
    await msg.answer(
        f"⭐ <b>GoalBot Pro</b>\n\n{status}\n\n"
        "Что входит в подписку:\n"
        "• ИИ-ассистент без ограничений\n"
        "• Расширенная аналитика\n"
        "• Доступ к закрытому каналу\n"
        "• Экспорт данных\n\n"
        "Выбери тариф:",
        parse_mode="HTML",
        reply_markup=subscription_kb()
    )

@router.callback_query(F.data.in_({"pay_monthly", "pay_yearly"}))
async def pay_invoice(cb: CallbackQuery, bot: Bot):
    if cb.data == "pay_monthly":
        title, desc, amount = "GoalBot Pro — 1 месяц", "Подписка на 1 месяц", 39900
    else:
        title, desc, amount = "GoalBot Pro — 1 год", "Годовая подписка", 299000

    if not PAYMENT_PROVIDER_TOKEN:
        await cb.message.answer(
            "⚙️ Платёжная система ещё не настроена.\n"
            "Свяжись с администратором для оплаты."
        )
        await cb.answer()
        return

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title=title,
        description=desc,
        payload=cb.data,
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=title, amount=amount)],
    )
    await cb.answer()

@router.pre_checkout_query()
async def pre_checkout(pcq: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pcq.id, ok=True)

@router.message(F.successful_payment)
async def payment_done(msg: Message, bot: Bot):
    user_id = msg.from_user.id
    payload = msg.successful_payment.invoice_payload
    months = 12 if payload == "pay_yearly" else 1
    from dateutil.relativedelta import relativedelta
    until = date.today() + relativedelta(months=months)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_subscribed = 1, subscription_until = ? WHERE user_id = ?",
            (str(until), user_id)
        )
        await db.commit()

    # Добавить в закрытый канал
    try:
        invite_link = await bot.create_chat_invite_link(CHANNEL_ID, member_limit=1)
        channel_text = f"\n\n🔗 <a href='{invite_link.invite_link}'>Войти в закрытый канал</a>"
    except Exception:
        channel_text = ""

    await msg.answer(
        f"🎉 <b>Оплата прошла!</b>\n\n"
        f"Подписка активна до <b>{until.strftime('%d.%m.%Y')}</b>.{channel_text}\n\n"
        "Теперь тебе доступны все функции GoalBot Pro!",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )

# ── Коллбэки навигации ──────────────────────
@router.callback_query(F.data == "main_menu")
async def back_to_menu(cb: CallbackQuery):
    await cb.message.answer("Главное меню:", reply_markup=main_menu_kb())
    await cb.answer()

# ─────────────────────────────────────────────
# Планировщик — ежедневная рассылка
# ─────────────────────────────────────────────
async def send_daily_motivation(bot: Bot):
    quote = DAILY_QUOTES[date.today().toordinal() % len(DAILY_QUOTES)]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()
    for (user_id,) in users:
        try:
            await bot.send_message(
                user_id,
                f"☀️ <b>Доброе утро!</b>\n\n💡 <i>{quote}</i>\n\nКак твои цели на сегодня?",
                parse_mode="HTML",
                reply_markup=main_menu_kb()
            )
        except Exception:
            pass

# ─────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────
async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_daily_motivation, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()

    log.info("GoalBot starting...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
