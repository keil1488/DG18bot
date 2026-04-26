import json
import logging
import os
import time
from aiohttp import web
import aiohttp_cors
from db import upsert_goal, delete_goal

logger = logging.getLogger(__name__)
WEBAPP_SECRET = os.getenv("WEBAPP_SECRET", "dg18secret")


async def sync_goals(request: web.Request) -> web.Response:
    if request.headers.get("X-Secret") != WEBAPP_SECRET:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    try:
        data = await request.json()
        user_id = int(data["user_id"])
        goals = data.get("goals", [])

        for g in goals:
            await upsert_goal(
                user_id=user_id,
                goal_id=str(g["id"]),
                text=g["text"],
                done=bool(g.get("done", False)),
                deadline=g.get("deadline"),
                created_at=g.get("createdAt", int(time.time() * 1000)),
            )
        return web.json_response({"ok": True, "synced": len(goals)})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)


async def delete_goal_handler(request: web.Request) -> web.Response:
    if request.headers.get("X-Secret") != WEBAPP_SECRET:
        return web.json_response({"ok": False}, status=401)

    data = await request.json()
    await delete_goal(str(data["goal_id"]))
    return web.json_response({"ok": True})


def create_app() -> web.Application:
    app = web.Application()

    # Настройка CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })

    cors.add(app.router.add_post("/goals/sync", sync_goals))
    cors.add(app.router.add_post("/goals/delete", delete_goal_handler))

    return app