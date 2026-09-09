# -*- coding: utf-8 -*-
"""Веб-витрина (Telegram Mini App) + REST API.

Маршруты:
- GET / — Mini App HTML
- GET /api/products — список товаров
- GET /api/products/{id}
- POST /api/orders/create — создать заказ (требует Telegram auth)
- GET /api/orders/{id} — статус заказа
- POST /api/orders/{id}/check — проверить оплату через TONAPI/GRAM API
- POST /api/payments/webhook — webhook от GRAM API
- GET /api/media/{file_id} — прокси фото из Telegram (кэш)
- POST /api/sessions/request — заявка на сессию
- GET /api/reviews
- GET /api/config — публичная конфигурация (contact, payment_link и т.д.)
- GET /admin — веб-админка (требует ADMIN_PANEL_TOKEN)
- /api/admin/* — админ API
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web

from config import settings, PROJECT_ROOT
import database as db
from .auth import current_user, require_user, require_admin, WebUser
import payments
from payments.gram import create_invoice as gram_create_invoice, get_invoice_status
from notify import bot_api

log = logging.getLogger("vizitka.web")

# ---------- helpers ----------

async def _get_file_path(file_id: str) -> str | None:
    if not settings.bot_token or not file_id:
        return None
    res = await bot_api(settings.bot_token, "getFile", file_id=file_id)
    if not res.get("ok"):
        return None
    return res.get("result", {}).get("file_path")


async def _download_telegram_file(file_path: str, dest: Path) -> bool:
    if not settings.bot_token:
        return False
    url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file_path}"
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=30) as resp:
                if resp.status != 200:
                    return False
                data = await resp.read()
                dest.write_bytes(data)
                return True
    except Exception as e:
        log.warning("download file %s failed: %s", file_path, e)
        return False


# ---------- public routes ----------

async def handle_root(request: web.Request) -> web.Response:
    # Отдаем Mini App HTML — если есть web/static/index.html, иначе встроенный
    static_index = PROJECT_ROOT / "web" / "static" / "index.html"
    if static_index.exists():
        return web.FileResponse(static_index)

    # Встроенный минимальный фронт
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Витрина — @{settings.contact_username}</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{{font-family:system-ui,Arial,sans-serif;background:#0f0f0f;color:#fff;margin:0;padding:16px}}
h1{{font-size:22px}}
.card{{background:#1e1e1e;border-radius:16px;padding:14px;margin:12px 0;display:flex;gap:12px;align-items:center}}
.card img{{width:72px;height:72px;object-fit:cover;border-radius:12px;background:#333}}
.price{{color:#8aff8a;font-weight:600}}
.btn{{background:#7c4dff;color:#fff;border:0;border-radius:12px;padding:10px 16px;font-weight:600;cursor:pointer}}
.btn:disabled{{opacity:.5}}
.badge{{font-size:12px;background:#333;padding:2px 8px;border-radius:8px}}
#products{{max-width:720px;margin:0 auto}}
.header{{max-width:720px;margin:0 auto 16px;display:flex;justify-content:space-between;align-items:center}}
a{{color:#8ab4ff}}
</style>
</head>
<body>
<div class="header">
<div><h1>🛍 Витрина</h1><div style="opacity:.7">@{settings.contact_username} · <a href="https://t.me/{settings.contact_username}" target="_blank">ЛС Богини</a></div></div>
<div id="user"></div>
</div>
<div id="products">Загрузка…</div>
<script>
const tg = window.Telegram?.WebApp; if(tg){{tg.ready(); tg.expand();}}
let initData = tg?.initData || new URLSearchParams(location.search).get('initData') || '';
function headers(){{ const h={{'Content-Type':'application/json'}}; if(initData) h['X-Telegram-Init-Data']=initData; return h; }}
async function load() {{
  const r = await fetch('/api/products', {{headers: headers()}});
  const j = await r.json();
  const cont = document.getElementById('products');
  if(!j.ok){{ cont.innerHTML='Ошибка: '+j.error; return; }}
  if(!j.products.length){{ cont.innerHTML='Товаров пока нет'; return; }}
  cont.innerHTML='';
  j.products.forEach(p=>{{
    const price = (p.price_gram? p.price_gram+' GRAM ' : '') + (p.price_rub? p.price_rub+' ₽':'');
    const img = p.photo_file_id? `/api/media/${{p.photo_file_id}}` : (p.photo_url||'');
    const el = document.createElement('div'); el.className='card';
    el.innerHTML=`<img src="${{img}}" onerror="this.style.display='none'"><div style="flex:1"><div><b>#${{p.id}} ${{p.title}}</b> <span class="badge">${{p.category}}</span></div><div style="opacity:.8;font-size:13px;margin:4px 0">${{p.description||''}}</div><div class="price">${{price||'цена не указана'}}</div></div><button class="btn" onclick="order(${{p.id}})">Купить</button>`;
    cont.appendChild(el);
  }});
}}
async function order(id){{
  const btn = event.target; btn.disabled=true; btn.textContent='...';
  try{{
    const r = await fetch('/api/orders/create', {{method:'POST', headers: headers(), body: JSON.stringify({{product_id:id}})}});
    const j = await r.json();
    if(!j.ok){{ alert('Ошибка: '+(j.error||'unknown')); return; }}
    let txt = `Заказ #${{j.order.id}}\\nСумма: ${{j.order.amount_gram||j.order.amount_rub}} ${{j.invoice.mode}}\\nМемо: ${{j.order.pay_memo}}\\n`;
    if(j.invoice.pay_url) txt+=`Ссылка: ${{j.invoice.pay_url}}\\n`;
    if(j.invoice.address) txt+=`Адрес: ${{j.invoice.address}}\\nМемо: ${{j.invoice.memo}}\\n`;
    if(j.invoice.note) txt+=`\\n${{j.invoice.note}}`;
    alert(txt);
    if(j.invoice.pay_url) window.open(j.invoice.pay_url, '_blank');
  }}finally{{btn.disabled=false; btn.textContent='Купить';}}
}}
load();
if(tg?.initDataUnsafe?.user) document.getElementById('user').textContent = '@'+(tg.initDataUnsafe.user.username||tg.initDataUnsafe.user.first_name);
</script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def handle_config(request: web.Request) -> web.Response:
    return web.json_response({
        "ok": True,
        "contact_username": settings.contact_username,
        "payment_link": settings.payment_link,
        "channels": settings.channels,
        "payments_mode": settings.payments_mode,
        "gram_wallet_address": settings.gram_wallet_address or settings.ton_wallet_address,
        "ton_wallet_address": settings.ton_wallet_address or settings.gram_wallet_address,
        "public_url": settings.public_url,
        "webapp_url": settings.webapp_url,
    })


async def handle_products(request: web.Request) -> web.Response:
    category = request.query.get("category", "")
    active_only = request.query.get("all") != "1"
    products = await db.list_products(active_only=active_only, category=category)
    # Добавляем gram price если нужно
    out = []
    for p in products:
        pp = dict(p)
        # если цена в GRAM не задана, но есть RUB и курс — посчитаем
        if not pp.get("price_gram") and pp.get("price_rub"):
            g = await db.gram_price_for(pp)
            if g:
                pp["price_gram_calculated"] = g
        out.append(pp)
    return web.json_response({"ok": True, "products": out})


async def handle_product_one(request: web.Request) -> web.Response:
    try:
        pid = int(request.match_info["id"])
    except:
        return web.json_response({"ok": False, "error": "bad_id"}, status=400)
    p = await db.get_product(pid)
    if not p:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    return web.json_response({"ok": True, "product": dict(p)})


async def handle_reviews(request: web.Request) -> web.Response:
    items = await db.db_list_reviews(limit=50)
    return web.json_response({"ok": True, "reviews": items})


async def handle_media(request: web.Request) -> web.Response:
    file_id = request.match_info["file_id"]
    # кэш
    cache_dir = Path(settings.media_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # file_id может содержать символы, делаем безопасное имя
    safe_name = "".join(c for c in file_id if c.isalnum() or c in ("-", "_"))[:80]
    cached = cache_dir / f"{safe_name}.jpg"
    if cached.exists() and cached.stat().st_size > 0:
        return web.FileResponse(cached)

    file_path = await _get_file_path(file_id)
    if not file_path:
        return web.json_response({"ok": False, "error": "file_not_found"}, status=404)
    ok = await _download_telegram_file(file_path, cached)
    if ok and cached.exists():
        return web.FileResponse(cached)
    # редирект на Telegram напрямую
    url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file_path}"
    return web.HTTPFound(url)


@require_user
async def handle_orders_create(request: web.Request) -> web.Response:
    user: WebUser = request["user"]
    try:
        data = await request.json()
    except:
        data = {}
    product_id = int(data.get("product_id") or 0)
    if not product_id:
        return web.json_response({"ok": False, "error": "product_id required"}, status=400)

    product = await db.get_product(product_id)
    if not product or not product.get("is_active"):
        return web.json_response({"ok": False, "error": "product_not_found"}, status=404)

    # промокод опционально
    promocode = (data.get("promocode") or "").strip().upper()

    # цены
    amount_gram = product.get("price_gram")
    amount_rub = product.get("price_rub")
    if not amount_gram and amount_rub:
        amount_gram = await db.gram_price_for(product)

    # применяем промокод если есть — для примера скидка 100%? Пока просто помечаем
    if promocode:
        promo = await db.db_get_promocode(promocode)
        if promo and promo["is_active"] and promo["used"] < promo["max_uses"]:
            # тут можно логику скидок, пока просто используем
            await db.db_use_promocode(promocode)
        else:
            return web.json_response({"ok": False, "error": "bad_promocode"}, status=400)

    # создаем мемо
    # ORDER-<id> будет после создания, пока временный
    pay_memo = f"ORDER-{int(time.time())}-{user.id}"

    order_id = await db.create_order(
        user_id=user.id,
        username=user.username or user.first_name,
        product_id=product_id,
        title=product.get("title", ""),
        amount_gram=amount_gram,
        amount_rub=amount_rub,
        promocode=promocode,
        provider=settings.payments_mode,
        pay_memo=pay_memo,
    )
    # обновляем мемо на ORDER-<id>
    real_memo = f"ORDER-{order_id}"
    await db._exec("UPDATE orders SET pay_memo = ? WHERE id = ?", (real_memo, order_id))
    order = await db.get_order(order_id)
    assert order

    # создаем инвойс
    invoice = await gram_create_invoice(
        order_id=order_id,
        amount_gram=amount_gram,
        memo=real_memo,
        description=product.get("title", "")[:200],
    )

    if invoice.get("provider_id"):
        await db.attach_provider(order_id, invoice["provider_id"], invoice.get("raw", ""))

    return web.json_response({"ok": True, "order": order, "invoice": invoice})


@require_user
async def handle_order_get(request: web.Request) -> web.Response:
    user: WebUser = request["user"]
    try:
        oid = int(request.match_info["id"])
    except:
        return web.json_response({"ok": False, "error": "bad_id"}, status=400)
    order = await db.get_order(oid)
    if not order:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    if order["user_id"] != user.id and user.id not in settings.admin_ids:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    return web.json_response({"ok": True, "order": order})


@require_user
async def handle_order_check(request: web.Request) -> web.Response:
    user: WebUser = request["user"]
    try:
        oid = int(request.match_info["id"])
    except:
        return web.json_response({"ok": False, "error": "bad_id"}, status=400)
    order = await db.get_order(oid)
    if not order:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    if order["user_id"] != user.id and user.id not in settings.admin_ids:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)

    if order["status"] == "paid":
        return web.json_response({"ok": True, "status": "paid", "order": order})

    # 1) пробуем GRAM API статус если есть provider_id
    if order.get("provider_id") and settings.gram_configured:
        st = await get_invoice_status(order["provider_id"])
        if st.get("status") == "paid":
            await db.set_order_status(oid, "paid")
            order = await db.get_order(oid)
            return web.json_response({"ok": True, "status": "paid", "order": order, "via": "gram_api"})

    # 2) пробуем TONAPI
    if settings.tonapi_configured:
        try:
            from payments.tonapi import verify_order
            res = await verify_order(order)
            if res.get("paid"):
                await db.set_order_status(oid, "paid")
                await db.record_payment(
                    order_id=oid,
                    provider="tonapi",
                    provider_payment_id=res["found"]["tx"].get("hash") or res["memo"],
                    amount=res["found"].get("amount"),
                    status="paid",
                    raw=str(res["found"]["tx"])[:2000],
                    currency="GRAM",
                )
                # авто-выдача
                from bots.admin_bot import fulfill_order
                import notify as notify_mod
                user_text = await fulfill_order(order)
                await notify_mod.notify_user(order["user_id"], user_text)
                order = await db.get_order(oid)
                return web.json_response({"ok": True, "status": "paid", "order": order, "via": "tonapi", "tx": res["found"]})
        except Exception as e:
            log.warning("order check tonapi failed: %s", e)

    return web.json_response({"ok": True, "status": order["status"], "order": order})


async def handle_payments_webhook(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except:
        body = {}
    headers = dict(request.headers)
    try:
        parsed = payments.gram.parse_webhook(headers, body)
    except Exception as e:
        log.warning("webhook parse failed: %s", e)
        return web.json_response({"ok": False}, status=400)

    if not parsed:
        return web.json_response({"ok": False, "error": "invalid"}, status=400)

    order_id = parsed.get("order_id")
    provider_id = parsed.get("provider_id")
    status = parsed.get("status")

    # если order_id нет, пробуем найти по provider_id
    order = None
    if order_id:
        order = await db.get_order(int(order_id))
    if not order and provider_id:
        # поиск по provider_id
        rows = await db._fetchall("SELECT * FROM orders WHERE provider_id = ? ORDER BY id DESC LIMIT 1", (provider_id,))
        if rows:
            order = dict(rows[0])

    if not order:
        log.warning("webhook: order not found for %s", parsed)
        return web.json_response({"ok": False, "error": "order_not_found"}, status=404)

    if status == "paid" and order["status"] != "paid":
        await db.set_order_status(order["id"], "paid")
        await db.record_payment(
            order_id=order["id"],
            provider="gram",
            provider_payment_id=provider_id or "",
            amount=parsed.get("amount"),
            status="paid",
            raw=json.dumps(body, ensure_ascii=False)[:2000],
        )
        from bots.admin_bot import fulfill_order
        import notify as notify_mod
        user_text = await fulfill_order(order)
        await notify_mod.notify_user(order["user_id"], user_text)
        await notify_mod.notify_admins(f"✅ Webhook оплата: заказ #{order['id']} {order.get('title')}")

    return web.json_response({"ok": True})


@require_user
async def handle_sessions_request(request: web.Request) -> web.Response:
    user: WebUser = request["user"]
    try:
        data = await request.json()
    except:
        data = {}
    kind = (data.get("kind") or "instant").strip()
    slot = (data.get("slot") or "").strip()
    comment = (data.get("comment") or "").strip()
    product_id = int(data.get("product_id") or 0)
    order_id = int(data.get("order_id") or 0)

    sid = await db.create_session_request(
        user_id=user.id,
        username=user.username or user.first_name,
        kind=kind,
        product_id=product_id,
        order_id=order_id,
        slot=slot,
        comment=comment,
    )
    import notify as notify_mod
    await notify_mod.notify_admins(
        f"👠 Новая заявка на сессию #{sid} от @{user.username or user.id}\n"
        f"Вид: {kind} {slot}\nКоммент: {comment[:200]}"
    )
    return web.json_response({"ok": True, "session_id": sid})


# ---------- admin web ----------

async def handle_admin_page(request: web.Request) -> web.Response:
    token = request.query.get("admin_token") or request.headers.get("X-Admin-Token") or ""
    if not settings.admin_panel_token or token != settings.admin_panel_token:
        return web.Response(text="""
<html><body style="font-family:sans-serif;background:#111;color:#fff;padding:24px">
<h2>🔒 Админка</h2>
<p>Укажи токен: /admin?admin_token=ВАШ_ТОКЕН</p>
<p>Задай ADMIN_PANEL_TOKEN в ENV на БотХосте.</p>
</body></html>""", content_type="text/html", status=403)

    # простая админка
    stats = await db.get_stats()
    pending_orders = await db.list_orders(status="pending", limit=20)
    new_sessions = await db.list_session_requests(status="new", limit=20)

    html = f"""
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Admin — vizitka</title>
<style>
body{{font-family:system-ui;background:#0f0f0f;color:#fff;padding:16px}}
.card{{background:#1e1e1e;border-radius:12px;padding:12px;margin:12px 0}}
a{{color:#8ab4ff}} .btn{{background:#7c4dff;color:#fff;border:0;border-radius:8px;padding:6px 12px;cursor:pointer}}
</style></head><body>
<h2>🔧 Админка vizitka</h2>
<div class="card">
<b>Статистика</b><br>
Игроков: {stats['total_players']} · Оплачено: {stats['paid_orders']} · Выручка: {stats['revenue_gram']} GRAM / {stats['revenue_rub']} ₽
<br>Payments mode: {settings.payments_mode} · TONAPI: {'OK' if settings.tonapi_configured else '—'} · GRAM API: {'OK' if settings.gram_configured else '—'}
<br>Wallet: {settings.ton_wallet_address or settings.gram_wallet_address or '—'}
</div>
<div class="card"><b>⏳ Pending заказы ({len(pending_orders)})</b><br>
{''.join(f"<div>#{o['id']} @{o.get('username')} {o.get('title')} {o.get('amount_gram')} GRAM memo={o.get('pay_memo')} <a href='/api/admin/orders/{o['id']}/approve?admin_token={token}'>✅ Approve</a></div>" for o in pending_orders) or 'нет'}
</div>
<div class="card"><b>👠 Новые сессии ({len(new_sessions)})</b><br>
{''.join(f"<div>#{s['id']} @{s.get('username')} {s.get('kind')} {s.get('comment')[:80]}</div>" for s in new_sessions) or 'нет'}
</div>
<div class="card"><b>Быстрые ссылки</b><br>
<a href="/api/products?admin_token={token}">/api/products</a> · <a href="/api/admin/stats?admin_token={token}">/api/admin/stats</a>
</div>
</body></html>
"""
    return web.Response(text=html, content_type="text/html")


@require_admin
async def handle_admin_stats(request: web.Request) -> web.Response:
    stats = await db.get_stats()
    pending = await db.list_orders(status="pending", limit=100)
    new_s = await db.list_session_requests(status="new", limit=100)
    return web.json_response({
        "ok": True,
        "stats": stats,
        "pending_orders": len(pending),
        "new_sessions": len(new_s),
        "payments_mode": settings.payments_mode,
        "tonapi_configured": settings.tonapi_configured,
        "gram_configured": settings.gram_configured,
    })


@require_admin
async def handle_admin_orders(request: web.Request) -> web.Response:
    status = request.query.get("status", "")
    limit = int(request.query.get("limit", "50") or 50)
    orders = await db.list_orders(status=status, limit=limit)
    return web.json_response({"ok": True, "orders": orders})


@require_admin
async def handle_admin_order_approve(request: web.Request) -> web.Response:
    try:
        oid = int(request.match_info["id"])
    except:
        return web.json_response({"ok": False, "error": "bad_id"}, status=400)
    order = await db.get_order(oid)
    if not order:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    await db.set_order_status(oid, "paid")
    from bots.admin_bot import fulfill_order
    import notify as notify_mod
    user_text = await fulfill_order(order)
    await notify_mod.notify_user(order["user_id"], user_text)
    return web.json_response({"ok": True, "order": await db.get_order(oid)})


# ---------- app factory ----------

def create_app() -> web.Application:
    app = web.Application()

    # CORS для Mini App
    async def cors_middleware(request, handler):
        try:
            resp = await handler(request)
        except web.HTTPException as ex:
            resp = ex
        # Добавляем CORS заголовки
        if isinstance(resp, web.StreamResponse):
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data, X-Admin-Token, X-Dev-User"
        return resp

    app.middlewares.append(cors_middleware)

    # routes
    app.router.add_get("/", handle_root)
    app.router.add_get("/api/config", handle_config)
    app.router.add_get("/api/products", handle_products)
    app.router.add_get("/api/products/{id}", handle_product_one)
    app.router.add_get("/api/reviews", handle_reviews)
    app.router.add_get("/api/media/{file_id}", handle_media)

    app.router.add_post("/api/orders/create", handle_orders_create)
    app.router.add_get("/api/orders/{id}", handle_order_get)
    app.router.add_post("/api/orders/{id}/check", handle_order_check)

    app.router.add_post("/api/payments/webhook", handle_payments_webhook)
    app.router.add_post("/api/sessions/request", handle_sessions_request)

    app.router.add_get("/admin", handle_admin_page)
    app.router.add_get("/api/admin/stats", handle_admin_stats)
    app.router.add_get("/api/admin/orders", handle_admin_orders)
    app.router.add_post("/api/admin/orders/{id}/approve", handle_admin_order_approve)
    app.router.add_get("/api/admin/orders/{id}/approve", handle_admin_order_approve)  # для удобства по ссылке

    # OPTIONS для CORS preflight
    async def options_handler(request):
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data, X-Admin-Token, X-Dev-User",
        })
    app.router.add_route("OPTIONS", "/{tail:.*}", options_handler)

    return app


async def run_web_app():
    if not settings.run_web:
        log.info("web: RUN_WEB=0 — пропуск")
        return

    await db.ensure_schema()
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.host, port=settings.port)
    await site.start()
    log.info("web: слушает %s:%s public=%s", settings.host, settings.port, settings.public_url or "—")
    # держим
    while True:
        await asyncio.sleep(3600)
