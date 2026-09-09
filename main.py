# -*- coding: utf-8 -*-
"""Точка входа для Ботхоста.

Порядок запуска (как в .env.example):
config -> db -> payments -> web -> bots

Все сервисы независимы:
- если нет BOT_TOKEN — веб продолжит работать
- если нет ADMIN_BOT_TOKEN — админ-бот пропускается
- если нет TONAPI/GRAM API — оплата в manual режиме

Переменные окружения читаются из config.Settings (см. .env.example).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

# логирование до импорта остального
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)

log = logging.getLogger("vizitka.main")


def _ensure_dependencies() -> None:
    """Страховка для хостингов (БотХост и т.п.).

    Если build-команда (pip install -r requirements.txt) не выполнилась,
    ставим недостающие пакеты сами — до первых импортов, иначе процесс
    падает с ModuleNotFoundError (например: No module named 'aiosqlite').
    """
    import importlib.util
    import subprocess
    from pathlib import Path

    required = {
        "aiosqlite": "aiosqlite",
        "aiogram": "aiogram",
        "aiohttp": "aiohttp",
        "dotenv": "python-dotenv",
    }
    missing = [pip_name for mod, pip_name in required.items() if importlib.util.find_spec(mod) is None]
    if not missing:
        return

    log.warning("startup: не установлены пакеты: %s — ставлю через pip", ", ".join(missing))
    req_file = Path(__file__).with_name("requirements.txt")
    base_cmd = [sys.executable, "-m", "pip", "install", "--no-input", "--disable-pip-version-check"]
    # сначала пробуем по requirements.txt (пинненные версии), иначе — только недостающее
    attempts = [
        base_cmd + ["-r", str(req_file)] if req_file.exists() else None,
        base_cmd + missing,
        base_cmd + ["--user"] + missing,
    ]
    for cmd in attempts:
        if cmd is None:
            continue
        try:
            subprocess.run(cmd, check=True, timeout=600)
            log.info("startup: зависимости установлены: %s", ", ".join(missing))
            return
        except Exception as e:
            log.warning("startup: попытка pip install не удалась: %s", e)
    log.error("startup: не удалось установить зависимости — проверь build-команду на хостинге")
    raise SystemExit(1)


_ensure_dependencies()

from config import settings, log_startup_summary, validate, FatalStartupError  # noqa: E402
import database as db  # noqa: E402


async def _run_with_restart(coro_func, name: str):
    """Запускает корутину с авто-рестартом при падении."""
    while True:
        try:
            log.info("main: запуск %s", name)
            await coro_func()
            log.warning("main: %s завершился без ошибки — перезапуск через 5 сек", name)
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            log.info("main: %s отменён", name)
            break
        except FatalStartupError as e:
            # Например: наш порт уже слушает другая копия vizitka.
            # Внутренний рестарт бессмысленен (порт снова занят), а боты этого
            # процесса-дубля конфликтуют с работающей копией за getUpdates
            # (TelegramConflictError). Глушим весь процесс, чтобы осталась
            # одна живая копия — она и веб, и бота обслуживает.
            log.error(
                "main: %s: %s — останавливаю ВЕСЬ процесс (это дубль), "
                "чтобы не мешать работающей копии.",
                name, e,
            )
            # даём логам вытолкнуться в stdout хостинга и выходим
            await asyncio.sleep(0.2)
            os._exit(0)
        except Exception as e:
            log.exception("main: %s упал: %s — рестарт через 5 сек", name, e)
            await asyncio.sleep(5)


async def main():
    # 1. config
    try:
        # переопределяем уровень логов из ENV
        logging.getLogger().setLevel(getattr(logging, settings.log_level, logging.INFO))
    except Exception:
        pass

    log_startup_summary()
    for w in validate():
        log.warning("startup check: %s", w)

    # 2. db
    try:
        await db.init_db()
        log.info("main: db готов (%s)", settings.db_path)
    except Exception as e:
        log.exception("main: db init failed: %s", e)
        # не роняем весь процесс — веб и боты могут работать без БД? но лучше продолжить
        # если БД не создалась, дальнейшие запросы будут падать, но логи покажут

    tasks = []

    # 3. payments — фоновая проверка TONAPI если настроен
    if settings.tonapi_configured and settings.payments_mode in ("tonapi", "manual", "auto"):
        try:
            from payments.tonapi import tonapi_poll_loop
            tasks.append(asyncio.create_task(_run_with_restart(tonapi_poll_loop, "tonapi_poll"), name="tonapi_poll"))
            log.info("main: TONAPI poll включен (ключ OK, кошелек %s)", (settings.ton_wallet_address or settings.gram_wallet_address)[:12] + "…")
        except Exception as e:
            log.warning("main: не удалось запустить TONAPI poll: %s", e)
    else:
        log.info("main: TONAPI poll выключен (нет ключа или кошелька)")

    # 4. web
    if settings.run_web:
        try:
            from web import run_web_app
            tasks.append(asyncio.create_task(_run_with_restart(run_web_app, "web"), name="web"))
        except Exception as e:
            log.exception("main: web import/run failed: %s", e)
    else:
        log.info("main: RUN_WEB=0 — веб выключен")

    # 5. bots
    if settings.run_client_bot:
        if settings.bot_token:
            try:
                from bots.client_bot import run_client_bot
                tasks.append(asyncio.create_task(_run_with_restart(run_client_bot, "client_bot"), name="client_bot"))
            except Exception as e:
                log.exception("main: client_bot import failed: %s", e)
        else:
            log.warning("main: BOT_TOKEN пуст — client_bot пропускаю")
    else:
        log.info("main: RUN_CLIENT_BOT=0 — клиентский бот выключен")

    if settings.run_admin_bot:
        if settings.admin_bot_token:
            try:
                from bots.admin_bot import run_admin_bot
                tasks.append(asyncio.create_task(_run_with_restart(run_admin_bot, "admin_bot"), name="admin_bot"))
            except Exception as e:
                log.exception("main: admin_bot import failed: %s", e)
        else:
            log.warning("main: ADMIN_BOT_TOKEN пуст — admin_bot пропускаю")
    else:
        log.info("main: RUN_ADMIN_BOT=0 — админ-бот выключен")

    if not tasks:
        log.error("main: нечего запускать — все сервисы выключены. Проверь ENV.")
        return

    # Ждем все задачи
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        log.info("main: завершение")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("main: KeyboardInterrupt")
