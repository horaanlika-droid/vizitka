# -*- coding: utf-8 -*-
"""Загрузка старого файла хендлеров (имя с пробелами/кириллицей).

Старый файл не трогаем: подменяем только константы (оплата, контакт,
админ, каналы) значениями из config.py, чтобы всё управлялось через ENV.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

from config import PROJECT_ROOT, settings

log = logging.getLogger("vizitka.legacy")

LEGACY_FILENAME = "хендлерс который у меня на боте."

_cached: ModuleType | None = None


def _find_legacy_file() -> Path | None:
    for name in (LEGACY_FILENAME, LEGACY_FILENAME + ".py", "legacy_handlers.py"):
        p = PROJECT_ROOT / name
        if p.is_file():
            return p
    # fallback: любой файл с 'хендлерс' в имени
    for p in PROJECT_ROOT.glob("*хендлерс*"):
        if p.is_file() and p.suffix != ".pyc":
            return p
    return None


def load_legacy() -> ModuleType:
    """Импортировать legacy-модуль один раз, вернуть его."""
    global _cached
    if _cached is not None:
        return _cached

    path = _find_legacy_file()
    if not path:
        raise FileNotFoundError("legacy-файл хендлеров не найден")

    # старый код делает from config/database/scenes import ... — корень в sys.path
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)

    # spec_from_file_location не работает для файлов без .py — делаем fallback через exec
    spec = importlib.util.spec_from_file_location("legacy_handlers", path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules["legacy_handlers"] = module
        spec.loader.exec_module(module)
    else:
        # ручная загрузка: читаем файл как текст и исполняем
        log.warning("legacy: файл без .py расширения (%s), гружу через exec", path.name)
        import types
        module = types.ModuleType("legacy_handlers")
        sys.modules["legacy_handlers"] = module
        # нужно подставить __file__ для относительных импортов
        module.__file__ = str(path)
        code = path.read_text(encoding="utf-8", errors="ignore")
        # компилируем и исполняем в контексте модуля
        exec(compile(code, str(path), "exec"), module.__dict__)

    # --- перекрываем константы значениями из ENV ---
    module.PAYMENT_LINK = settings.payment_link
    module.DICE_PAYMENT_LINK = settings.payment_link
    module.CONTACT = "@" + settings.contact_username
    if settings.admin_ids:
        module.ADMIN_ID = settings.admin_ids[0]
    if settings.channels:
        module.CHANNELS = list(settings.channels)

    log.info("legacy: загружен %s", path.name)
    _cached = module
    return _cached
