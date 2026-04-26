import aiosqlite
import time
from datetime import date

DB_PATH = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                language       TEXT    DEFAULT 'ru',
                morning_hour   INTEGER DEFAULT 8,
                morning_minute INTEGER DEFAULT 0,
                evening_hour   INTEGER DEFAULT 21,
                evening_minute INTEGER DEFAULT 0
            )
        """)
        # Таблица целей из Веб-приложения
        await db.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id           TEXT    PRIMARY KEY,
                user_id      INTEGER NOT NULL,
                text         TEXT    NOT NULL,
                done         INTEGER DEFAULT 0,
                deadline     INTEGER,
                created_at   INTEGER NOT NULL,
                notified     TEXT    DEFAULT ''
            )
        """)
        # Таблица ежедневных задач (для утренних вопросов)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_tasks (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL,
                task     TEXT    NOT NULL,
                date     TEXT    NOT NULL
            )
        """)
        # Логи вечерних чекинов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS evening_logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                date      TEXT    NOT NULL,
                completed INTEGER NOT NULL,
                note      TEXT
            )
        """)
        await db.commit()

async def upsert_goal(user_id: int, goal_id: str, text: str, done: bool, deadline: int | None, created_at: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO goals (id, user_id, text, done, deadline, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                text     = excluded.text,
                done     = excluded.done,
                deadline = excluded.deadline
        """, (goal_id, user_id, text, int(done), deadline, created_at))
        await db.commit()

async def delete_goal(goal_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        await db.commit()

async def get_active_goals_with_deadline():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM goals WHERE done = 0 AND deadline IS NOT NULL")
        return await cursor.fetchall()

async def was_notified(goal_id: str, label: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT notified FROM goals WHERE id = ?", (goal_id,))
        row = await cursor.fetchone()
        return label in (row[0] or "").split(",") if row else False

async def mark_notified(goal_id: str, label: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT notified FROM goals WHERE id = ?", (goal_id,))
        row = await cursor.fetchone()
        curr = row[0] if row and row[0] else ""
        new = f"{curr},{label}".strip(",")
        await db.execute("UPDATE goals SET notified = ? WHERE id = ?", (new, goal_id))
        await db.commit()

# Функции для получения данных (используются в scheduler.py)
async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users")
        return await cursor.fetchall()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()

async def get_today_task(user_id: int):
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT task FROM daily_tasks WHERE user_id = ? AND date = ? ORDER BY id DESC LIMIT 1", (user_id, today))
        row = await cursor.fetchone()
        return row[0] if row else None