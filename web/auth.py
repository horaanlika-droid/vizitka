# -*- coding: utf-8 -*-
"""Авторизация Mini App: проверка Telegram initData (HMAC).

Если BOT_TOKEN нет или подпись не сошлась — доступ только в DEV-режиме
(ALLOW_DEV_AUTH=1, заголовок X-Dev-User или ?dev_user=).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl

from aiohttp import web

from config import settings

log = logging.getLogger("vizitka.auth")


@dataclass
class WebUser:
    id: int
    username: str = ""
    first_name: str = ""


def validate_init_data(init_data: str) -> Optional[WebUser]:
    if not init_data or not settings.bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        recv_hash = pairs.pop("hash", "")
        if not recv_hash:
            return None
        check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, recv_hash):
            return None
        user = json.loads(pairs.get("user", "{}"))
        return WebUser(id=int(user.get("id", 0)),
                       username=user.get("username", "") or "",
                       first_name=user.get("first_name", "") or "")
    except Exception as e:
        log.warning("initData invalid: %s", e)
        return None


def dev_user(request: web.Request) -> Optional[WebUser]:
    if not settings.allow_dev_auth:
        return None
    raw = request.headers.get("X-Dev-User") or request.query.get("dev_user") or ""
    try:
        uid = int(raw or 0)
    except ValueError:
        uid = 0
    if uid > 0:
        return WebUser(id=uid, username=f"dev_{uid}", first_name="Dev")
    return None


def current_user(request: web.Request) -> Optional[WebUser]:
    init_data = (request.headers.get("X-Telegram-Init-Data")
                 or request.query.get("initData") or "")
    user = validate_init_data(init_data)
    if user and user.id:
        return user
    return dev_user(request)


def require_user(handler):
    async def wrapper(request: web.Request):
        user = current_user(request)
        if not user:
            return web.json_response({"ok": False, "error": "auth_required"}, status=401)
        request["user"] = user
        return await handler(request)
    return wrapper


def require_admin(handler):
    async def wrapper(request: web.Request):
        token = (request.headers.get("X-Admin-Token")
                 or request.query.get("admin_token") or "")
        if not settings.admin_panel_token or token != settings.admin_panel_token:
            return web.json_response({"ok": False, "error": "forbidden"}, status=403)
        return await handler(request)
    return wrapper
