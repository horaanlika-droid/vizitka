# -*- coding: utf-8 -*-
"""Оплата GRAM.

Логика выбора режима — в config.Settings.payments_mode:
- 'gram'   — твой API задан (GRAM_API_BASE_URL + GRAM_API_KEY);
- 'manual' — ручной режим: витрина показывает адрес/мемо,
             админ подтверждает заказ в админ-боте.

Свой API подключается ТОЛЬКО переменными окружения,
перезапуск подхватит их автоматически (порядок старта в main.py).
"""

from .gram import (
    PROVIDER_NAME,
    create_invoice,
    get_invoice_status,
    parse_webhook,
    payment_is_configured,
)

__all__ = [
    "PROVIDER_NAME",
    "create_invoice",
    "get_invoice_status",
    "parse_webhook",
    "payment_is_configured",
]
