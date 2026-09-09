# -*- coding: utf-8 -*-
"""Центральная конфигурация из ENV.

Принципы (важно для Ботхоста):
1. Импорт config.py НИКОГДА не падает из-за отсутствующих переменных.
2. Все значения читаются лениво через объект settings, у каждой
   переменной есть безопасный дефолт.
3. Проверка окружения — отдельной функцией validate(), её вызывает
   main.py на старте и только ЛОГИРУЕТ предупреждения.
4. Порядок запуска в main.py: config -> db -> payments -> web -> bots,
   каждый этап независим и не роняет остальные.
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
    port: int = 8080             # PORT (Ботхост обычно выставляет сам)
    public_url: str = ""         # PUBLIC_URL — внешний https адрес сервиса
    webapp_url: str = ""         # WEBAPP_URL — адрес Mini App (по умолчанию PUBLIC_URL)

    # ---- база и файлы ----
    db_path: str = ""            # DB_PATH (по умолчанию game.db в корне)
    media_cache_dir: str = ""    # MEDIA_CACHE_DIR (кэш фото из Telegram)

    # ---- контакты/контент (перекрывают захардкоженное в legacy) ----
    contact_username: str = "milayaqueen"  # CONTACT_USERNAME (без @)
    payment_link: str = "https://yoomoney.ru/to/4100119149767529"  # PAYMENT_LINK (fallback)
    channels: list[str] = field(default_factory=lambda: ["chat_goddes"])  # CHANNELS

    # ---- оплата GRAM ----
    payments_provider: str = "auto"  # PAYMENTS_PROVIDER: auto|gram|manual
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
    ton_wallet_address: str = ""     # TON_WALLET_ADDRESS (если отличается от GRAM_WALLET_ADDRESS)
    gram_jetton_master: str = ""     # GRAM_JETTON_MASTER — адрес мастера GRAM Jetton (опционально)
    tonapi_check_interval: int = 30  # TONAPI_CHECK_INTERVAL — интервал проверки pending заказов

    # ---- админ-панель (веб) ----
    admin_panel_token: str = ""  # ADMIN_PANEL_TOKEN — доступ к /admin и admin API

    # ---- режимы запуска (каждый сервис независим) ----
    run_web: bool = True          # RUN_WEB
    run_client_bot: bool = True   # RUN_CLIENT_BOT
    run_admin_bot: bool = True    # RUN_ADMIN_BOT

    # ---- прочее ----
    allow_dev_auth: bool = False  # ALLOW_DEV_AUTH=1 — вход в веб без Telegram (превью)
    promo_sync_interval: int = 30  # PROMO_SYNC_INTERVAL — синк промокодов БД->бот, сек
    log_level: str = "INFO"       # LOG_LEVEL

    @classmethod
    def load(cls) -> "Settings":
        db_path = _str("DB_PATH", "game.db")
        media_dir = _str("MEDIA_CACHE_DIR", "media_cache")
        # PUBLIC_URL — пробуем авто-детект из популярных хостингов (БотХост, Render, Railway и т.д.)
        public_url = _str_any([
            "PUBLIC_URL", "WEBAPP_URL", "APP_URL", "BOTHOST_PUBLIC_URL",
            "RENDER_EXTERNAL_URL", "RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL",
            "HOST_URL", "BASE_URL", "EXTERNAL_URL"
        ], "").rstrip("/")
        # Railway дает домен без https
        if public_url and not public_url.startswith("http"):
            public_url = "https://" + public_url
        # WEBAPP_URL отдельно, если не задан — = PUBLIC_URL
        webapp_url = _str("WEBAPP_URL", public_url).rstrip("/") or public_url

        # Токены: ADMIN_BOT_TOKEN fallback на BOT_TOKEN, чтобы хватило одного токена
        bot_token = _str("BOT_TOKEN")
        admin_bot_token = _str("ADMIN_BOT_TOKEN") or bot_token

        # ADMIN_PANEL_TOKEN — если пусто, генерим из ADMIN_IDS, чтобы работал /admin без доп. настроек
        admin_panel_token = _str("ADMIN_PANEL_TOKEN")
        admin_ids_raw = _str("ADMIN_IDS", "1896036065")
        # если токен пуст, но есть ADMIN_IDS — сгенерим дефолтный, чтобы админка не была закрыта
        if not admin_panel_token and admin_ids_raw:
            # берем первый id как токен — просто и запоминается
            first_id = admin_ids_raw.split(",")[0].strip().replace(";", "")[:20]
            if first_id:
                admin_panel_token = f"admin_{first_id}"

        # TON кошелек — пробуем все варианты имен
        ton_wallet = _str_any(["TON_WALLET_ADDRESS", "GRAM_WALLET_ADDRESS", "WALLET_ADDRESS", "TON_WALLET"], "")

        return cls(
            bot_token=bot_token,
            admin_bot_token=admin_bot_token,
            admin_ids=_int_list("ADMIN_IDS", [1896036065]),
            host=_str("HOST", "0.0.0.0"),
            port=_int("PORT", 8080),
            public_url=public_url,
            webapp_url=webapp_url,
            db_path=str((PROJECT_ROOT / db_path).resolve()) if not os.path.isabs(db_path) else db_path,
            media_cache_dir=str((PROJECT_ROOT / media_dir).resolve()) if not os.path.isabs(media_dir) else media_dir,
            contact_username=_str("CONTACT_USERNAME", "milayaqueen").lstrip("@"),
            payment_link=_str("PAYMENT_LINK", "https://yoomoney.ru/to/4100119149767529"),
            channels=_str_list("CHANNELS", ["chat_goddes"]),
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
            run_client_bot=_bool("RUN_CLIENT_BOT", True),
            run_admin_bot=_bool("RUN_ADMIN_BOT", True),
            allow_dev_auth=_bool("ALLOW_DEV_AUTH", False),
            promo_sync_interval=_int("PROMO_SYNC_INTERVAL", 30),
            log_level=_str("LOG_LEVEL", "INFO").upper() or "INFO",
        )

    @property
    def gram_configured(self) -> bool:
        """True, если твой GRAM API задан и может использоваться."""
        return bool(self.gram_api_base_url and self.gram_api_key)

    @property
    def tonapi_configured(self) -> bool:
        """True, если TONAPI ключ задан — для минимального деплоя достаточно только ключа.
        Кошелек может быть задан позже через админку /admin или ENV."""
        # Для совместимости: раньше требовали кошелек, теперь достаточно ключа
        # poll loop сам проверит наличие кошелька в ENV или БД
        return bool(self.tonapi_key)

    @property
    def tonapi_wallet_configured(self) -> bool:
        """True, если и ключ и кошелек заданы — можно сразу проверять блокчейн."""
        wallet = self.ton_wallet_address or self.gram_wallet_address
        return bool(self.tonapi_key and wallet)

    @property
    def payments_mode(self) -> str:
        """Итоговый режим оплаты: 'gram' / 'tonapi' / 'manual'."""
        if self.payments_provider == "gram":
            return "gram"
        if self.payments_provider == "tonapi":
            return "tonapi"
        if self.payments_provider == "manual":
            return "manual"
        if self.gram_configured:
            return "gram"
        # если есть TONAPI ключ — считаем tonapi режимом, даже если кошелек пока не задан
        # (кошелек можно задать позже через /admin)
        if self.tonapi_configured:
            return "tonapi"
        return "manual"


settings = Settings.load()

# Совместимость со старым кодом: from config import ADMIN_IDS
ADMIN_IDS: list[int] = settings.admin_ids
ADMIN_ID: int | None = ADMIN_IDS[0] if ADMIN_IDS else None
BOT_TOKEN: str = settings.bot_token
CONTACT: str = "@" + settings.contact_username


def validate() -> list[str]:
    """Проверка окружения. Возвращает список предупреждений (не падает).
    Для минимального деплоя достаточно TONAPI_KEY + ADMIN_IDS — всё остальное опционально.
    """
    warns: list[str] = []
    if settings.run_client_bot and not settings.bot_token:
        warns.append("BOT_TOKEN пуст — клиентский бот не запустится (веб продолжит работать).")
    if settings.run_admin_bot and not settings.admin_bot_token:
        warns.append("ADMIN_BOT_TOKEN пуст — админ-бот не запустится (используй BOT_TOKEN как fallback).")
    if not settings.admin_ids:
        warns.append("ADMIN_IDS пуст — админ-функции недоступны.")
    if settings.payments_mode == "manual":
        if settings.payments_provider == "gram" and not settings.gram_configured:
            warns.append("PAYMENTS_PROVIDER=gram, но GRAM_API_* не заданы — оплата упадёт в ручной режим.")
        else:
            warns.append("Оплата в ручном режиме (подтверждение через админ-бота /admin).")
    elif settings.payments_mode == "tonapi":
        if not settings.tonapi_configured:
            warns.append("TONAPI_KEY не задан — автопроверка не работает.")
        elif not settings.tonapi_wallet_configured:
            warns.append("TONAPI_KEY есть, но TON_WALLET_ADDRESS пуст — задай кошелек в ENV или через /admin (настройки оплаты).")
        else:
            warns.append("TONAPI режим: оплата проверяется напрямую по блокчейну (мемо + сумма).")
    if not settings.admin_panel_token:
        warns.append("ADMIN_PANEL_TOKEN пуст — веб-админка (/admin) отключена.")
    else:
        # если токен сгенерирован автоматически — подскажем
        if settings.admin_panel_token.startswith("admin_"):
            warns.append(f"ADMIN_PANEL_TOKEN сгенерирован автоматически: {settings.admin_panel_token} — используй его для /admin?admin_token=...")
    if not settings.public_url and settings.run_web:
        warns.append("PUBLIC_URL пуст — авто-детект не сработал, WebApp-кнопка может не работать. Задай PUBLIC_URL если есть.")
    if settings.allow_dev_auth:
        warns.append("ALLOW_DEV_AUTH=1 — включён тестовый вход в веб БЕЗ Telegram! Выключи на проде.")
    # подсказка для минимального деплоя
    if settings.tonapi_key and settings.admin_ids:
        warns.append("Минимальный деплой OK: достаточно TONAPI_KEY + ADMIN_IDS, остальное опционально.")
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
    for w in validate():
        log.warning("config: %s", w)
