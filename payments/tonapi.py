# -*- coding: utf-8 -*-
"""Проверка платежей через TONAPI.io напрямую.

Использует TONAPI_KEY + TON_WALLET_ADDRESS (или GRAM_WALLET_ADDRESS).

Логика:
- Клиент создает заказ -> получаем memo типа ORDER-123
- Пользователь должен перевести TON или GRAM Jetton на твой кошелек с комментарием memo
- Фоновая задача каждые N секунд запрашивает последние транзакции через TONAPI
  и ищет совпадение по memo и сумме
- Если найдено — заказ автоматом подтверждается

Поддерживает:
- TON нативные переводы (проверка comment)
- GRAM Jetton переводы (если указан GRAM_JETTON_MASTER) — проверка jetton transfer
- Fallback: если jetton master не указан — ищем любые входящие с memo

Ничего не роняет, все ошибки логируются.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import aiohttp

from config import settings
import database as db
import notify

log = logging.getLogger("vizitka.payments.tonapi")

TONAPI_TIMEOUT = 20


def is_configured() -> bool:
    return settings.tonapi_configured


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if settings.tonapi_key:
        h["Authorization"] = f"Bearer {settings.tonapi_key}"
    return h


def _wallet() -> str:
    return (settings.ton_wallet_address or settings.gram_wallet_address or "").strip()


async def _get(path: str, params: dict | None = None) -> tuple[bool, Any]:
    url = f"{settings.tonapi_base_url}{path}"
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, headers=_headers(), params=params or {}, timeout=TONAPI_TIMEOUT) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    txt = (await resp.text())[:500]
                    return False, {"_text": txt, "status": resp.status}
                if resp.status >= 400:
                    log.warning("tonapi GET %s -> %s: %s", path, resp.status, str(data)[:500])
                    return False, {"http": resp.status, "data": data}
                return True, data
    except Exception as e:
        log.warning("tonapi GET %s failed: %s", path, e)
        return False, {"error": str(e)}


async def fetch_recent_transactions(limit: int = 100) -> list[dict]:
    """Получить последние транзакции кошелька через TONAPI."""
    wallet = _wallet()
    if not wallet:
        return []
    # Основной endpoint: /v2/accounts/{account_id}/transactions
    ok, data = await _get(f"/v2/accounts/{wallet}/transactions", {"limit": min(limit, 100)})
    if not ok:
        # fallback: /v2/blockchain/accounts/{account_id}/transactions
        ok2, data2 = await _get(f"/v2/blockchain/accounts/{wallet}/transactions", {"limit": min(limit, 100), "sort_order": "desc"})
        if ok2:
            ok, data = ok2, data2
    if not ok:
        return []
    # TONAPI возвращает {"transactions": [...]} или список
    if isinstance(data, dict):
        txs = data.get("transactions") or data.get("events") or []
        if isinstance(txs, list):
            return txs
        # иногда /v2/accounts/... возвращает dict с транзакциями внутри events
        return []
    if isinstance(data, list):
        return data
    return []


def _extract_comment(tx: dict) -> str:
    """Вытащить комментарий/memo из транзакции TONAPI (учитывает разные форматы)."""
    # Нативные TON переводы
    try:
        # Формат tonapi v2: tx["in_msg"]["message_content"]["decoded"]["comment"] или
        # tx["in_msg"]["decoded_body"] или tx["in_msg"]["message"]
        in_msg = tx.get("in_msg") or {}
        # decoded comment
        decoded = in_msg.get("decoded_body") or {}
        if isinstance(decoded, dict):
            c = decoded.get("comment") or decoded.get("text") or ""
            if c:
                return str(c).strip()
        # message_content
        mc = in_msg.get("message_content") or {}
        dec = mc.get("decoded") or {}
        if isinstance(dec, dict):
            c = dec.get("comment") or dec.get("text") or ""
            if c:
                return str(c).strip()
        # raw body
        body = in_msg.get("message") or in_msg.get("body") or ""
        if isinstance(body, str) and body:
            return body.strip()
        # comment в корне
        if tx.get("comment"):
            return str(tx["comment"]).strip()
        # jetton transfer comment
        # для jetton: tx["in_msg"]["jetton_transfer"]["comment"]
        jt = in_msg.get("jetton_transfer") or {}
        if jt.get("comment"):
            return str(jt["comment"]).strip()
        # actions
        for action in tx.get("actions", []) or []:
            if action.get("comment"):
                return str(action["comment"]).strip()
            # JettonTransfer action
            jt_act = action.get("JettonTransfer") or action.get("jetton_transfer") or {}
            if jt_act.get("comment"):
                return str(jt_act["comment"]).strip()
    except Exception:
        pass
    return ""


def _extract_amount_ton(tx: dict) -> float:
    """Сумма входящего TON в TON (не nanotons)."""
    try:
        in_msg = tx.get("in_msg") or {}
        # value в nanotons
        val = in_msg.get("value") or tx.get("value") or 0
        if isinstance(val, str):
            try:
                val = int(val)
            except:
                val = 0
        if val:
            return float(val) / 1e9
        # alternative: amount field
        amt = tx.get("amount") or in_msg.get("amount") or 0
        if amt:
            return float(amt) / 1e9 if float(amt) > 1000 else float(amt)
    except Exception:
        pass
    return 0.0


def _extract_jetton_amount(tx: dict, jetton_master: str = "") -> tuple[str, float]:
    """Если это Jetton трансфер, вернуть (jetton_master, amount)."""
    try:
        in_msg = tx.get("in_msg") or {}
        jt = in_msg.get("jetton_transfer") or {}
        if jt:
            master = jt.get("jetton_master") or jt.get("jetton") or ""
            amount_raw = jt.get("amount") or jt.get("jetton_amount") or 0
            # amount обычно в минимальных единицах, но для GRAM часто 9 decimals
            # пробуем распарсить как float, если большое — делим на 1e9
            try:
                amt = float(amount_raw)
                if amt > 1e6:  # likely nanotons
                    amt = amt / 1e9
            except:
                amt = 0.0
            return master, amt
        for action in tx.get("actions", []) or []:
            jt_act = action.get("JettonTransfer") or {}
            if jt_act:
                master = jt_act.get("jetton_master") or jt_act.get("jetton") or ""
                amt_raw = jt_act.get("amount") or 0
                try:
                    amt = float(amt_raw)
                    if amt > 1e6:
                        amt = amt / 1e9
                except:
                    amt = 0.0
                return master, amt
    except Exception:
        pass
    return "", 0.0


async def find_payment_by_memo(memo: str, expected_amount: float | None = None, tolerance: float = 0.05) -> Optional[dict]:
    """Найти транзакцию с memo. Возвращает dict с данными или None."""
    memo = (memo or "").strip()
    if not memo:
        return None
    txs = await fetch_recent_transactions(limit=100)
    if not txs:
        return None

    memo_lower = memo.lower()
    for tx in txs:
        comment = _extract_comment(tx)
        if not comment:
            continue
        if memo_lower not in comment.lower():
            continue

        # memo совпал, проверяем сумму если указана
        if expected_amount and expected_amount > 0:
            # проверяем TON amount
            ton_amt = _extract_amount_ton(tx)
            jetton_master, jetton_amt = _extract_jetton_amount(tx, settings.gram_jetton_master)

            # если указан jetton master — требуем совпадение мастера
            if settings.gram_jetton_master:
                if jetton_master and settings.gram_jetton_master.lower() not in jetton_master.lower():
                    # не тот jetton
                    continue
                # сравниваем jetton amount
                if jetton_amt > 0 and abs(jetton_amt - expected_amount) <= max(tolerance, expected_amount * 0.02):
                    return {"tx": tx, "comment": comment, "amount": jetton_amt, "type": "jetton", "jetton_master": jetton_master}
                # если jetton amount не нашли, но memo совпал — считаем оплаченным (для ручного режима)
                if jetton_amt == 0:
                    return {"tx": tx, "comment": comment, "amount": ton_amt, "type": "jetton_unknown", "jetton_master": jetton_master}
            else:
                # без jetton master — проверяем TON amount или любой jetton
                if ton_amt > 0:
                    if abs(ton_amt - expected_amount) <= max(tolerance, expected_amount * 0.02):
                        return {"tx": tx, "comment": comment, "amount": ton_amt, "type": "ton"}
                    # если сумма сильно отличается, но memo точный — все равно считаем (админ проверит)
                    # для безопасности требуем хотя бы 50% от ожидаемой
                    if ton_amt >= expected_amount * 0.5:
                        return {"tx": tx, "comment": comment, "amount": ton_amt, "type": "ton_partial"}
                if jetton_amt > 0:
                    if abs(jetton_amt - expected_amount) <= max(tolerance, expected_amount * 0.02):
                        return {"tx": tx, "comment": comment, "amount": jetton_amt, "type": "jetton"}
                    if jetton_amt >= expected_amount * 0.5:
                        return {"tx": tx, "comment": comment, "amount": jetton_amt, "type": "jetton_partial"}
        else:
            # сумма не указана — достаточно memo
            ton_amt = _extract_amount_ton(tx)
            _, jetton_amt = _extract_jetton_amount(tx)
            return {"tx": tx, "comment": comment, "amount": ton_amt or jetton_amt, "type": "any"}

    return None


async def verify_order(order: dict) -> dict:
    """Проверить конкретный заказ по TONAPI. Возвращает {paid: bool, tx_info}. """
    memo = order.get("pay_memo") or f"ORDER-{order['id']}"
    expected = order.get("amount_gram") or order.get("amount_rub") or None
    # для TONAPI ожидаем GRAM amount, но если его нет — берем RUB как fallback (админ решит)
    try:
        expected_f = float(expected) if expected else None
    except:
        expected_f = None

    found = await find_payment_by_memo(memo, expected_f)
    if found:
        return {"paid": True, "found": found, "memo": memo}
    return {"paid": False, "memo": memo}


async def tonapi_poll_loop():
    """Фоновая задача: каждые N секунд проверять pending заказы."""
    if not is_configured():
        log.info("tonapi poll: не настроен (TONAPI_KEY или кошелек пуст) — пропускаю")
        return
    interval = max(10, settings.tonapi_check_interval)
    log.info("tonapi poll: старт, интервал %s сек, кошелек %s", interval, _wallet()[:12] + "…")
    while True:
        try:
            await asyncio.sleep(interval)
            pending = await db.list_orders(status="pending", limit=50)
            if not pending:
                continue
            log.info("tonapi poll: проверяю %s pending заказов", len(pending))
            for order in pending:
                try:
                    res = await verify_order(order)
                    if res.get("paid"):
                        await db.set_order_status(order["id"], "paid")
                        await db.record_payment(
                            order_id=order["id"],
                            provider="tonapi",
                            provider_payment_id=res["found"]["tx"].get("hash") or res["found"]["tx"].get("transaction_id") or res["memo"],
                            amount=res["found"].get("amount"),
                            status="paid",
                            raw=str(res["found"]["tx"])[:2000],
                            currency="GRAM" if res["found"].get("type", "").startswith("jetton") else "TON",
                        )
                        # авто-выдача
                        from bots.admin_bot import fulfill_order
                        user_text = await fulfill_order(order)
                        await notify.notify_user(order["user_id"], user_text)
                        await notify.notify_admins(
                            f"✅ TONAPI автоподтверждение: заказ #{order['id']} {order.get('title')} "
                            f"от @{order.get('username') or order['user_id']} — {res['found'].get('amount')} {res['found'].get('type')}"
                        )
                        log.info("tonapi poll: заказ #%s подтвержден", order["id"])
                except Exception as e:
                    log.warning("tonapi poll: ошибка заказа #%s: %s", order.get("id"), e)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.warning("tonapi poll loop error: %s", e)
            await asyncio.sleep(interval)
