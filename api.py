"""
api.py — лёгкий HTTP-сервер на aiohttp.
Веб-приложение (index.html) отправляет сюда POST-запросы
при создании, обновлении и удалении целей.

Эндпоинты:
  POST /goals/sync   — синхронизировать весь список целей пользователя
  POST /goals/delete — удалить одну цель
"""

import json
import logging
import os
import time
from aiohttp import web
from db import upsert_goal, delete_goal

logger = logging.getLogger(__name__)

# Секретный токен — задай в .env как WEBAPP_SECRET=xxx
# В index.html передавай тот же токен в заголовке X-Secret
WEBAPP_SECRET = os.getenv("WEBAPP_SECRET", "dg18secret")


def _check_secret(request: web.Request) -> bool:
    return request.headers.get("X-Secret") == WEBAPP_SECRET


async def sync_goals(request: web.Request) -> web.Response:
    """
    Принимает JSON:
    {
      "user_id": 123456789,
      "goals": [
        { "id": "abc", "text": "...", "done": false,
          "deadline": 1720000000000, "createdAt": 1719000000000 }
      ]
    }
    """
    if not _check_secret(request):
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    try:
        data = await request.json()
        user_id = int(data["user_id"])
        goals   = data.get("goals", [])
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

    for g in goals:
        await upsert_goal(
            user_id    = user_id,
            goal_id    = str(g["id"]),
            text       = g["text"],
            done       = bool(g.get("done", False)),
            deadline   = g.get("deadline"),   # может быть None
            created_at = g.get("createdAt", int(time.time() * 1000)),
        )

    logger.info(f"Synced {len(goals)} goals for user {user_id}")
    return web.json_response({"ok": True, "synced": len(goals)})


async def delete_goal_handler(request: web.Request) -> web.Response:
    """
    Принимает JSON:
    { "goal_id": "abc" }
    """
    if not _check_secret(request):
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    try:
        data = await request.json()
        goal_id = str(data["goal_id"])
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

    await delete_goal(goal_id)
    logger.info(f"Deleted goal {goal_id}")
    return web.json_response({"ok": True})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/goals/sync",   sync_goals)
    app.router.add_post("/goals/delete", delete_goal_handler)
    return app
