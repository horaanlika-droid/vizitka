# -*- coding: utf-8 -*-
"""Центральная конфигурация из ENV.

Принципы (важно для сервера):
1. Импорт config.py НИКОГДА не падает из-за отсутствующих переменных.
2. В панель сервера вводятся ТОЛЬКО секреты (токены/ключи).
   Все не-секретные настройки зашиты в код — блок SITE_* в начале файла.
3. Все значения читаются лениво через объект settings, у каждой
   переменной есть безопасный дефолт.
4. Проверка окружения — отдельной функцией validate(), её вызывает
   main.py на старте и только ЛОГИРУЕТ предупреждения.
5. Порядок запуска в main.py: config -> db -> payments -> web -> bots,
   каждый этап независим и не роняет остальные.

Минимальный деплой: достаточно TONAPI_KEY + ADMIN_IDS.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # локальный запуск: подхватить .env, на хостинге переменные уже в ENV
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

log = logging.getLogger("vizitka.config")

PROJECT_ROOT = Path(__file__).resolve().parent


class FatalStartupError(RuntimeError):
    """Ошибка старта сервиса, при которой перезапускать его внутри процесса бессмысленно.

    Пример: на нашем порту уже слушает ДРУГАЯ копия этого же приложения
    (дубль не собрался умирать при рестарте). В этом случае main.py глушит
    весь процесс-дубль, чтобы он не конфликтовал с работающей копией
    (в т.ч. за getUpdates в Telegram).
    """


# ============================================================
#  НЕ-СЕКРЕТНЫЕ настройки — живут В КОДЕ, в панель сервера их
#  вводить не нужно. Единственное, что обычно надо поменять
#  вручную, — SITE_PUBLIC_URL: подставь адрес, который сервер
#  выдаст проекту (например https://my-bot.com), либо
#  свой домен. ENV-переменные (если вдруг заданы) имеют приоритет
#  и переопределяют значения ниже.
# ============================================================
SITE_PUBLIC_URL = "https://tvoy-bot.com"  # ← ЗАМЕНИТЬ на реальный адрес
SITE_CONTACT_USERNAME = "milayaqueen"            # ТГ-юзернейм для связи, без @
SITE_PAYMENT_LINK = "https://yoomoney.ru/to/4100119149767529"  # ссылка-фолбэк на оплату
SITE_CHANNELS = ["chat_goddes"]                  # обязательные каналы
SITE_ADMIN_IDS = [1896036065]                    # id админов (без @)


def _str(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or default).strip()


def _str_any(names: list[str], default: str = "") -> str:
    """Взять первую непустую переменную из списка имен."""
    for n in names:
        v = (os.getenv(n, "") or "").strip()
        if v:
            return v
    return default


def _int(name: str, default: int) -> int:
    try:
        return int((os.getenv(name) or "").strip() or default)
    except (ValueError, TypeError):
        return default


def _int_any(names: list[str], default: int) -> int:
    """Взять первый валидный int-порт из списка имен (для хостингов).

    Улучшено для сервера: перебирает много вариантов, логирует что нашел.
    """
    for n in names:
        raw = (os.getenv(n) or "").strip()
        if not raw:
            continue
        # иногда хостинг дает URL вместо порта — пробуем вытащить порт из URL
        # или число из строки
        try:
            # если это URL типа https://...:8080 — парсим
            if "://" in raw:
                # берем после последнего :
                maybe_port = raw.rsplit(":", 1)[-1].split("/")[0]
                v = int(maybe_port)
            else:
                # убираем нецифровые символы кроме цифр
                cleaned = "".join(ch for ch in raw if ch.isdigit())
                # если исходное уже число — используем его
                if cleaned == raw or raw.isdigit():
                    v = int(raw)
                else:
                    # пробуем распарсить как int напрямую, иначе cleaned
                    try:
                        v = int(raw)
                    except ValueError:
                        v = int(cleaned) if cleaned else 0
            if 1 <= v <= 65535:
                if n != "PORT":
                    log.info("config: порт взят из %s=%s", n, v)
                return v
        except (ValueError, TypeError):
            continue
    return default


# Подстроки-заглушки: если PUBLIC_URL похож на это — считаем что не задан.
PLACEHOLDER_URL_MARKERS = ("tvoy-bot", "example", "change-me", "замени", "your-", "todo", "xxx")


def _is_placeholder_url(url: str) -> bool:
    u = (url or "").lower()
    if not u:
        return True
    return any(m in u for m in PLACEHOLDER_URL_MARKERS)


def _float(name: str, default: float) -> float:
    try:
        return float((os.getenv(name) or "").strip().replace(",", ".") or default)
    except (ValueError, TypeError):
        return default


def _bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw in ("1", "true", "yes", "y", "on", "да"):
        return True
    if raw in ("0", "false", "no", "n", "off", "нет"):
        return False
    return default


def _int_list(name: str, default: list[int] | None = None) -> list[int]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return list(default or [])
    out: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            log.warning("config: пропускаю мусор в %s: %r", name, part)
    return out


def _str_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return list(default or [])
    return [p.strip().lstrip("@") for p in raw.replace(";", ",").split(",") if p.strip()]


@dataclass
class Settings:
    # ---- боты ----
    bot_token: str = ""          # BOT_TOKEN — основной (клиентский) бот
    admin_bot_token: str = ""    # ADMIN_BOT_TOKEN — отдельный админ-бот
    admin_ids: list[int] = field(default_factory=list)  # ADMIN_IDS "id1,id2"

    # ---- веб ----
    host: str = "0.0.0.0"        # HOST
    port: int = 8080             # PORT (сервер обычно выставляет сам)
    public_url: str = ""         # PUBLIC_URL — внешний https адрес сервиса
    webapp_url: str = ""         # WEBAPP_URL — адрес Mini App (по умолчанию PUBLIC_URL)

    # ---- база и файлы ----
    db_path: str = ""            # DB_PATH (по умолчанию game.db в корне)
    media_cache_dir: str = ""    # MEDIA_CACHE_DIR (кэш фото из Telegram)

    # ---- контакты/контент (не секреты — зашиты в SITE_* выше) ----
    contact_username: str = SITE_CONTACT_USERNAME   # CONTACT_USERNAME (без @)
    payment_link: str = SITE_PAYMENT_LINK           # PAYMENT_LINK (fallback)
    channels: list[str] = field(default_factory=lambda: list(SITE_CHANNELS))  # CHANNELS

    # ---- оплата GRAM ----
    payments_provider: str = "auto"  # PAYMENTS_PROVIDER: auto|gram|manual|tonapi
    gram_api_base_url: str = ""      # GRAM_API_BASE_URL — твой API
    gram_api_key: str = ""           # GRAM_API_KEY
    gram_merchant_id: str = ""       # GRAM_MERCHANT_ID
    gram_wallet_address: str = ""    # GRAM_WALLET_ADDRESS — для ручного режима
    gram_webhook_secret: str = ""    # GRAM_WEBHOOK_SECRET — подпись колбэков
    gram_create_path: str = "/invoices"  # GRAM_CREATE_PATH
    gram_status_path: str = "/invoices/{id}"  # GRAM_STATUS_PATH
    gram_rub_rate: float = 0.0       # GRAM_RUB_RATE — курс для автоконвертации цен

    # ---- TONAPI (для проверки платежей TON/GRAM напрямую) ----
    tonapi_key: str = ""             # TONAPI_KEY — ключ с tonapi.io
    tonapi_base_url: str = "https://tonapi.io"  # TONAPI_BASE_URL
    ton_wallet_address: str = ""     # TON_WALLET_ADDRESS
    gram_jetton_master: str = ""     # GRAM_JETTON_MASTER — адрес мастера GRAM Jetton (опционально)
    tonapi_check_interval: int = 30  # TONAPI_CHECK_INTERVAL

    # ---- админ-панель (веб) ----
    admin_panel_token: str = ""  # ADMIN_PANEL_TOKEN — доступ к /admin и admin API

    # ---- режимы запуска ----
    run_web: bool = True
    # Клиентский бот выключен по умолчанию: витрина работает через веб,
    # а админ-бот может использовать BOT_TOKEN как fallback. Если запускать
    # два polling-бота с одним токеном, Telegram отвечает Conflict.
    run_client_bot: bool = False
    run_admin_bot: bool = True

    # ---- прочее ----
    allow_dev_auth: bool = False
    promo_sync_interval: int = 30
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> "Settings":
        db_path = _str("DB_PATH", "game.db")
        media_dir = _str("MEDIA_CACHE_DIR", "media_cache")

        # PUBLIC_URL — авто-детект из популярных хостингов + сервер
        # сервер может давать домен в разных переменных, пробуем все
        public_url = _str_any([
            "PUBLIC_URL", "WEBAPP_URL", "APP_URL",
            "BOT_PUBLIC_URL", "BOT_URL",
            "RENDER_EXTERNAL_URL", "RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL",
            "HOST_URL", "BASE_URL", "EXTERNAL_URL", "KOYEB_PUBLIC_DOMAIN",
            "VERCEL_URL", "FLY_APP_NAME", "HEROKU_APP_NAME",
        ], "").rstrip("/")
        # fallback на SITE_* из кода — но заглушку считаем пустой
        if not public_url:
            site_url = (SITE_PUBLIC_URL or "").strip().rstrip("/")
            if site_url and not _is_placeholder_url(site_url):
                public_url = site_url
        if public_url and not public_url.startswith("http"):
            # если это просто домен bot-123.com — добавляем https
            public_url = "https://" + public_url
        webapp_url = _str("WEBAPP_URL", public_url).rstrip("/") or public_url
        if _is_placeholder_url(webapp_url):
            webapp_url = public_url if not _is_placeholder_url(public_url) else ""

        # Токены: ADMIN_BOT_TOKEN fallback на BOT_TOKEN
        bot_token = _str("BOT_TOKEN")
        admin_bot_token = _str("ADMIN_BOT_TOKEN") or bot_token

        # ADMIN_PANEL_TOKEN — авто-генерация если пусто
        admin_panel_token = _str("ADMIN_PANEL_TOKEN")
        admin_ids_raw = _str("ADMIN_IDS", "")
        if not admin_panel_token and admin_ids_raw:
            first_id = admin_ids_raw.split(",")[0].strip().replace(";", "")[:20]
            if first_id:
                admin_panel_token = f"admin_{first_id}"
        elif not admin_panel_token:
            # fallback на дефолт из SITE_ADMIN_IDS
            admin_panel_token = f"admin_{SITE_ADMIN_IDS[0]}" if SITE_ADMIN_IDS else ""

        # TON кошелек — все варианты имен
        ton_wallet = _str_any(["TON_WALLET_ADDRESS", "GRAM_WALLET_ADDRESS", "WALLET_ADDRESS", "TON_WALLET"], "")

        # HOST — всегда 0.0.0.0 для сервера, но уважим ENV если там 0.0.0.0 или ::
        host_env = _str_any(["HOST", "SERVER_HOST", "WEB_HOST", "HTTP_HOST"], "0.0.0.0")
        # Если хост пустой или localhost — форсим 0.0.0.0 для серверов
        if not host_env or host_env in ("127.0.0.1", "localhost"):
            host_env = "0.0.0.0"

        # PORT — расширенный список
        port = _int_any([
            "PORT", "SERVER_PORT", "HTTP_PORT", "APP_PORT", "WEB_PORT",
            "EXTERNAL_PORT", "INTERNAL_PORT", "BOT_PORT", "WEBAPP_PORT",
        ], 8080)

        return cls(
            bot_token=bot_token,
            admin_bot_token=admin_bot_token,
            admin_ids=_int_list("ADMIN_IDS", SITE_ADMIN_IDS),
            host=host_env or "0.0.0.0",
            port=port,
            public_url=public_url,
            webapp_url=webapp_url,
            db_path=str((PROJECT_ROOT / db_path).resolve()) if not os.path.isabs(db_path) else db_path,
            media_cache_dir=str((PROJECT_ROOT / media_dir).resolve()) if not os.path.isabs(media_dir) else media_dir,
            contact_username=_str("CONTACT_USERNAME", SITE_CONTACT_USERNAME).lstrip("@"),
            payment_link=_str("PAYMENT_LINK", SITE_PAYMENT_LINK),
            channels=_str_list("CHANNELS", SITE_CHANNELS),
            payments_provider=_str("PAYMENTS_PROVIDER", "auto").lower() or "auto",
            gram_api_base_url=_str("GRAM_API_BASE_URL", "").rstrip("/"),
            gram_api_key=_str("GRAM_API_KEY", "") or _str("TONAPI_KEY", ""),
            gram_merchant_id=_str("GRAM_MERCHANT_ID", ""),
            gram_wallet_address=_str("GRAM_WALLET_ADDRESS", "") or ton_wallet,
            gram_webhook_secret=_str("GRAM_WEBHOOK_SECRET", ""),
            gram_create_path=_str("GRAM_CREATE_PATH", "/invoices"),
            gram_status_path=_str("GRAM_STATUS_PATH", "/invoices/{id}"),
            gram_rub_rate=_float("GRAM_RUB_RATE", 0.0),
            tonapi_key=_str("TONAPI_KEY", "") or _str("GRAM_API_KEY", ""),
            tonapi_base_url=_str("TONAPI_BASE_URL", "https://tonapi.io").rstrip("/"),
            ton_wallet_address=ton_wallet,
            gram_jetton_master=_str("GRAM_JETTON_MASTER", ""),
            tonapi_check_interval=_int("TONAPI_CHECK_INTERVAL", 30),
            admin_panel_token=admin_panel_token,
            run_web=_bool("RUN_WEB", True),
            run_client_bot=_bool("RUN_CLIENT_BOT", False),
            run_admin_bot=_bool("RUN_ADMIN_BOT", True),
            allow_dev_auth=_bool("ALLOW_DEV_AUTH", False),
            promo_sync_interval=_int("PROMO_SYNC_INTERVAL", 30),
            log_level=_str("LOG_LEVEL", "INFO").upper() or "INFO",
        )

    @property
    def gram_configured(self) -> bool:
        return bool(self.gram_api_base_url and self.gram_api_key)

    @property
    def tonapi_configured(self) -> bool:
        # Достаточно ключа для минимального деплоя
        return bool(self.tonapi_key)

    @property
    def tonapi_wallet_configured(self) -> bool:
        wallet = self.ton_wallet_address or self.gram_wallet_address
        return bool(self.tonapi_key and wallet)

    @property
    def payments_mode(self) -> str:
        if self.payments_provider == "gram":
            return "gram"
        if self.payments_provider == "tonapi":
            return "tonapi"
        if self.payments_provider == "manual":
            return "manual"
        if self.gram_configured:
            return "gram"
        if self.tonapi_configured:
            return "tonapi"
        return "manual"


settings = Settings.load()

ADMIN_IDS: list[int] = settings.admin_ids
ADMIN_ID: int | None = ADMIN_IDS[0] if ADMIN_IDS else None
BOT_TOKEN: str = settings.bot_token
CONTACT: str = "@" + settings.contact_username


def validate() -> list[str]:
    warns: list[str] = []
    if settings.run_client_bot and not settings.bot_token:
        warns.append("BOT_TOKEN пуст — клиентский бот не запустится (веб продолжит работать).")
    if settings.run_admin_bot and not settings.admin_bot_token:
        warns.append("ADMIN_BOT_TOKEN/BOT_TOKEN пуст — админ-бот не запустится.")
    if (
        settings.run_client_bot
        and settings.run_admin_bot
        and settings.bot_token
        and settings.admin_bot_token
        and settings.bot_token == settings.admin_bot_token
    ):
        warns.append(
            "BOT_TOKEN и ADMIN_BOT_TOKEN одинаковые — клиентский бот будет пропущен, "
            "иначе Telegram даст Conflict/getUpdates."
        )
    if not settings.admin_ids:
        warns.append("ADMIN_IDS пуст — админ-функции недоступны.")
    if settings.payments_mode == "manual":
        warns.append("Оплата в ручном режиме (подтверждение через админ-бота /admin).")
    elif settings.payments_mode == "tonapi":
        if not settings.tonapi_configured:
            warns.append("TONAPI_KEY не задан — автопроверка не работает.")
        elif not settings.tonapi_wallet_configured:
            warns.append("TONAPI_KEY есть, но TON_WALLET_ADDRESS пуст — задай кошелек в ENV или через /admin.")
        else:
            warns.append("TONAPI режим: оплата проверяется по блокчейну (мемо + сумма).")
    if not settings.admin_panel_token:
        warns.append("ADMIN_PANEL_TOKEN пуст — веб-админка (/admin) отключена.")
    elif settings.admin_panel_token.startswith("admin_"):
        warns.append(f"ADMIN_PANEL_TOKEN авто: {settings.admin_panel_token} — /admin?admin_token=...")
    if (not settings.public_url or _is_placeholder_url(settings.public_url)) and settings.run_web:
        warns.append("PUBLIC_URL пуст — вставь адрес из панели сервера в ENV PUBLIC_URL, иначе кнопка 🛍 ВИТРИНА не откроется.")
    if not settings.webapp_url and settings.run_web:
        warns.append("WEBAPP_URL пуст — кнопка витрины в боте отключена, но веб (/ и /api/*) работает.")
    if settings.allow_dev_auth:
        warns.append("ALLOW_DEV_AUTH=1 — тестовый вход БЕЗ Telegram! Выключи на проде.")
    if settings.tonapi_key and settings.admin_ids:
        warns.append("Минимальный деплой OK: достаточно TONAPI_KEY + ADMIN_IDS.")
    return warns


def log_startup_summary() -> None:
    log.info("=== vizitka config ===")
    log.info("web: run=%s %s:%s public=%s", settings.run_web, settings.host, settings.port,
             settings.public_url or "— (авто-детект)")
    log.info("client_bot: run=%s token=%s", settings.run_client_bot, "OK" if settings.bot_token else "—")
    log.info("admin_bot: run=%s token=%s admins=%s", settings.run_admin_bot,
             "OK" if settings.admin_bot_token else "—", settings.admin_ids or "—")
    log.info("payments: mode=%s gram_api=%s tonapi=%s wallet=%s", settings.payments_mode,
             "OK" if settings.gram_configured else "—",
             "OK" if settings.tonapi_configured else "—",
             (settings.ton_wallet_address or settings.gram_wallet_address or "—")[:12] + "…" if (settings.ton_wallet_address or settings.gram_wallet_address) else "— (задай через ENV или /admin)")
    log.info("admin_panel: token=%s", "OK" if settings.admin_panel_token else "—")
    log.info("db: %s", settings.db_path)
    # Доп. лог для сервера — покажем все PORT-переменные
    port_vars = {k: v for k, v in os.environ.items() if "PORT" in k.upper()}
    if port_vars:
        log.info("env PORT vars: %s", port_vars)
    for w in validate():
        log.warning("config: %s", w)
