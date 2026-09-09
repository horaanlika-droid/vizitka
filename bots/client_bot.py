# -*- coding: utf-8 -*-
"""Клиентский бот: старые хендлеры + кнопка веб-витрины.

- legacy-модуль грузится как есть (legacy_loader), правим только константы;
- в главное меню добавляется кнопка 🛍 ВИТРИНА (WebApp);
- промокоды синхронизируются с БД (персистентность + единый список с админ-ботом);
- кнопка 🎀 Стать Сисси из финала игры ведёт в школу сисси (в legacy она висела).
"""

from __future__ import annotations

import asyncio
import logging
from types import ModuleType
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    WebAppInfo,
)

import aiosqlite

import database as db
from config import settings
from legacy_loader import load_legacy
from scenes import scenes

log = logging.getLogger("vizitka.client_bot")

extra = Router()


# ---------- промокоды: dict с персистентностью в БД ----------

def _schedule(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_guard(coro))
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)


async def _guard(coro) -> None:
    try:
        await coro
    except Exception as e:
        log.warning("promo hook: %s", e)


class PromoDict(dict):
    """dict, который дублирует изменения в таблицу promocodes."""

    def __setitem__(self, code: str, value: Any) -> None:
        super().__setitem__(code, value)
        reward = value.get("reward", "") if isinstance(value, dict) else str(value)
        _schedule(db.db_create_promocode(str(code), str(reward)))

    def __delitem__(self, code: str) -> None:
        super().__delitem__(code)
        _schedule(_deactivate_db(code))

    def pop(self, code: str, *a):  # type: ignore[override]
        if code in self:
            del self[code]
            return True
        return a[0] if a else None


async def _deactivate_db(code: str) -> None:
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute("UPDATE promocodes SET used = max_uses WHERE code = ?",
                           (str(code).upper().strip(),))
        await conn.commit()


_DB_CODES_KEY = "_db_codes"


async def sync_promos_from_db(legacy: ModuleType) -> None:
    """Подтянуть промокоды из БД в память legacy (без срабатывания хуков)."""
    try:
        promos = await db.db_list_promocodes()
    except Exception as e:
        log.warning("promo sync: %s", e)
        return
    store: dict = legacy.active_promocodes
    live = {p["code"] for p in promos if p["is_active"] and p["used"] < p["max_uses"]}
    for p in promos:
        if p["code"] in live and p["code"] not in store:
            dict.__setitem__(store, p["code"], {"reward": p["reward"]})
    known: set = getattr(legacy, _DB_CODES_KEY, set())
    for code in list(known - live):
        if code in store:
            dict.__delitem__(store, code)
    setattr(legacy, _DB_CODES_KEY, live)


async def promo_sync_loop(legacy: ModuleType) -> None:
    await sync_promos_from_db(legacy)
    while True:
        await asyncio.sleep(max(10, settings.promo_sync_interval))
        await sync_promos_from_db(legacy)


def install_promo_store(legacy: ModuleType) -> None:
    old: dict = legacy.active_promocodes
    store = PromoDict(old)
    legacy.active_promocodes = store


# ---------- WebApp-кнопка в главном меню ----------

def install_webapp_button(legacy: ModuleType) -> None:
    if not settings.webapp_url:
        log.warning("client_bot: WEBAPP_URL пуст — кнопка витрины не добавлена")
        return
    orig = legacy.get_main_keyboard

    def patched():
        kb = orig()
        kb.keyboard.append([KeyboardButton(
            text="🛍 ВИТРИНА",
            web_app=WebAppInfo(url=settings.webapp_url),
        )])
        return kb

    legacy.get_main_keyboard = patched
    log.info("client_bot: кнопка витрины -> %s", settings.webapp_url)


# ---------- доп. хендлеры ----------

@extra.message(Command("app"))
async def cmd_app(message: Message) -> None:
    if not settings.webapp_url:
        await message.answer("🛍 Витрина пока не настроена. Напиши в ЛС @"
                             + settings.contact_username)
        return
    await message.answer(
        "🛍 <b>Витрина</b>\n\nТовары, сессии, оплата GRAM — всё в одном окне:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🛍 ОТКРЫТЬ ВИТРИНУ",
                                 web_app=WebAppInfo(url=settings.webapp_url))
        ]]),
    )


@extra.callback_query(F.data == "sissy_access")
async def sissy_access(callback: Any) -> None:
    """Кнопка из идеального финала: вести в школу сисси."""
    user_id = callback.from_user.id
    scene = scenes.get("sissy_lesson1")
    if not scene:
        await callback.answer("Раздел недоступен", show_alert=True)
        return
    legacy = load_legacy()
    await db.ensure_player(user_id, callback.from_user.username or "")
    await db.update_current_scene(user_id, "sissy_lesson1")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await legacy.show_scene(callback.message, user_id, scene, "sissy_lesson1")
    await callback.answer()


# ---------- сборка и запуск ----------

def build_client_bot() -> tuple[Bot, Dispatcher]:
    legacy = load_legacy()
    bot = Bot(token=settings.bot_token,
              default=DefaultBotProperties(parse_mode="HTML"))
    legacy.set_bot(bot)
    install_promo_store(legacy)
    install_webapp_button(legacy)

    dp = Dispatcher()
    dp.include_router(extra)
    dp.include_router(legacy.router)
    return bot, dp


async def run_client_bot() -> None:
    if not settings.bot_token:
        log.warning("client_bot: BOT_TOKEN пуст — пропуск")
        return
    bot, dp = build_client_bot()
    legacy = load_legacy()
    sync_task = asyncio.create_task(promo_sync_loop(legacy))
    log.info("client_bot: polling стартовал")
    try:
        await dp.start_polling(bot)
    finally:
        sync_task.cancel()
        await bot.session.close()
