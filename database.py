# -*- coding: utf-8 -*-
"""SQLite-слой (aiosqlite).

- Полностью реализует функции, которые ждёт старый файл хендлеров
  (from database import *) — старый game.db подхватится как есть,
  недостающие колонки/таблицы докреются миграцией ensure_schema().
- Новые таблицы витрины: products, orders, sessions, promocodes, reviews, payments.
"""

from __future__ import annotations

import aiosqlite
import asyncio
import logging
import time
from typing import Any, Optional

from config import settings

log = logging.getLogger("vizitka.db")

__all__ = [
    # служебные
    "init_db", "ensure_schema", "ensure_player", "utcnow",
    # горячее предложение
    "get_hot_offer", "set_hot_offer", "clear_hot_offer",
    # legacy-игроки
    "get_player", "create_player", "get_username", "update_dressage_level",
    "get_points", "get_nickname", "get_rolls_left", "get_used_rolls",
    "get_dressage_level", "get_sissy_level", "get_adult_level",
    "get_invites_count", "get_achievements", "get_current_scene",
    "update_current_scene", "reset_player", "verify_tasks", "set_ending",
    "add_points", "add_achievement", "complete_dressage", "complete_adult",
    "set_rolls_left", "increment_used_rolls", "update_sissy_level",
    "update_adult_level", "get_all_players", "get_stats",
    # витрина: товары
    "create_product", "get_product", "list_products", "update_product",
    "delete_product", "toggle_product",
    # заказы и оплаты
    "create_order", "get_order", "list_orders", "set_order_status",
    "attach_provider", "record_payment",
    # сессии
    "create_session_request", "get_session_request", "list_session_requests",
    "set_session_status",
    # промокоды (персистентные)
    "db_create_promocode", "db_list_promocodes", "db_delete_promocode",
    "db_use_promocode", "db_get_promocode",
    # отзывы
    "db_add_review", "db_list_reviews", "db_delete_review",
    # курс
    "get_gram_rate", "set_gram_rate",
    # общие настройки (для минимального деплоя)
    "get_setting", "set_setting", "get_wallet_address", "set_wallet_address",
]

_lock = asyncio.Lock()
DB_PATH = settings.db_path


def utcnow() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ---------- низкоуровневые хелперы ----------

async def _connect() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def _fetchone(query: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
    async with _lock:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cur:
                return await cur.fetchone()


async def _fetchall(query: str, params: tuple = ()) -> list[aiosqlite.Row]:
    async with _lock:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cur:
                return await cur.fetchall()


async def _exec(query: str, params: tuple = ()) -> int:
    """Выполнить INSERT/UPDATE/DELETE. Возвращает lastrowid."""
    async with _lock:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, params)
            await db.commit()
            return cur.lastrowid or 0


async def _execmany(query: str, seq: list[tuple]) -> None:
    async with _lock:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            await db.executemany(query, seq)
            await db.commit()


# ---------- схема ----------

_PLAYERS_COLUMNS: dict[str, str] = {
    "user_id": "INTEGER PRIMARY KEY",
    "username": "TEXT DEFAULT ''",
    "nickname": "TEXT DEFAULT ''",
    "points": "INTEGER DEFAULT 0",
    "rolls_left": "INTEGER DEFAULT 0",
    "used_rolls": "INTEGER DEFAULT 0",
    "dressage_level": "INTEGER DEFAULT 0",
    "sissy_level": "INTEGER DEFAULT 0",
    "adult_level": "INTEGER DEFAULT 0",
    "sissy_access": "INTEGER DEFAULT 0",
    "current_scene": "TEXT DEFAULT 'prolog_scene1'",
    "invites_count": "INTEGER DEFAULT 0",
    "achievements": "TEXT DEFAULT ''",
    "payment_tier": "TEXT DEFAULT ''",
    "ending": "TEXT DEFAULT ''",
    "tasks_verified": "INTEGER DEFAULT 0",
    "dressage_done": "INTEGER DEFAULT 0",
    "adult_done": "INTEGER DEFAULT 0",
    "created_at": "TEXT DEFAULT ''",
    "updated_at": "TEXT DEFAULT ''",
}

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    username TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    photo_file_id TEXT DEFAULT '',
    photo_url TEXT DEFAULT '',
    price_gram REAL,
    price_rub REAL,
    category TEXT DEFAULT 'general',
    is_active INTEGER DEFAULT 1,
    sort INTEGER DEFAULT 0,
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT DEFAULT '',
    product_id INTEGER DEFAULT 0,
    title TEXT DEFAULT '',
    amount_gram REAL,
    amount_rub REAL,
    promocode TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    pay_memo TEXT DEFAULT '',
    provider TEXT DEFAULT 'manual',
    provider_id TEXT DEFAULT '',
    provider_raw TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT DEFAULT '',
    kind TEXT DEFAULT 'instant',
    product_id INTEGER DEFAULT 0,
    order_id INTEGER DEFAULT 0,
    slot TEXT DEFAULT '',
    comment TEXT DEFAULT '',
    status TEXT DEFAULT 'new',
    admin_comment TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

CREATE TABLE IF NOT EXISTS promocodes (
    code TEXT PRIMARY KEY,
    reward TEXT DEFAULT '',
    max_uses INTEGER DEFAULT 1,
    used INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_name TEXT,
    review_text TEXT,
    review_date TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    provider TEXT DEFAULT '',
    provider_payment_id TEXT DEFAULT '',
    amount REAL,
    currency TEXT DEFAULT 'GRAM',
    status TEXT DEFAULT '',
    raw TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
"""


async def ensure_schema() -> None:
    """Создать таблицы и докрутить недостающие колонки players (для старого game.db)."""
    async with _lock:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            await db.executescript(_SCHEMA_SQL)
            async with db.execute("PRAGMA table_info(players)") as cur:
                existing = {row[1] for row in await cur.fetchall()}
            for col, ddl in _PLAYERS_COLUMNS.items():
                if col not in existing:
                    # PRIMARY KEY нельзя добавить через ALTER — но user_id есть всегда
                    coldef = ddl.replace(" PRIMARY KEY", "")
                    await db.execute(f"ALTER TABLE players ADD COLUMN {col} {coldef}")
                    log.info("db: добавлена колонка players.%s", col)
            await db.commit()


_SEED_PRODUCTS = [
    ("🔞 Приватка", "Самый горячий контент. Доступ в закрытый канал после оплаты.",
     "content", 999.0, 10),
    ("👠 Сессия с Богиней", "Индивидуальная сессия: задания, контроль, личное внимание.",
     "session", None, 20),
    ("🔐 Дрессировка", "5 испытаний для послушных псов. Код доступа после оплаты.",
     "course", 111.0, 30),
    ("🎀 Стать сисси", "6 уроков трансформации + закрытый чат для выпускниц.",
     "course", 333.0, 40),
    ("🔞 Тёмная комната", "6 испытаний для самых смелых. Финалистам — сессия в подарок.",
     "course", 777.0, 50),
    ("🎲 Кубики ×1", "Один бросок кубика с призами от Богини.", "dice", 222.0, 60),
    ("🎲 Кубики ×3", "Три броска — выгоднее.", "dice", 444.0, 61),
    ("🎲 Кубики ×5", "Пять бросков — супер цена.", "dice", 555.0, 62),
    ("🏷️ Кличка", "Личное имя от Богини в профиль.", "extra", 111.0, 70),
]


async def _seed_products() -> None:
    row = await _fetchone("SELECT COUNT(*) AS c FROM products")
    if row and row["c"]:
        return
    now = utcnow()
    await _execmany(
        "INSERT INTO products (title, description, category, price_rub, sort, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [(t, d, c, p, s, now) for (t, d, c, p, s) in _SEED_PRODUCTS],
    )
    log.info("db: добавлены стартовые товары витрины (%d)", len(_SEED_PRODUCTS))


async def init_db() -> None:
    await ensure_schema()
    await _seed_products()


# ---------- legacy: игроки ----------

def _row_to_dict(row: Optional[aiosqlite.Row]) -> Optional[dict[str, Any]]:
    return dict(row) if row else None


async def get_player(user_id: int) -> Optional[dict[str, Any]]:
    return _row_to_dict(await _fetchone("SELECT * FROM players WHERE user_id = ?", (user_id,)))


async def create_player(user_id: int, username: str) -> None:
    now = utcnow()
    await _exec(
        "INSERT OR IGNORE INTO players (user_id, username, created_at, updated_at)"
        " VALUES (?, ?, ?, ?)",
        (user_id, username or "", now, now),
    )


async def ensure_player(user_id: int, username: str = "") -> dict[str, Any]:
    p = await get_player(user_id)
    if not p:
        await create_player(user_id, username)
        p = await get_player(user_id)
    elif username and not p.get("username"):
        await _exec("UPDATE players SET username = ?, updated_at = ? WHERE user_id = ?",
                    (username, utcnow(), user_id))
        p = await get_player(user_id)
    return p or {}


async def _get_field(user_id: int, field: str, default: Any = 0) -> Any:
    row = await _fetchone(f"SELECT {field} FROM players WHERE user_id = ?", (user_id,))
    if not row or row[field] is None:
        return default
    return row[field]


async def _set_field(user_id: int, field: str, value: Any) -> None:
    await _exec(f"UPDATE players SET {field} = ?, updated_at = ? WHERE user_id = ?",
                (value, utcnow(), user_id))


async def get_username(user_id: int) -> str:
    return str(await _get_field(user_id, "username", "") or f"user_{user_id}")


async def get_points(user_id: int) -> int:
    return int(await _get_field(user_id, "points", 0))


async def add_points(user_id: int, delta: int) -> int:
    await ensure_player(user_id)
    total = await get_points(user_id) + int(delta)
    await _set_field(user_id, "points", total)
    return total


async def get_nickname(user_id: int) -> str:
    return str(await _get_field(user_id, "nickname", "") or "")


async def get_rolls_left(user_id: int) -> int:
    return int(await _get_field(user_id, "rolls_left", 0))


async def set_rolls_left(user_id: int, value: int) -> None:
    await _set_field(user_id, "rolls_left", int(value))


async def get_used_rolls(user_id: int) -> int:
    return int(await _get_field(user_id, "used_rolls", 0))


async def increment_used_rolls(user_id: int) -> None:
    await _set_field(user_id, "used_rolls", await get_used_rolls(user_id) + 1)


async def get_dressage_level(user_id: int) -> int:
    return int(await _get_field(user_id, "dressage_level", 0))


async def update_dressage_level(user_id: int, level: int) -> None:
    await _set_field(user_id, "dressage_level", int(level))


async def get_sissy_level(user_id: int) -> int:
    return int(await _get_field(user_id, "sissy_level", 0))


async def update_sissy_level(user_id: int, level: int) -> None:
    await _set_field(user_id, "sissy_level", int(level))


async def get_adult_level(user_id: int) -> int:
    return int(await _get_field(user_id, "adult_level", 0))


async def update_adult_level(user_id: int, level: int) -> None:
    await _set_field(user_id, "adult_level", int(level))


async def get_invites_count(user_id: int) -> int:
    return int(await _get_field(user_id, "invites_count", 0))


async def bump_invites(user_id: int) -> int:
    total = await get_invites_count(user_id) + 1
    await _set_field(user_id, "invites_count", total)
    return total


async def get_achievements(user_id: int) -> str:
    return str(await _get_field(user_id, "achievements", "") or "")


async def add_achievement(user_id: int, text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    current = await get_achievements(user_id)
    items = [a for a in current.split(",") if a]
    if text in items:
        return
    items.append(text)
    await _set_field(user_id, "achievements", ",".join(items))


async def get_current_scene(user_id: int) -> str:
    return str(await _get_field(user_id, "current_scene", "prolog_scene1") or "prolog_scene1")


async def update_current_scene(user_id: int, scene_id: str) -> None:
    await _set_field(user_id, "current_scene", scene_id)


async def reset_player(user_id: int) -> None:
    await _exec(
        "UPDATE players SET current_scene = 'prolog_scene1', ending = '',"
        " tasks_verified = 0, updated_at = ? WHERE user_id = ?",
        (utcnow(), user_id),
    )


async def verify_tasks(user_id: int) -> None:
    await _set_field(user_id, "tasks_verified", 1)


async def set_ending(user_id: int, ending: str) -> None:
    await _set_field(user_id, "ending", ending or "")


async def complete_dressage(user_id: int) -> None:
    await _set_field(user_id, "dressage_done", 1)


async def complete_adult(user_id: int) -> None:
    await _set_field(user_id, "adult_done", 1)


async def get_all_players() -> list[tuple]:
    rows = await _fetchall(
        "SELECT user_id, username, payment_tier, rolls_left, used_rolls"
        " FROM players ORDER BY user_id"
    )
    return [(r["user_id"], r["username"], r["payment_tier"],
             r["rolls_left"], r["used_rolls"]) for r in rows]


async def get_stats() -> dict[str, Any]:
    row = await _fetchone("SELECT COUNT(*) AS total_players, COALESCE(SUM(points),0) AS s"
                          " FROM players")
    orders = await _fetchone("SELECT COUNT(*) AS c FROM orders WHERE status='paid'")
    revenue = await _fetchone("SELECT COALESCE(SUM(amount_gram),0) AS g,"
                              " COALESCE(SUM(amount_rub),0) AS r FROM orders WHERE status='paid'")
    return {
        "total_players": (row["total_players"] if row else 0),
        "total_points": (row["s"] if row else 0),
        "paid_orders": (orders["c"] if orders else 0),
        "revenue_gram": (revenue["g"] if revenue else 0),
        "revenue_rub": (revenue["r"] if revenue else 0),
    }


# ---------- витрина: товары ----------

def _product_dict(r: aiosqlite.Row) -> dict[str, Any]:
    return dict(r)


async def create_product(title: str, description: str = "", photo_file_id: str = "",
                         photo_url: str = "", price_gram: float | None = None,
                         price_rub: float | None = None, category: str = "general",
                         sort: int = 0) -> int:
    return await _exec(
        "INSERT INTO products (title, description, photo_file_id, photo_url,"
        " price_gram, price_rub, category, sort, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, description, photo_file_id, photo_url, price_gram, price_rub,
         category, sort, utcnow()),
    )


async def get_product(product_id: int) -> Optional[dict[str, Any]]:
    return _row_to_dict(await _fetchone("SELECT * FROM products WHERE id = ?", (product_id,)))


async def list_products(active_only: bool = True, category: str = "") -> list[dict[str, Any]]:
    q = "SELECT * FROM products"
    conds: list[str] = []
    params: list[Any] = []
    if active_only:
        conds.append("is_active = 1")
    if category:
        conds.append("category = ?")
        params.append(category)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY sort, id"
    return [dict(r) for r in await _fetchall(q, tuple(params))]


async def update_product(product_id: int, **fields: Any) -> None:
    allowed = {"title", "description", "photo_file_id", "photo_url", "price_gram",
               "price_rub", "category", "is_active", "sort"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        return
    params.append(product_id)
    await _exec(f"UPDATE products SET {', '.join(sets)} WHERE id = ?", tuple(params))


async def delete_product(product_id: int) -> None:
    await _exec("DELETE FROM products WHERE id = ?", (product_id,))


async def toggle_product(product_id: int) -> int:
    p = await get_product(product_id)
    if not p:
        return 0
    new = 0 if p["is_active"] else 1
    await update_product(product_id, is_active=new)
    return new


# ---------- заказы ----------

async def create_order(user_id: int, username: str, product_id: int, title: str,
                       amount_gram: float | None, amount_rub: float | None,
                       promocode: str = "", provider: str = "manual",
                       pay_memo: str = "") -> int:
    return await _exec(
        "INSERT INTO orders (user_id, username, product_id, title, amount_gram,"
        " amount_rub, promocode, provider, pay_memo, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, product_id, title, amount_gram, amount_rub,
         promocode, provider, pay_memo, utcnow()),
    )


async def get_order(order_id: int) -> Optional[dict[str, Any]]:
    return _row_to_dict(await _fetchone("SELECT * FROM orders WHERE id = ?", (order_id,)))


async def list_orders(status: str = "", limit: int = 50) -> list[dict[str, Any]]:
    if status:
        rows = await _fetchall("SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?",
                               (status, limit))
    else:
        rows = await _fetchall("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


async def set_order_status(order_id: int, status: str) -> None:
    paid = utcnow() if status == "paid" else ""
    if paid:
        await _exec("UPDATE orders SET status = ?, paid_at = ? WHERE id = ?",
                    (status, paid, order_id))
    else:
        await _exec("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


async def attach_provider(order_id: int, provider_id: str, raw: str) -> None:
    await _exec("UPDATE orders SET provider_id = ?, provider_raw = ? WHERE id = ?",
                (provider_id, raw, order_id))


async def record_payment(order_id: int, provider: str, provider_payment_id: str,
                         amount: float | None, status: str, raw: str = "",
                         currency: str = "GRAM") -> None:
    await _exec(
        "INSERT INTO payments (order_id, provider, provider_payment_id, amount,"
        " currency, status, raw, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (order_id, provider, provider_payment_id, amount, currency, status, raw, utcnow()),
    )


# ---------- сессии ----------

async def create_session_request(user_id: int, username: str, kind: str,
                                 product_id: int = 0, order_id: int = 0,
                                 slot: str = "", comment: str = "") -> int:
    return await _exec(
        "INSERT INTO sessions (user_id, username, kind, product_id, order_id,"
        " slot, comment, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, kind, product_id, order_id, slot, comment, utcnow(), utcnow()),
    )


async def get_session_request(sid: int) -> Optional[dict[str, Any]]:
    return _row_to_dict(await _fetchone("SELECT * FROM sessions WHERE id = ?", (sid,)))


async def list_session_requests(status: str = "", limit: int = 50) -> list[dict[str, Any]]:
    if status:
        rows = await _fetchall("SELECT * FROM sessions WHERE status = ?"
                               " ORDER BY id DESC LIMIT ?", (status, limit))
    else:
        rows = await _fetchall("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


async def set_session_status(sid: int, status: str, admin_comment: str = "") -> None:
    await _exec("UPDATE sessions SET status = ?, admin_comment = ?, updated_at = ? WHERE id = ?",
                (status, admin_comment, utcnow(), sid))


# ---------- промокоды ----------

async def db_create_promocode(code: str, reward: str, max_uses: int = 1) -> None:
    await _exec(
        "INSERT OR REPLACE INTO promocodes (code, reward, max_uses, used, is_active, created_at)"
        " VALUES (?, ?, ?, 0, 1, ?)",
        (code.upper().strip(), reward, max_uses, utcnow()),
    )


async def db_list_promocodes() -> list[dict[str, Any]]:
    return [dict(r) for r in await _fetchall("SELECT * FROM promocodes ORDER BY code")]


async def db_get_promocode(code: str) -> Optional[dict[str, Any]]:
    return _row_to_dict(await _fetchone("SELECT * FROM promocodes WHERE code = ?",
                                        (code.upper().strip(),)))


async def db_delete_promocode(code: str) -> None:
    await _exec("DELETE FROM promocodes WHERE code = ?", (code.upper().strip(),))


async def db_use_promocode(code: str) -> Optional[dict[str, Any]]:
    """Одноразовое списание. Возвращает промокод или None, если недоступен."""
    p = await db_get_promocode(code)
    if not p or not p["is_active"] or p["used"] >= p["max_uses"]:
        return None
    await _exec("UPDATE promocodes SET used = used + 1 WHERE code = ?", (p["code"],))
    return p


# ---------- отзывы ----------

async def db_add_review(author: str, text: str) -> int:
    return await _exec(
        "INSERT INTO reviews (author_name, review_text, review_date) VALUES (?, ?, ?)",
        (author, text, time.strftime("%d.%m.%Y")),
    )


async def db_list_reviews(limit: int = 20) -> list[dict[str, Any]]:
    return [dict(r) for r in await _fetchall(
        "SELECT id, author_name, review_text, review_date FROM reviews"
        " ORDER BY id DESC LIMIT ?", (limit,))]


async def db_delete_review(rid: int) -> None:
    await _exec("DELETE FROM reviews WHERE id = ?", (rid,))


# ---------- курс GRAM ----------

async def get_gram_rate() -> float:
    if settings.gram_rub_rate > 0:
        return settings.gram_rub_rate
    row = await _fetchone("SELECT value FROM settings WHERE key = 'gram_rub_rate'")
    try:
        return float(row["value"]) if row else 0.0
    except (ValueError, TypeError):
        return 0.0


async def set_gram_rate(value: float) -> None:
    await _exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('gram_rub_rate', ?)",
                (str(value),))


async def gram_price_for(product: dict[str, Any]) -> float | None:
    """Цена товара в GRAM: явная или пересчёт из рублей по курсу."""
    if product.get("price_gram"):
        return float(product["price_gram"])
    if product.get("price_rub"):
        rate = await get_gram_rate()
        if rate > 0:
            return round(float(product["price_rub"]) / rate, 4)
    return None


# ---------- общие настройки (для минимального деплоя TONAPI_KEY + ADMIN_IDS) ----------

async def get_setting(key: str) -> str:
    row = await _fetchone("SELECT value FROM settings WHERE key = ?", (key,))
    return str(row["value"]) if row and row["value"] is not None else ""


async def set_setting(key: str, value: str) -> None:
    await _exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))


async def get_wallet_address() -> str:
    """Кошелек для TONAPI: сначала ENV, потом БД, потом пусто."""
    env_wallet = (settings.ton_wallet_address or settings.gram_wallet_address or "").strip()
    if env_wallet:
        return env_wallet
    db_wallet = await get_setting("ton_wallet_address") or await get_setting("gram_wallet_address")
    return db_wallet.strip()


async def set_wallet_address(address: str) -> None:
    address = (address or "").strip()
    if not address:
        return
    await set_setting("ton_wallet_address", address)
    await set_setting("gram_wallet_address", address)


# ---------- горячее предложение ----------

async def get_hot_offer() -> dict[str, Any]:
    """Получить текущее горячее предложение.

    Возвращает dict с полями: text, is_active, photo_file_id, price, emoji.
    Если предложения нет — возвращает dict с is_active=False.
    """
    text = await get_setting("hot_offer_text")
    is_active = await get_setting("hot_offer_active") == "1"
    photo_file_id = await get_setting("hot_offer_photo")
    price = await get_setting("hot_offer_price")
    emoji = await get_setting("hot_offer_emoji") or "🔥"
    return {
        "text": text,
        "is_active": is_active,
        "photo_file_id": photo_file_id,
        "price": price,
        "emoji": emoji,
    }


async def set_hot_offer(text: str, photo_file_id: str = "", price: str = "",
                        emoji: str = "🔥", is_active: bool = True) -> None:
    """Создать или обновить горячее предложение."""
    await set_setting("hot_offer_text", text)
    await set_setting("hot_offer_active", "1" if is_active else "0")
    await set_setting("hot_offer_photo", photo_file_id)
    await set_setting("hot_offer_price", price)
    await set_setting("hot_offer_emoji", emoji)


async def clear_hot_offer() -> None:
    """Удалить горячее предложение."""
    await set_setting("hot_offer_text", "")
    await set_setting("hot_offer_active", "0")
    await set_setting("hot_offer_photo", "")
    await set_setting("hot_offer_price", "")
