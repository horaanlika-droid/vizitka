# -*- coding: utf-8 -*-
"""GRAM-провайдер.

Два режима:
1) gram   — REST к твоему API (endpoints настраиваются через ENV,
             ответы разбираются по распространённым полям с fallback'ами).
2) manual — без API: адрес кошелька + мемо, подтверждение вручную.

Ни одна функция здесь не роняет процесс: ошибки логируются и
возвращаются в виде словаря с ok=False.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import aiohttp

from config import settings

log = logging.getLogger("vizitka.payments")

PROVIDER_NAME = "gram"


def payment_is_configured() -> bool:
    return settings.payments_mode == "gram" and settings.gram_configured


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if settings.gram_api_key:
        h["Authorization"] = f"Bearer {settings.gram_api_key}"
    if settings.gram_merchant_id:
        h["X-Merchant-Id"] = settings.gram_merchant_id
    return h


def _pick(data: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if isinstance(data, dict) and data.get(k) not in (None, ""):
            return data[k]
    return default


async def _post(path: str, payload: dict) -> tuple[bool, dict]:
    url = settings.gram_api_base_url + path
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, json=payload, headers=_headers(),
                                 timeout=20) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    data = {"_text": (await resp.text())[:500]}
                if resp.status >= 400:
                    log.warning("gram POST %s -> %s: %s", path, resp.status, data)
                    return False, {"ok": False, "http": resp.status, "data": data}
                return True, data if isinstance(data, dict) else {"ok": True, "data": data}
    except Exception as e:
        log.warning("gram POST %s failed: %s", path, e)
        return False, {"ok": False, "error": str(e)}


async def _get(path: str) -> tuple[bool, dict]:
    url = settings.gram_api_base_url + path
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, headers=_headers(), timeout=20) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    data = {"_text": (await resp.text())[:500]}
                if resp.status >= 400:
                    return False, {"ok": False, "http": resp.status, "data": data}
                return True, data if isinstance(data, dict) else {"ok": True, "data": data}
    except Exception as e:
        log.warning("gram GET %s failed: %s", path, e)
        return False, {"ok": False, "error": str(e)}


# ---------- создание счёта ----------

async def create_invoice(order_id: int, amount_gram: float | None,
                         memo: str, description: str = "") -> dict[str, Any]:
    """Создать счёт. Возвращает dict для витрины:

    {ok, mode: 'gram'|'manual', pay_url?, address?, memo?, amount?,
     qr_text?, provider_id?, raw?, error?}
    """
    if not payment_is_configured():
        return _manual_invoice(amount_gram, memo)

    payload = {
        "amount": amount_gram,
        "currency": "GRAM",
        "order_id": order_id,
        "memo": memo,
        "description": description or f"Заказ #{order_id}",
        "webhook_url": f"{settings.public_url}/api/payments/webhook}" if settings.public_url else "",
        "merchant_id": settings.gram_merchant_id,
    }
    ok, data = await _post(settings.gram_create_path, payload)
    if not ok:
        log.warning("gram: create_invoice упал, отдаю manual как fallback")
        out = _manual_invoice(amount_gram, memo)
        out["fallback_reason"] = str(data.get("error") or data.get("http") or "api_error")
        return out

    body = data.get("data", data) if isinstance(data.get("data"), dict) else data
    provider_id = str(_pick(body, "id", "invoice_id", "payment_id", "uuid", default=""))
    pay_url = _pick(body, "pay_url", "payment_url", "url", "invoice_url", "link", default="")
    address = _pick(body, "address", "wallet", "wallet_address", default="")
    out_memo = _pick(body, "memo", "tag", "comment", "payload", default=memo)
    amount = _pick(body, "amount", default=amount_gram)
    return {
        "ok": True,
        "mode": "gram",
        "pay_url": pay_url or "",
        "address": address or "",
        "memo": out_memo or memo,
        "amount": amount,
        "qr_text": pay_url or (f"{address}:{out_memo}" if address else ""),
        "provider_id": provider_id,
        "raw": json.dumps(data, ensure_ascii=False)[:2000],
    }


def _manual_invoice(amount_gram: float | None, memo: str) -> dict[str, Any]:
    address = settings.gram_wallet_address or ""
    return {
        "ok": True,
        "mode": "manual",
        "pay_url": "",
        "address": address,
        "memo": memo,
        "amount": amount_gram,
        "qr_text": f"{address}:{memo}" if address else memo,
        "provider_id": "",
        "raw": "",
        "contact": "@" + settings.contact_username,
        "note": ("Оплата в ручном режиме: переведи GRAM на адрес с мемо, "
                 "админ подтвердит заказ в течение дня."),
    }


# ---------- статус счёта ----------

_PAID = {"paid", "success", "succeeded", "completed", "confirmed", "ok"}
_EXPIRED = {"expired", "canceled", "cancelled", "failed", "rejected"}


async def get_invoice_status(provider_id: str) -> dict[str, Any]:
    """Проверить статус у API. Возвращает {ok, status: paid|pending|expired|unknown, raw}."""
    if not provider_id or not payment_is_configured():
        return {"ok": False, "status": "unknown"}
    path = settings.gram_status_path.replace("{id}", provider_id)
    ok, data = await _get(path)
    if not ok:
        return {"ok": False, "status": "unknown", "raw": json.dumps(data, ensure_ascii=False)[:500]}
    body = data.get("data", data) if isinstance(data.get("data"), dict) else data
    raw_status = str(_pick(body, "status", "state", default="")).lower()
    if raw_status in _PAID:
        status = "paid"
    elif raw_status in _EXPIRED:
        status = "expired"
    elif raw_status:
        status = "pending"
    else:
        status = "unknown"
    return {"ok": True, "status": status,
            "raw": json.dumps(data, ensure_ascii=False)[:1000]}


# ---------- вебхук от API ----------

def parse_webhook(headers: dict, body: dict) -> Optional[dict[str, Any]]:
    """Разобрать колбэк оплаты. Возвращает {order_id, provider_id, status, amount} или None."""
    if settings.gram_webhook_secret:
        got = (headers.get("x-webhook-secret") or headers.get("x-signature") or "")
        if got != settings.gram_webhook_secret:
            log.warning("gram webhook: неверный секрет")
            return None
    data = body.get("data", body) if isinstance(body.get("data"), dict) else body
    raw_status = str(_pick(data, "status", "state", default="")).lower()
    if raw_status in _PAID:
        status = "paid"
    elif raw_status in _EXPIRED:
        status = "expired"
    else:
        status = "pending"
    try:
        order_id = int(_pick(data, "order_id", "orderId", "external_id", default=0) or 0)
    except (ValueError, TypeError):
        order_id = 0
    provider_id = str(_pick(data, "id", "invoice_id", "payment_id", "uuid", default=""))
    try:
        amount = float(_pick(data, "amount", "sum", default=0) or 0)
    except (ValueError, TypeError):
        amount = 0.0
    if not order_id and not provider_id:
        log.warning("gram webhook: нет order_id/provider_id: %s", body)
        return None
    return {"order_id": order_id, "provider_id": provider_id,
            "status": status, "amount": amount or None}
