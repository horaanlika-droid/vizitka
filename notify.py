# -*- coding: utf-8 -*-
"""Уведомления через Bot API напрямую (без aiogram).

Работает из любого процесса: веб-сервер шлёт события в боты,
админ-бот — пользователям клиентского бота.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp

from config import settings

log = logging.getLogger("vizitka.notify")


async def bot_api(token: str, method: str, timeout: int = 15, **params: Any) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, json=params, timeout=timeout) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    log.warning("bot_api %s: %s", method, data)
                return data
    except Exception as e:
        log.warning("bot_api %s failed: %s", method, e)
        return {"ok": False, "error": str(e)}


async def send_message(token: str, chat_id: int, text: str,
                       reply_markup: Optional[dict] = None,
                       parse_mode: str = "HTML") -> bool:
    if not token or not chat_id:
        return False
    params: dict[str, Any] = {"chat_id": chat_id, "text": text[:4000]}
    if parse_mode:
        params["parse_mode"] = parse_mode
    if reply_markup:
        params["reply_markup"] = reply_markup
    res = await bot_api(token, "sendMessage", **params)
    return bool(res.get("ok"))


async def notify_admins(text: str, reply_markup: Optional[dict] = None) -> None:
    """Сообщение всем админам (через админ-бота, fallback — клиентский)."""
    token = settings.admin_bot_token or settings.bot_token
    if not token:
        log.warning("notify_admins: нет токена, пропускаю")
        return
    for admin_id in settings.admin_ids:
        await send_message(token, admin_id, text, reply_markup)


async def notify_user(user_id: int, text: str,
                      reply_markup: Optional[dict] = None) -> bool:
    """Сообщение пользователю через клиентский бот."""
    if not settings.bot_token:
        log.warning("notify_user: BOT_TOKEN пуст")
        return False
    return await send_message(settings.bot_token, user_id, text, reply_markup)


async def check_subscription(user_id: int, channel: str) -> bool:
    """Проверка подписки на канал через клиентский бот."""
    if not settings.bot_token:
        return False
    res = await bot_api(settings.bot_token, "getChatMember",
                        chat_id=f"@{channel.lstrip('@')}", user_id=user_id)
    try:
        return res.get("result", {}).get("status") in ("member", "administrator", "creator")
    except Exception:
        return False
