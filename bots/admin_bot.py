# -*- coding: utf-8 -*-
"""Отдельный админ-бот: витрина, заказы, сессии, промокоды, отзывы, рассылки.

Доступ только для ADMIN_IDS. Запускается своим токеном ADMIN_BOT_TOKEN
в том же процессе (main.py) или отдельно —ницы нет.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import database as db
import notify
from config import settings

log = logging.getLogger("vizitka.admin_bot")

CATEGORIES = [
    ("general", "📦 Общее"),
    ("content", "🔞 Контент"),
    ("session", "👠 Сессии"),
    ("course", "📚 Курсы"),
    ("dice", "🎲 Кубики"),
    ("extra", "✨ Extra"),
]
CAT_NAMES = dict(CATEGORIES)


# ---------- доступ ----------

class AdminGuard(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user or user.id not in settings.admin_ids:
            if isinstance(event, Message):
                await event.answer("⛔ Нет прав")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Нет прав", show_alert=True)
            return None
        return await handler(event, data)


# ---------- FSM ----------

class AddProduct(StatesGroup):
    photo = State()
    title = State()
    desc = State()
    price_gram = State()
    price_rub = State()
    category = State()
    confirm = State()


class EditValue(StatesGroup):
    value = State()


class Broadcast(StatesGroup):
    text = State()
    confirm = State()


class AddPromo(StatesGroup):
    code = State()
    reward = State()
    max_uses = State()


class AddReview(StatesGroup):
    author = State()
    text = State()


class SetRate(StatesGroup):
    value = State()


class AddDice(StatesGroup):
    username = State()
    amount = State()


class SessionComment(StatesGroup):
    text = State()


# ---------- клавиатуры ----------

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Товары", callback_data="adm:products"),
         InlineKeyboardButton(text="🧾 Заказы", callback_data="adm:orders")],
        [InlineKeyboardButton(text="👠 Сессии", callback_data="adm:sessions"),
         InlineKeyboardButton(text="🎁 Промокоды", callback_data="adm:promos")],
        [InlineKeyboardButton(text="📝 Отзывы", callback_data="adm:reviews"),
         InlineKeyboardButton(text="🎲 Кубики", callback_data="adm:dice")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"),
         InlineKeyboardButton(text="💱 Курс GRAM", callback_data="adm:rate")],
        [InlineKeyboardButton(text="📣 Рассылка", callback_data="adm:broadcast")],
    ])


def back_to(menu_cb: str = "adm:menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=menu_cb)]])


def fmt_price(p: dict) -> str:
    parts = []
    if p.get("price_gram"):
        parts.append(f"{p['price_gram']} GRAM")
    if p.get("price_rub"):
        parts.append(f"{p['price_rub']} ₽")
    return " · ".join(parts) or "цена не задана"


def product_card(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    status = "🟢" if p["is_active"] else "⚫️"
    text = (f"{status} <b>#{p['id']} {p['title']}</b>\n"
            f"📁 {CAT_NAMES.get(p['category'], p['category'])}\n"
            f"💰 {fmt_price(p)}\n"
            f"🖼 {'есть' if (p.get('photo_file_id') or p.get('photo_url')) else 'нет'}\n\n"
            f"{(p.get('description') or '')[:500]}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Название", callback_data=f"p:edit:{p['id']}:title"),
         InlineKeyboardButton(text="📝 Описание", callback_data=f"p:edit:{p['id']}:description")],
        [InlineKeyboardButton(text="🖼 Фото", callback_data=f"p:edit:{p['id']}:photo"),
         InlineKeyboardButton(text="📁 Категория", callback_data=f"p:edit:{p['id']}:category")],
        [InlineKeyboardButton(text="💎 Цена GRAM", callback_data=f"p:edit:{p['id']}:price_gram"),
         InlineKeyboardButton(text="💰 Цена ₽", callback_data=f"p:edit:{p['id']}:price_rub")],
        [InlineKeyboardButton(text="🔄 Вкл/Выкл", callback_data=f"p:toggle:{p['id']}"),
         InlineKeyboardButton(text="🗑 Удалить", callback_data=f"p:del:{p['id']}")],
        [InlineKeyboardButton(text="◀️ К товарам", callback_data="adm:products")],
    ])
    return text, kb


# ---------- /start ----------

async def cmd_start(message: Message) -> None:
    await message.answer("🔧 <b>Админ-панель</b>\n\nВитрина, заказы, сессии — всё здесь:",
                         reply_markup=main_menu())


async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Отменено", reply_markup=main_menu())


async def cb_menu(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("🔧 <b>Админ-панель</b>", reply_markup=main_menu())
    await cb.answer()


async def cb_photo_id(message: Message) -> None:
    """Любое фото боту — вернуть file_id (пригодится для витрины)."""
    await message.answer(f"🖼 <code>{message.photo[-1].file_id}</code>")


# ---------- товары ----------

async def cb_products(cb: CallbackQuery) -> None:
    products = await db.list_products(active_only=False)
    if not products:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить товар", callback_data="p:add")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="adm:menu")]])
        await cb.message.edit_text("📭 Товаров пока нет", reply_markup=kb)
        await cb.answer()
        return
    rows = []
    for p in products:
        mark = "🟢" if p["is_active"] else "⚫️"
        rows.append([InlineKeyboardButton(
            text=f"{mark} #{p['id']} {p['title'][:30]} — {fmt_price(p)[:25]}",
            callback_data=f"p:view:{p['id']}")])
    rows.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data="p:add")])
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm:menu")])
    await cb.message.edit_text(f"🛍 <b>Товары ({len(products)})</b>",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


async def cb_product_view(cb: CallbackQuery) -> None:
    pid = int(cb.data.split(":")[2])
    p = await db.get_product(pid)
    if not p:
        await cb.answer("Товар не найден", show_alert=True)
        return
    text, kb = product_card(p)
    try:
        await cb.message.delete()
    except Exception:
        pass
    if p.get("photo_file_id"):
        await cb.message.answer_photo(p["photo_file_id"], caption=text, reply_markup=kb)
    else:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


async def cb_product_toggle(cb: CallbackQuery) -> None:
    pid = int(cb.data.split(":")[2])
    new = await db.toggle_product(pid)
    await cb.answer("🟢 Включён" if new else "⚫️ Выключен")
    p = await db.get_product(pid)
    if p:
        text, kb = product_card(p)
        try:
            await cb.message.edit_caption(caption=text, reply_markup=kb)
        except Exception:
            try:
                await cb.message.edit_text(text, reply_markup=kb)
            except Exception:
                pass


async def cb_product_del(cb: CallbackQuery) -> None:
    pid = int(cb.data.split(":")[2])
    await db.delete_product(pid)
    await cb.answer("Удалён")
    await cb_products(cb)


async def cb_product_add(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddProduct.photo)
    await cb.message.answer("➕ <b>Новый товар</b>\n\nШаг 1/6: пришли <b>фото</b> или отправь «-», чтобы без фото.")
    await cb.answer()


async def ap_photo(message: Message, state: FSMContext) -> None:
    if message.photo:
        await state.update_data(photo_file_id=message.photo[-1].file_id)
    elif (message.text or "").strip() not in ("-", "нет", "0"):
        await message.answer("Пришли фото или «-»")
        return
    await state.set_state(AddProduct.title)
    await message.answer("Шаг 2/6: <b>название</b> товара:")


async def ap_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer("Название слишком короткое")
        return
    await state.update_data(title=title)
    await state.set_state(AddProduct.desc)
    await message.answer("Шаг 3/6: <b>описание</b> (или «-»):")


async def ap_desc(message: Message, state: FSMContext) -> None:
    desc = (message.text or "").strip()
    await state.update_data(description="" if desc == "-" else desc)
    await state.set_state(AddProduct.price_gram)
    await message.answer("Шаг 4/6: <b>цена в GRAM</b> (число или «-»):")


def _parse_price(text: str) -> Optional[float]:
    t = (text or "").strip().replace(",", ".")
    if t in ("-", "нет", "0", ""):
        return None
    try:
        v = float(t)
        return v if v > 0 else None
    except ValueError:
        return "bad"  # type: ignore[return-value]


async def ap_price_gram(message: Message, state: FSMContext) -> None:
    v = _parse_price(message.text or "")
    if v == "bad":
        await message.answer("Нужно число или «-»")
        return
    await state.update_data(price_gram=v)
    await state.set_state(AddProduct.price_rub)
    await message.answer("Шаг 5/6: <b>цена в рублях</b> (число или «-»):")


async def ap_price_rub(message: Message, state: FSMContext) -> None:
    v = _parse_price(message.text or "")
    if v == "bad":
        await message.answer("Нужно число или «-»")
        return
    await state.update_data(price_rub=v)
    await state.set_state(AddProduct.category)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"p:cat:{code}")]
        for code, name in CATEGORIES])
    await message.answer("Шаг 6/6: выбери <b>категорию</b>:", reply_markup=kb)


async def ap_category(cb: CallbackQuery, state: FSMContext) -> None:
    code = cb.data.split(":")[2]
    data = await state.get_data()
    data["category"] = code
    await state.update_data(category=code)
    text = (f"Проверь товар:\n\n<b>{data.get('title')}</b>\n"
            f"📁 {CAT_NAMES.get(code, code)}\n"
            f"💰 {data.get('price_gram') or '—'} GRAM · {data.get('price_rub') or '—'} ₽\n"
            f"🖼 {'есть' if data.get('photo_file_id') else 'нет'}\n\n"
            f"{(data.get('description') or '')[:300]}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="p:publish"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="adm:products")]])
    await state.set_state(AddProduct.confirm)
    if data.get("photo_file_id"):
        await cb.message.answer_photo(data["photo_file_id"], caption=text, reply_markup=kb)
    else:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


async def ap_publish(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    pid = await db.create_product(
        title=data.get("title", "Без названия"),
        description=data.get("description", ""),
        photo_file_id=data.get("photo_file_id", ""),
        price_gram=data.get("price_gram"),
        price_rub=data.get("price_rub"),
        category=data.get("category", "general"),
    )
    await state.clear()
    await cb.message.answer(f"✅ Товар <b>#{pid}</b> опубликован в витрине!")
    await cb.answer()
    await cb_products(cb)


# --- редактирование ---

EDIT_LABELS = {"title": "название", "description": "описание", "photo": "фото",
               "price_gram": "цену в GRAM", "price_rub": "цену в рублях",
               "category": "категорию"}


async def cb_product_edit(cb: CallbackQuery, state: FSMContext) -> None:
    _, _, pid, field = cb.data.split(":")
    await state.clear()
    await state.update_data(pid=int(pid), field=field)
    await state.set_state(EditValue.value)
    if field == "category":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"p:setcat:{pid}:{code}")]
            for code, name in CATEGORIES])
        await cb.message.answer("Выбери категорию:", reply_markup=kb)
    elif field == "photo":
        await cb.message.answer("Пришли новое фото (или «-», чтобы убрать):")
    else:
        await cb.message.answer(f"Введи новое значение: <b>{EDIT_LABELS.get(field, field)}</b>")
    await cb.answer()


async def ev_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    pid, field = data["pid"], data["field"]
    if field == "photo":
        if message.photo:
            await db.update_product(pid, photo_file_id=message.photo[-1].file_id)
        elif (message.text or "").strip() == "-":
            await db.update_product(pid, photo_file_id="", photo_url="")
        else:
            await message.answer("Пришли фото или «-»")
            return
    elif field in ("price_gram", "price_rub"):
        v = _parse_price(message.text or "")
        if v == "bad":
            await message.answer("Нужно число или «-»")
            return
        await db.update_product(pid, **{field: v})
    else:
        await db.update_product(pid, **{field: (message.text or "").strip()})
    await state.clear()
    p = await db.get_product(pid)
    await message.answer("✅ Сохранено")
    if p:
        text, kb = product_card(p)
        await message.answer(text, reply_markup=kb)


async def cb_product_setcat(cb: CallbackQuery, state: FSMContext) -> None:
    _, _, pid, code = cb.data.split(":")
    await db.update_product(int(pid), category=code)
    await state.clear()
    await cb.answer("✅ Категория обновлена")
    p = await db.get_product(int(pid))
    if p:
        text, kb = product_card(p)
        await cb.message.answer(text, reply_markup=kb)


# ---------- заказы ----------

def order_card(o: dict) -> tuple[str, InlineKeyboardMarkup | None]:
    user = f"@{o['username']}" if o.get("username") else f"id {o['user_id']}"
    amount = []
    if o.get("amount_gram"):
        amount.append(f"{o['amount_gram']} GRAM")
    if o.get("amount_rub"):
        amount.append(f"{o['amount_rub']} ₽")
    text = (f"🧾 <b>Заказ #{o['id']}</b> [{o['status']}]\n"
            f"👤 {user}\n📦 {o.get('title')}\n"
            f"💰 {' · '.join(amount) or '—'}\n"
            f"🔑 Мемо: <code>{o.get('pay_memo')}</code>\n"
            f"📅 {o.get('created_at')}")
    kb = None
    if o["status"] == "pending":
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"order:approve:{o['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"order:reject:{o['id']}")]])
    return text, kb


async def cb_orders(cb: CallbackQuery) -> None:
    orders = await db.list_orders(limit=15)
    pending = [o for o in orders if o["status"] == "pending"]
    rows = []
    for o in orders:
        mark = {"pending": "⏳", "paid": "✅"}.get(o["status"], "▪️")
        rows.append([InlineKeyboardButton(
            text=f"{mark} #{o['id']} {o.get('title','')[:22]}",
            callback_data=f"order:view:{o['id']}")])
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm:menu")])
    await cb.message.edit_text(f"🧾 <b>Заказы</b> (ожидают: {len(pending)})",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


async def cb_order_view(cb: CallbackQuery) -> None:
    oid = int(cb.data.split(":")[2])
    o = await db.get_order(oid)
    if not o:
        await cb.answer("Не найден", show_alert=True)
        return
    text, kb = order_card(o)
    rows = (kb.inline_keyboard if kb else []) + [[
        InlineKeyboardButton(text="◀️ К заказам", callback_data="adm:orders")]]
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


def _dice_qty_from_title(title: str) -> int:
    m = re.search(r"[×xX](\d+)", title or "")
    return int(m.group(1)) if m else 0


async def fulfill_order(o: dict) -> str:
    """Автовыдача после оплаты. Возвращает текст для пользователя."""
    p = await db.get_product(o.get("product_id") or 0)
    if p and p.get("category") == "dice":
        qty = _dice_qty_from_title(p.get("title", "")) or _dice_qty_from_title(o.get("title", "")) or 1
        left = await db.get_rolls_left(o["user_id"])
        await db.set_rolls_left(o["user_id"], left + qty)
        return (f"🎲 Оплата подтверждена! Тебе начислено бросков: <b>{qty}</b>.\n"
                f"Жми «🎲 КУБИКИ» в боте и играй!")
    return ("✅ Оплата заказа <b>#%(oid)s</b> (%(title)s) подтверждена!\n\n"
            "Напиши в ЛС @%(contact)s — Богиня выдаст доступ." % {
                "oid": o["id"], "title": o.get("title"),
                "contact": settings.contact_username})


async def cb_order_approve(cb: CallbackQuery) -> None:
    oid = int(cb.data.split(":")[2])
    o = await db.get_order(oid)
    if not o:
        await cb.answer("Не найден", show_alert=True)
        return
    if o["status"] == "paid":
        await cb.answer("Уже оплачен")
        return
    await db.set_order_status(oid, "paid")
    user_text = await fulfill_order(o)
    await notify.notify_user(o["user_id"], user_text)
    await cb.answer("✅ Подтверждён, пользователь уведомлён")
    o = await db.get_order(oid)
    assert o
    text, _ = order_card(o)
    await cb.message.edit_text(text + "\n\n✅ Оплачен", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ К заказам", callback_data="adm:orders")]]))


async def cb_order_reject(cb: CallbackQuery) -> None:
    oid = int(cb.data.split(":")[2])
    o = await db.get_order(oid)
    if not o:
        await cb.answer("Не найден", show_alert=True)
        return
    await db.set_order_status(oid, "cancelled")
    await notify.notify_user(o["user_id"],
                             f"❌ Заказ <b>#{oid}</b> отклонён. По вопросам — ЛС @{settings.contact_username}")
    await cb.answer("Отклонён")
    await cb_orders(cb)


# ---------- сессии ----------

def session_card(s: dict) -> tuple[str, InlineKeyboardMarkup | None]:
    user = f"@{s['username']}" if s.get("username") else f"id {s['user_id']}"
    kind = "⚡️ МГНОВЕННАЯ" if s["kind"] == "instant" else f"📅 {s.get('slot') or 'время не указано'}"
    text = (f"👠 <b>Сессия #{s['id']}</b> [{s['status']}]\n"
            f"👤 {user} (<code>{s['user_id']}</code>)\n{kind}\n"
            f"💬 {s.get('comment') or '—'}\n📅 {s.get('created_at')}")
    kb = None
    if s["status"] == "new":
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Принять", callback_data=f"sess:accept:{s['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"sess:decline:{s['id']}")]])
    return text, kb


async def cb_sessions(cb: CallbackQuery) -> None:
    items = await db.list_session_requests(limit=15)
    new = [s for s in items if s["status"] == "new"]
    rows = []
    for s in items:
        mark = {"new": "🆕", "accepted": "✅", "declined": "❌", "done": "🏁"}.get(s["status"], "▪️")
        rows.append([InlineKeyboardButton(
            text=f"{mark} #{s['id']} {s.get('username') or s['user_id']} ({s['kind']})",
            callback_data=f"sess:view:{s['id']}")])
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm:menu")])
    await cb.message.edit_text(f"👠 <b>Заявки на сессии</b> (новые: {len(new)})",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


async def cb_session_view(cb: CallbackQuery) -> None:
    sid = int(cb.data.split(":")[2])
    s = await db.get_session_request(sid)
    if not s:
        await cb.answer("Не найдена", show_alert=True)
        return
    text, kb = session_card(s)
    rows = (kb.inline_keyboard if kb else []) + [[
        InlineKeyboardButton(text="◀️ К сессиям", callback_data="adm:sessions")]]
    if s["status"] == "accepted":
        rows.insert(0, [InlineKeyboardButton(text="🏁 Завершить", callback_data=f"sess:done:{s['id']}")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


async def cb_session_accept(cb: CallbackQuery, state: FSMContext) -> None:
    sid = int(cb.data.split(":")[2])
    await state.clear()
    await state.update_data(sid=sid)
    await state.set_state(SessionComment.text)
    await cb.message.answer(f"✅ Принимаешь сессию <b>#{sid}</b>.\n\n"
                            "Напиши комментарий для пользователя (время, что делать) или «-»:")
    await cb.answer()


async def sess_comment(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    sid = data["sid"]
    comment = (message.text or "").strip()
    comment = "" if comment == "-" else comment
    await db.set_session_status(sid, "accepted", comment)
    s = await db.get_session_request(sid)
    await state.clear()
    await message.answer(f"✅ Сессия #{sid} принята, пользователь уведомлён.")
    if s:
        await notify.notify_user(
            s["user_id"],
            f"👠 <b>Сессия #{sid} подтверждена!</b>\n\n"
            f"{comment}\n\nПиши в ЛС @{settings.contact_username} — Богиня ждёт.")


async def cb_session_decline(cb: CallbackQuery) -> None:
    sid = int(cb.data.split(":")[2])
    await db.set_session_status(sid, "declined")
    s = await db.get_session_request(sid)
    if s:
        await notify.notify_user(s["user_id"], f"❌ Заявка на сессию #{sid} отклонена. "
                                                f"По вопросам — ЛС @{settings.contact_username}")
    await cb.answer("Отклонена")
    await cb_sessions(cb)


async def cb_session_done(cb: CallbackQuery) -> None:
    sid = int(cb.data.split(":")[2])
    await db.set_session_status(sid, "done")
    await cb.answer("🏁 Завершена")
    await cb_sessions(cb)


# ---------- промокоды ----------

def _legacy_store():
    try:
        from legacy_loader import load_legacy
        return load_legacy().active_promocodes
    except Exception:
        return None


async def cb_promos(cb: CallbackQuery) -> None:
    promos = await db.db_list_promocodes()
    rows = []
    for p in promos:
        mark = "🟢" if (p["is_active"] and p["used"] < p["max_uses"]) else "⚫️"
        rows.append([InlineKeyboardButton(
            text=f"{mark} {p['code']} ({p['used']}/{p['max_uses']})",
            callback_data=f"promo:del:{p['code']}")])
    rows.append([InlineKeyboardButton(text="➕ Создать", callback_data="promo:add")])
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm:menu")])
    await cb.message.edit_text("🎁 <b>Промокоды</b> (нажми, чтобы удалить):",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


async def cb_promo_add(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddPromo.code)
    await cb.message.answer("➕ <b>Промокод.</b> Шаг 1/3: введи КОД:")
    await cb.answer()


async def promo_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip().upper()
    if len(code) < 2:
        await message.answer("Код слишком короткий")
        return
    await state.update_data(code=code)
    await state.set_state(AddPromo.reward)
    await message.answer("Шаг 2/3: введи <b>награду</b> (текст для пользователя):")


async def promo_reward(message: Message, state: FSMContext) -> None:
    reward = (message.text or "").strip()
    if len(reward) < 2:
        await message.answer("Награда слишком короткая")
        return
    await state.update_data(reward=reward)
    await state.set_state(AddPromo.max_uses)
    await message.answer("Шаг 3/3: сколько <b>активаций</b>? (число, 1 = одноразовый):")


async def promo_max_uses(message: Message, state: FSMContext) -> None:
    try:
        n = max(1, int((message.text or "1").strip()))
    except ValueError:
        await message.answer("Нужно число")
        return
    data = await state.get_data()
    await db.db_create_promocode(data["code"], data["reward"], n)
    store = _legacy_store()
    if store is not None:
        store[data["code"]] = {"reward": data["reward"]}
    await state.clear()
    await message.answer(f"✅ Промокод <code>{data['code']}</code> создан ({n} шт.)",
                         reply_markup=main_menu())


async def cb_promo_del(cb: CallbackQuery) -> None:
    code = cb.data.split(":")[2]
    await db.db_delete_promocode(code)
    store = _legacy_store()
    if store is not None and code in store:
        try:
            del store[code]
        except KeyError:
            pass
    await cb.answer(f"{code} удалён")
    await cb_promos(cb)


# ---------- отзывы ----------

async def cb_reviews(cb: CallbackQuery) -> None:
    items = await db.db_list_reviews(limit=10)
    rows = []
    for r in items:
        rows.append([InlineKeyboardButton(
            text=f"❌ #{r['id']} {r['author_name']}: {r['review_text'][:25]}",
            callback_data=f"rev:del:{r['id']}")])
    rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data="rev:add")])
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm:menu")])
    await cb.message.edit_text("📝 <b>Отзывы</b> (нажми, чтобы удалить):",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


async def cb_review_add(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddReview.author)
    await cb.message.answer("✍️ <b>Отзыв.</b> Шаг 1/2: имя автора:")
    await cb.answer()


async def review_author(message: Message, state: FSMContext) -> None:
    await state.update_data(author=(message.text or "").strip())
    await state.set_state(AddReview.text)
    await message.answer("Шаг 2/2: текст отзыва:")


async def review_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await db.db_add_review(data["author"], (message.text or "").strip())
    await state.clear()
    await message.answer("✅ Отзыв добавлен", reply_markup=main_menu())


async def cb_review_del(cb: CallbackQuery) -> None:
    rid = int(cb.data.split(":")[2])
    await db.db_delete_review(rid)
    await cb.answer("Удалён")
    await cb_reviews(cb)


# ---------- кубики ----------

async def cb_dice(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddDice.username)
    await cb.message.answer("🎲 <b>Начислить броски.</b> Шаг 1/2: username (без @):")
    await cb.answer()


async def dice_username(message: Message, state: FSMContext) -> None:
    uname = (message.text or "").strip().lstrip("@").lower()
    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT user_id, username FROM players WHERE LOWER(username) = ?",
                                (uname,)) as cur:
            row = await cur.fetchone()
    if not row:
        await message.answer("❌ Пользователь не найден в базе")
        return
    await state.update_data(uid=row["user_id"], uname=row["username"])
    await state.set_state(AddDice.amount)
    await message.answer(f"Шаг 2/2: сколько бросков начислить @{row['username']}?")


async def dice_amount(message: Message, state: FSMContext) -> None:
    try:
        n = int((message.text or "").strip())
        assert n > 0
    except (ValueError, AssertionError):
        await message.answer("Нужно положительное число")
        return
    data = await state.get_data()
    left = await db.get_rolls_left(data["uid"])
    await db.set_rolls_left(data["uid"], left + n)
    await state.clear()
    await message.answer(f"✅ @{data['uname']}: +{n} бросков (всего {left + n})",
                         reply_markup=main_menu())
    await notify.notify_user(data["uid"], f"🎲 Богиня начислила тебе <b>{n}</b> бросков!\n\n"
                                          "Жми «🎲 КУБИКИ» в боте.")


# ---------- статистика / курс / рассылка ----------

async def cb_stats(cb: CallbackQuery) -> None:
    s = await db.get_stats()
    pend_o = await db.list_orders(status="pending", limit=1000)
    new_s = await db.list_session_requests(status="new", limit=1000)
    await cb.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Игроков: {s['total_players']}\n"
        f"⭐ Баллов выдано: {s['total_points']}\n"
        f"🧾 Оплаченных заказов: {s['paid_orders']}\n"
        f"💎 Выручка: {s['revenue_gram']} GRAM · {s['revenue_rub']} ₽\n"
        f"⏳ Ожидают оплаты: {len(pend_o)}\n"
        f"🆕 Новых сессий: {len(new_s)}",
        reply_markup=back_to())
    await cb.answer()


async def cb_rate(cb: CallbackQuery, state: FSMContext) -> None:
    rate = await db.get_gram_rate()
    await state.clear()
    await state.set_state(SetRate.value)
    await cb.message.answer(f"💱 Текущий курс: <b>{rate or 'не задан'}</b> ₽ за 1 GRAM\n\n"
                            "Введи новый курс (число) или «-», чтобы оставить:")
    await cb.answer()


async def rate_value(message: Message, state: FSMContext) -> None:
    t = (message.text or "").strip()
    if t != "-":
        try:
            v = float(t.replace(",", "."))
            assert v > 0
        except (ValueError, AssertionError):
            await message.answer("Нужно положительное число или «-»")
            return
        await db.set_gram_rate(v)
        await message.answer(f"✅ Курс: {v} ₽ / GRAM", reply_markup=main_menu())
    else:
        await message.answer("Оставлен без изменений", reply_markup=main_menu())
    await state.clear()


async def cb_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Broadcast.text)
    await cb.message.answer("📣 <b>Рассылка.</b> Пришли текст для всех игроков:")
    await cb.answer()


async def bc_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text or "")
    await state.set_state(Broadcast.confirm)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Отправить всем", callback_data="bc:go"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="adm:menu")]])
    await message.answer(f"Предпросмотр:\n\n{message.text}\n\nОтправляем?", reply_markup=kb)


async def cb_broadcast_go(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    players = await db.get_all_players()
    ok, fail = 0, 0
    await cb.message.edit_text(f"🚀 Рассылка {len(players)} игрокам...")
    for uid, *_ in players:
        if await notify.notify_user(uid, data.get("text", "")):
            ok += 1
        else:
            fail += 1
    await cb.message.answer(f"✅ Готово: доставлено {ok}, ошибок {fail}", reply_markup=main_menu())
    await cb.answer()


# ---------- регистрация ----------

def build_admin_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.admin_bot_token,
              default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.message.middleware(AdminGuard())
    dp.callback_query.middleware(AdminGuard())

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_cancel, Command("cancel"))
    dp.message.register(cb_photo_id, F.photo)

    dp.callback_query.register(cb_menu, F.data == "adm:menu")
    dp.callback_query.register(cb_products, F.data == "adm:products")
    dp.callback_query.register(cb_orders, F.data == "adm:orders")
    dp.callback_query.register(cb_sessions, F.data == "adm:sessions")
    dp.callback_query.register(cb_promos, F.data == "adm:promos")
    dp.callback_query.register(cb_reviews, F.data == "adm:reviews")
    dp.callback_query.register(cb_stats, F.data == "adm:stats")
    dp.callback_query.register(cb_rate, F.data == "adm:rate")
    dp.callback_query.register(cb_broadcast, F.data == "adm:broadcast")
    dp.callback_query.register(cb_dice, F.data == "adm:dice")

    dp.callback_query.register(cb_product_view, F.data.startswith("p:view:"))
    dp.callback_query.register(cb_product_toggle, F.data.startswith("p:toggle:"))
    dp.callback_query.register(cb_product_del, F.data.startswith("p:del:"))
    dp.callback_query.register(cb_product_add, F.data == "p:add")
    dp.callback_query.register(ap_category, F.data.startswith("p:cat:"), AddProduct.category)
    dp.callback_query.register(ap_publish, F.data == "p:publish", AddProduct.confirm)
    dp.callback_query.register(cb_product_edit, F.data.startswith("p:edit:"))
    dp.callback_query.register(cb_product_setcat, F.data.startswith("p:setcat:"))
    dp.message.register(ap_photo, AddProduct.photo)
    dp.message.register(ap_title, AddProduct.title)
    dp.message.register(ap_desc, AddProduct.desc)
    dp.message.register(ap_price_gram, AddProduct.price_gram)
    dp.message.register(ap_price_rub, AddProduct.price_rub)
    dp.message.register(ev_value, EditValue.value)

    dp.callback_query.register(cb_order_view, F.data.startswith("order:view:"))
    dp.callback_query.register(cb_order_approve, F.data.startswith("order:approve:"))
    dp.callback_query.register(cb_order_reject, F.data.startswith("order:reject:"))

    dp.callback_query.register(cb_session_view, F.data.startswith("sess:view:"))
    dp.callback_query.register(cb_session_accept, F.data.startswith("sess:accept:"))
    dp.callback_query.register(cb_session_decline, F.data.startswith("sess:decline:"))
    dp.callback_query.register(cb_session_done, F.data.startswith("sess:done:"))
    dp.message.register(sess_comment, SessionComment.text)

    dp.callback_query.register(cb_promo_add, F.data == "promo:add")
    dp.callback_query.register(cb_promo_del, F.data.startswith("promo:del:"))
    dp.message.register(promo_code, AddPromo.code)
    dp.message.register(promo_reward, AddPromo.reward)
    dp.message.register(promo_max_uses, AddPromo.max_uses)

    dp.callback_query.register(cb_review_add, F.data == "rev:add")
    dp.callback_query.register(cb_review_del, F.data.startswith("rev:del:"))
    dp.message.register(review_author, AddReview.author)
    dp.message.register(review_text, AddReview.text)

    dp.callback_query.register(cb_broadcast_go, F.data == "bc:go", Broadcast.confirm)
    dp.message.register(bc_text, Broadcast.text)
    dp.message.register(rate_value, SetRate.value)
    dp.message.register(dice_username, AddDice.username)
    dp.message.register(dice_amount, AddDice.amount)

    return bot, dp


async def run_admin_bot() -> None:
    if not settings.admin_bot_token:
        log.warning("admin_bot: ADMIN_BOT_TOKEN пуст — пропуск")
        return
    bot, dp = build_admin_bot()
    log.info("admin_bot: polling стартовал")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
