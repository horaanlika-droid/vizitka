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

Фиксы для сервера:
- Убран catch-all OPTIONS /{tail:.*} который давал 405 на любые неизвестные GET
- Добавлен SPA fallback: неизвестные не-API пути отдают index.html (200), а не 404/405
- / и /index.html и /app и т.д. теперь всегда отдают витрину
- HEAD поддерживается для healthcheck
- /api/products теперь не падает с 500 если БД пустая — возвращает []
- run_web_app слушает несколько портов (PORT, 8080, 3000, 8000) для совместимости с разными хостингами
"""

from __future__ import annotations

import asyncio
import errno
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web

from config import settings, PROJECT_ROOT, FatalStartupError
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
    # HEAD для healthcheck сервера — отдаем 200 без тела, но с CORS
    if request.method == "HEAD":
        return web.Response(status=200, headers=dict(CORS_HEADERS))

    # Отдаем Mini App HTML — если есть web/static/index.html, иначе встроенный
    static_index = PROJECT_ROOT / "web" / "static" / "index.html"
    if static_index.exists():
        return web.FileResponse(static_index, headers=dict(CORS_HEADERS))

    # Встроенный минимальный фронт (улучшен: не падает если /api/products 500)
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
<div style="max-width:720px;margin:24px auto 0;opacity:.6;font-size:12px">
<a href="/health">health</a> · <a href="/api/config">config</a> · <a href="/admin?admin_token={settings.admin_panel_token}">admin</a>
</div>
<script>
const tg = window.Telegram?.WebApp; if(tg){{tg.ready(); tg.expand();}}
let initData = tg?.initData || new URLSearchParams(location.search).get('initData') || '';
const PRODUCTS={{}};
function headers(){{ const h={{'Content-Type':'application/json'}}; if(initData) h['X-Telegram-Init-Data']=initData; return h; }}
async function load() {{
  try{{
    const r = await fetch('/api/products', {{headers: headers()}});
    const j = await r.json();
    const cont = document.getElementById('products');
    if(!j.ok){{ cont.innerHTML='Ошибка: '+(j.error||'unknown')+' <br><small>Проверь логи сервера, БД должна создаться автоматически</small>'; return; }}
    if(!j.products.length){{ cont.innerHTML='Товаров пока нет — добавь в админке /admin'; return; }}
    cont.innerHTML='';
    j.products.forEach(p=>{{
      PRODUCTS[p.id]=p;
      const price = (p.price_gram? p.price_gram+' GRAM ' : '') + (p.price_rub? p.price_rub+' ₽':'');
      const img = p.photo_file_id? `/api/media/${{p.photo_file_id}}` : (p.photo_url||'');
      const el = document.createElement('div'); el.className='card';
      el.innerHTML=`<img src="${{img}}" onerror="this.style.display='none'"><div style="flex:1"><div><b>#${{p.id}} ${{p.title}}</b> <span class="badge">${{p.category}}</span></div><div style="opacity:.8;font-size:13px;margin:4px 0">${{p.description||''}}</div><div class="price">${{price||'цена не указана'}}</div></div><button class="btn" onclick="buy(${{p.id}})">Купить</button>`;
      cont.appendChild(el);
    }});
  }}catch(e){{
    document.getElementById('products').innerHTML='Ошибка загрузки: '+e+'<br>Открой /api/products напрямую для диагностики';
  }}
}}
async function buy(id){{
  const p = PRODUCTS[id];
  const title = p ? (p.title||'') : '';
  const msg = title ? 'Госпожа, хочу купить «'+title+'». Подскажите, пожалуйста, реквизиты.' : 'Госпожа, хочу купить. Подскажите, пожалуйста, реквизиты.';
  const share = 'https://t.me/share/url?url=&text='+encodeURIComponent(msg);
  if(tg && typeof tg.openTelegramLink === 'function'){{ try{{ tg.openTelegramLink(share); return; }}catch(e){{}} }}
  window.open(share, '_blank');
}}
load();
if(tg?.initDataUnsafe?.user) document.getElementById('user').textContent = '@'+(tg.initDataUnsafe.user.username||tg.initDataUnsafe.user.first_name);
</script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html", headers=dict(CORS_HEADERS))


async def handle_config(request: web.Request) -> web.Response:
    try:
        wallet_db = await db.get_wallet_address()
    except Exception:
        wallet_db = ""
    effective_wallet = wallet_db or settings.gram_wallet_address or settings.ton_wallet_address or ""
    return web.json_response({
        "ok": True,
        "contact_username": settings.contact_username,
        "payment_link": settings.payment_link,
        "channels": settings.channels,
        "payments_mode": settings.payments_mode,
        "gram_wallet_address": effective_wallet,
        "ton_wallet_address": effective_wallet,
        "wallet_env": settings.ton_wallet_address or settings.gram_wallet_address or "",
        "wallet_db": wallet_db,
        "public_url": settings.public_url,
        "webapp_url": settings.webapp_url,
        "tonapi_configured": settings.tonapi_configured,
        "tonapi_wallet_configured": settings.tonapi_wallet_configured,
        "minimal_deploy": bool(settings.tonapi_key and settings.admin_ids),
    })


async def handle_products(request: web.Request) -> web.Response:
    try:
        category = request.query.get("category", "")
        active_only = request.query.get("all") != "1"
        products = await db.list_products(active_only=active_only, category=category)
        out = []
        for p in products:
            pp = dict(p)
            if not pp.get("price_gram") and pp.get("price_rub"):
                try:
                    g = await db.gram_price_for(pp)
                    if g:
                        pp["price_gram_calculated"] = g
                except Exception:
                    pass
            out.append(pp)
        return web.json_response({"ok": True, "products": out})
    except Exception as e:
        log.exception("handle_products failed: %s", e)
        # Попытка авто-восстановления схемы (для сервера где БД могла не создаться)
        try:
            await db.ensure_schema()
            await db.init_db()
            products = await db.list_products(active_only=True)
            return web.json_response({"ok": True, "products": [dict(r) for r in products], "recovered": True})
        except Exception as e2:
            log.warning("products recovery failed: %s", e2)
            return web.json_response({"ok": False, "error": "db_error", "details": str(e)[:200], "products": []}, status=200)


async def handle_product_one(request: web.Request) -> web.Response:
    try:
        pid = int(request.match_info["id"])
    except:
        return web.json_response({"ok": False, "error": "bad_id"}, status=400)
    try:
        p = await db.get_product(pid)
    except Exception as e:
        log.warning("get_product failed: %s", e)
        return web.json_response({"ok": False, "error": "db_error"}, status=500)
    if not p:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    return web.json_response({"ok": True, "product": dict(p)})


async def handle_reviews(request: web.Request) -> web.Response:
    try:
        items = await db.db_list_reviews(limit=50)
    except Exception as e:
        log.warning("reviews failed: %s", e)
        items = []
    return web.json_response({"ok": True, "reviews": items})


async def handle_media(request: web.Request) -> web.Response:
    file_id = request.match_info["file_id"]
    cache_dir = Path(settings.media_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
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

    promocode = (data.get("promocode") or "").strip().upper()

    amount_gram = product.get("price_gram")
    amount_rub = product.get("price_rub")
    if not amount_gram and amount_rub:
        amount_gram = await db.gram_price_for(product)

    if promocode:
        promo = await db.db_get_promocode(promocode)
        if promo and promo["is_active"] and promo["used"] < promo["max_uses"]:
            await db.db_use_promocode(promocode)
        else:
            return web.json_response({"ok": False, "error": "bad_promocode"}, status=400)

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
    real_memo = f"ORDER-{order_id}"
    await db._exec("UPDATE orders SET pay_memo = ? WHERE id = ?", (real_memo, order_id))
    order = await db.get_order(order_id)
    assert order

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

    if order.get("provider_id") and settings.gram_configured:
        st = await get_invoice_status(order["provider_id"])
        if st.get("status") == "paid":
            await db.set_order_status(oid, "paid")
            order = await db.get_order(oid)
            return web.json_response({"ok": True, "status": "paid", "order": order, "via": "gram_api"})

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

    order = None
    if order_id:
        order = await db.get_order(int(order_id))
    if not order and provider_id:
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
        hint = f"<p>Текущий токен (авто): <code>{settings.admin_panel_token}</code></p><p>Открой: <code>/admin?admin_token={settings.admin_panel_token}</code></p>" if settings.admin_panel_token.startswith("admin_") else ""
        from .auth import dev_user
        if settings.allow_dev_auth and dev_user(request):
            pass
        else:
            return web.Response(text=f"""
<html><body style="font-family:sans-serif;background:#111;color:#fff;padding:24px">
<h2>🔒 Админка</h2>
<p>Укажи токен (пароль): /admin?admin_token=ВАШ_ТОКЕН</p>
{hint}
</body></html>""", content_type="text/html", status=403)

    stats = await db.get_stats()
    pending_orders = await db.list_orders(status="pending", limit=20)
    new_sessions = await db.list_session_requests(status="new", limit=20)
    wallet_env = settings.ton_wallet_address or settings.gram_wallet_address or ""
    try:
        wallet_db = await db.get_wallet_address()
    except Exception:
        wallet_db = wallet_env
    wallet_display = wallet_db or wallet_env or "— не задан —"
    tonapi_key_display = (settings.tonapi_key[:6] + "…") if settings.tonapi_key else "—"

    html = f"""
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Admin Panel</title>
<style>
body{{font-family:system-ui;background:#0f0f0f;color:#fff;padding:16px;max-width:900px;margin:0 auto}}
.card{{background:#1e1e1e;border-radius:12px;padding:14px;margin:14px 0}}
a{{color:#8ab4ff}} .btn{{background:#7c4dff;color:#fff;border:0;border-radius:10px;padding:8px 14px;cursor:pointer;margin:4px}}
input{{background:#111;color:#fff;border:1px solid #333;border-radius:8px;padding:8px 12px;width:100%;max-width:500px}}
.badge{{background:#333;padding:2px 8px;border-radius:6px;font-size:12px}}
.ok{{color:#8aff8a}} .warn{{color:#ffb86c}} .err{{color:#ff6b6b}}
</style></head><body>
<h2>🔧 Управление Клубом</h2>

<div class="card">
<b>📊 Статистика</b><br>
Пользователей: {stats['total_players']} · Оплачено: {stats['paid_orders']} · Выручка: {stats['revenue_gram']} GRAM / {stats['revenue_rub']} ₽
<br>Payments mode: <b>{settings.payments_mode}</b> · TONAPI: <span class="{'ok' if settings.tonapi_configured else 'err'}">{'OK '+tonapi_key_display if settings.tonapi_configured else '— нет ключа'}</span>
<br>Кошелек (база): <b>{wallet_display}</b> {'<span class=ok>✅</span>' if wallet_display!='— не задан —' else '<span class=err>❌ задай ниже</span>'}
</div>

<div class="card">
<b>💳 Привязка кошелька TON</b><br>
<small>Укажи кошелек, на который будут поступать переводы.</small><br><br>
<form onsubmit="setWallet(event)">
<input id="wallet" placeholder="EQ... или UQ... твой TON кошелек" value="{wallet_db}" />
<button class="btn" type="submit">💾 Сохранить кошелек</button>
</form>
<div id="wallet_res" style="margin-top:8px"></div>
<script>
async function setWallet(e){{
 e.preventDefault();
 const w=document.getElementById('wallet').value.trim();
 const resDiv=document.getElementById('wallet_res');
 resDiv.textContent='Сохранение...';
 try{{
   const r=await fetch('/api/admin/settings/wallet?admin_token={token}', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{wallet:w}})}});
   const j=await r.json();
   resDiv.textContent=j.ok ? '✅ Сохранено: '+j.wallet : '❌ Ошибка: '+(j.error||'unknown');
   if(j.ok) setTimeout(() => location.reload(), 1000);
 }}catch(err){{ resDiv.textContent='❌ '+err; }}
}}
</script>
</div>

<div class="card"><b>⏳ Ожидающие заказы ({len(pending_orders)})</b><br>
{''.join(f"<div style='margin:6px 0'>#{o['id']} @{o.get('username')} {o.get('title')} {o.get('amount_gram')} GRAM memo={o.get('pay_memo')} <a class='btn' href='/api/admin/orders/{o['id']}/approve?admin_token={token}'>✅ Approve</a> <a class='btn' href='/api/admin/orders/{o['id']}/check?admin_token={token}'>🔍 Check TONAPI</a></div>" for o in pending_orders) or 'нет'}
</div>

<div class="card"><b>👠 Новые заявки ({len(new_sessions)})</b><br>
{''.join(f"<div>#{s['id']} @{s.get('username')} {s.get('kind')} {s.get('comment')[:80]}</div>" for s in new_sessions) or 'нет'}
</div>

<div class="card"><b>Быстрые ссылки</b><br>
<a href="/api/products?admin_token={token}">/api/products</a> · <a href="/api/admin/stats?admin_token={token}">/api/admin/stats</a> · <a href="/api/admin/settings?admin_token={token}">/api/admin/settings</a> · <a href="/api/config">/api/config</a>
<br><br><small>Для БотХоста достаточно: <code>TONAPI_KEY</code> + <code>ADMIN_IDS</code> — остальное подхватится. Если хочешь ботов — добавь <code>BOT_TOKEN</code>.</small>
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


@require_admin
async def handle_admin_order_check(request: web.Request) -> web.Response:
    try:
        oid = int(request.match_info["id"])
    except:
        return web.json_response({"ok": False, "error": "bad_id"}, status=400)
    order = await db.get_order(oid)
    if not order:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    if order["status"] == "paid":
        return web.json_response({"ok": True, "status": "paid", "order": order})
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
                from bots.admin_bot import fulfill_order
                import notify as notify_mod
                user_text = await fulfill_order(order)
                await notify_mod.notify_user(order["user_id"], user_text)
                order = await db.get_order(oid)
                return web.json_response({"ok": True, "status": "paid", "order": order, "via": "tonapi", "tx": res["found"]})
            return web.json_response({"ok": True, "status": "pending", "order": order, "tonapi": res})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)
    return web.json_response({"ok": True, "status": order["status"], "order": order})


@require_admin
async def handle_admin_settings(request: web.Request) -> web.Response:
    try:
        wallet = await db.get_wallet_address()
    except Exception:
        wallet = settings.ton_wallet_address or settings.gram_wallet_address
    try:
        gram_rate = await db.get_gram_rate()
    except Exception:
        gram_rate = 0
    return web.json_response({
        "ok": True,
        "tonapi_key": (settings.tonapi_key[:8] + "…") if settings.tonapi_key else "",
        "tonapi_configured": settings.tonapi_configured,
        "tonapi_wallet_configured": settings.tonapi_wallet_configured,
        "wallet_env": settings.ton_wallet_address or settings.gram_wallet_address or "",
        "wallet_db": wallet,
        "wallet_effective": wallet or settings.ton_wallet_address or settings.gram_wallet_address or "",
        "gram_jetton_master": settings.gram_jetton_master,
        "payments_mode": settings.payments_mode,
        "public_url": settings.public_url,
        "admin_ids": settings.admin_ids,
        "admin_panel_token": settings.admin_panel_token,
        "gram_rate": gram_rate,
        "contact_username": settings.contact_username,
    })


@require_admin
async def handle_admin_settings_wallet(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        data = {}
    wallet = (data.get("wallet") or data.get("address") or request.query.get("wallet") or "").strip()
    if not wallet:
        return web.json_response({"ok": False, "error": "wallet required, e.g. EQ... or UQ..."}, status=400)
    if len(wallet) < 20 or not wallet.startswith(("EQ", "UQ", "0Q", "kQ")):
        log.warning("admin: saving wallet with unusual format: %s", wallet)
    try:
        await db.set_wallet_address(wallet)
        return web.json_response({"ok": True, "wallet": wallet, "message": "saved to DB, tonapi poll will use it"})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)


# ---------- SPA fallback & 404 handling ----------

async def handle_api_404(request: web.Request) -> web.Response:
    """Явный 404 для неизвестных /api/* — чтобы не отдавать index.html на API."""
    return web.json_response({"ok": False, "error": "not_found", "path": request.path}, status=404)


async def handle_spa_fallback(request: web.Request) -> web.Response:
    """
    Fallback для сервера и Telegram Mini App:
    - /api/*, /admin, /health, /ping → 404 JSON (не маскируем ошибки API)
    - всё остальное → отдаем витрину (200), чтобы не было 404/405
    Это фиксит кейс когда сервер открывает /index.html или /app и получает 404/405.
    """
    path = request.path.lower()
    # API и админка должны отдавать честный 404, не витрину
    if path.startswith("/api/") or path.startswith("/admin") or path.startswith("/health") or path.startswith("/ping"):
        return web.json_response({"ok": False, "error": "not_found", "path": request.path}, status=404)
    # HEAD для healthcheck
    if request.method == "HEAD":
        return web.Response(status=200, headers=dict(CORS_HEADERS))
    # Всё остальное — витрина (SPA)
    return await handle_root(request)


# ---------- app factory ----------

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS, HEAD",
    "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data, X-Admin-Token, X-Dev-User",
}


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """CORS для Mini App. Обрабатывает OPTIONS сразу."""
    if request.method == "OPTIONS":
        return web.Response(headers=dict(CORS_HEADERS))
    try:
        resp = await handler(request)
    except web.HTTPException as ex:
        for k, v in CORS_HEADERS.items():
            try:
                ex.headers[k] = v
            except Exception:
                pass
        raise
    try:
        for k, v in CORS_HEADERS.items():
            resp.headers[k] = v
    except Exception:
        pass
    return resp


async def on_response_prepare(request: web.Request, response: web.StreamResponse):
    try:
        for k, v in CORS_HEADERS.items():
            if k not in response.headers:
                response.headers[k] = v
    except Exception:
        pass


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "vizitka"})


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.on_response_prepare.append(on_response_prepare)

    # Основные маршруты
    app.router.add_get("/", handle_root)
    app.router.add_get("/index.html", handle_root)
    app.router.add_get("/app", handle_root)
    app.router.add_get("/webapp", handle_root)

    # healthcheck-и для хостингов (БотХост пингует корень или /health)
    # HEAD автоматически обрабатывается aiohttp для GET
    app.router.add_get("/health", handle_health)
    app.router.add_get("/ping", handle_health)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/ping", handle_health)

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
    app.router.add_get("/api/admin/orders/{id}/approve", handle_admin_order_approve)
    app.router.add_get("/api/admin/orders/{id}/check", handle_admin_order_check)
    app.router.add_post("/api/admin/orders/{id}/check", handle_admin_order_check)
    app.router.add_get("/api/admin/settings", handle_admin_settings)
    app.router.add_post("/api/admin/settings/wallet", handle_admin_settings_wallet)
    app.router.add_get("/api/admin/settings/wallet", handle_admin_settings_wallet)

    # Статика если есть web/static (для будущего фронта) — только /static/
    # НЕ монтируем "/" на static, иначе /nonexistent будет 404 вместо SPA fallback
    static_dir = PROJECT_ROOT / "web" / "static"
    if static_dir.exists():
        app.router.add_static("/static/", path=str(static_dir), show_index=False, follow_symlinks=True)

    # SPA fallback — должен быть ПОСЛЕ всех конкретных роутов
    # Отдаем витрину на любые неизвестные GET, кроме /api/* (там 404 JSON)
    # Это фиксит 404 на сервере когда он открывает /app, /index.html, /webapp и т.д.
    app.router.add_get("/{tail:.*}", handle_spa_fallback)

    return app


def _is_addr_in_use(e: BaseException) -> bool:
    if getattr(e, "errno", None) == errno.EADDRINUSE:
        return True
    return "address already in use" in str(e).lower()


async def _another_vizitka_listening(host: str, port: int) -> bool:
    candidates = []
    for h in (host, "127.0.0.1"):
        if h and h not in ("0.0.0.0", "::") and h not in candidates:
            candidates.append(h)
    timeout = aiohttp.ClientTimeout(total=4)
    for h in candidates or ["127.0.0.1"]:
        url = f"http://{h}:{port}/health"
        try:
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get(url) as r:
                    if r.status != 200:
                        continue
                    body = (await r.text()).lower()
                    if "vizitka" in body:
                        return True
        except Exception:
            continue
    return False


async def run_web_app():
    if not settings.run_web:
        log.info("web: RUN_WEB=0 — пропуск")
        return

    # БД — страховка, даже если init_db уже был в main.py
    try:
        await db.ensure_schema()
        await db.init_db()
    except Exception as e:
        log.warning("web: ensure_schema/init_db failed (продолжаю): %s", e)

    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    # сервер может давать PORT, а может ожидать 8080 или 3000
    # Собираем список портов для попытки бинда (80 убран — требует root)
    primary_port = settings.port
    candidate_ports = []
    # 1. Порт из настроек (из ENV PORT и т.д.)
    candidate_ports.append(primary_port)
    # 2. Стандартные порты сервера / PaaS — слушаем все, чтобы не было 404
    for p in (8080, 3000, 8000, 5000, 3001, 8081):
        if p not in candidate_ports:
            candidate_ports.append(p)
    # 3. Если в ENV есть другие PORT-подобные переменные, уже учтены в settings.port,
    # но для логов покажем все ENV
    env_ports = {k: v for k, v in os.environ.items() if "PORT" in k.upper()}
    log.info("web: env PORT vars: %s", env_ports)

    sites = []
    last_exc = None
    # Пытаемся забиндить primary порт обязательно, остальные — как дополнение
    for port in candidate_ports:
        try:
            site = web.TCPSite(runner, host=settings.host, port=port)
            await site.start()
            sites.append((port, site))
            log.info("web: слушает %s:%s public=%s", settings.host, port, settings.public_url or "—")
        except OSError as e:
            last_exc = e
            if _is_addr_in_use(e):
                # Проверяем — может там уже наша копия?
                if await _another_vizitka_listening(settings.host, port):
                    if port == primary_port:
                        try:
                            await runner.cleanup()
                        except Exception:
                            pass
                        raise FatalStartupError(
                            f"порт {settings.host}:{port} уже слушает ДРУГАЯ КОПИЯ vizitka "
                            f"(health отвечает). Этот процесс — дубль, останавливаю его. "
                            f"Если веб не открывается — в панели хостинга сделай полный Restart/Redeploy "
                            f"и убедись, что приложение запущено ОДИН раз (один сервис, одна start-команда python main.py)."
                        ) from e
                    else:
                        log.warning("web: порт %s занят другой копией vizitka — пропускаю", port)
                        continue
                # Если это не primary порт — просто логируем и идем дальше
                if port == primary_port:
                    log.error(
                        "web: НЕ МОГУ слушать %s:%s — %s. Порт занят, но vizitka там не отвечает — "
                        "похоже, старый (зомби-)процесс или чужое приложение. "
                        "Сделай полный Restart проекта в панели хостинга, проверь PORT.",
                        settings.host, port, e,
                    )
                    # для primary — не выходим сразу, попробуем другие порты
                    continue
                else:
                    log.info("web: порт %s занят (%s) — пропускаю", port, e)
                    continue
            else:
                log.error("web: НЕ МОГУ слушать %s:%s — %s. Проверь PORT в панели хостинга.", settings.host, port, e)
                if port == primary_port:
                    continue

    if not sites:
        try:
            await runner.cleanup()
        except Exception:
            pass
        log.error("web: ни один порт не удалось забиндить %s — %s", candidate_ports, last_exc)
        raise last_exc or RuntimeError("no port bound")

    primary_bound = any(p == primary_port for p, _ in sites)
    if not primary_bound:
        log.warning("web: primary порт %s не забиндился, но забиндились %s — продолжаю (для сервера это ок)", primary_port, [p for p, _ in sites])

    log.info("web: витрина / | health /health | api /api/products | admin /admin?admin_token=... | bound ports=%s", [p for p, _ in sites])

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        try:
            await runner.cleanup()
        except Exception:
            pass
