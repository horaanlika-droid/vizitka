# vizitka

Бот-витрина (Telegram) + веб (Mini App / лендинг) + админ-бот.
Запуск: `python main.py` — aiogram polling + aiohttp веб + TONAPI проверка в одном процессе.

## Деплой — минимальный набор: TONAPI_KEY + ADMIN_IDS

В панель достаточно ввести 2 переменные:

```ini
TONAPI_KEY=твой_ключ_с_tonapi.io
ADMIN_IDS=123456789
```

Остальное опционально и подхватывается автоматически:
- `ADMIN_PANEL_TOKEN` генерится как `admin_{ADMIN_IDS}` если пусто → `/admin?admin_token=admin_123456789`
- `PUBLIC_URL` авто-детектится из `RENDER_EXTERNAL_URL`, `RAILWAY_PUBLIC_DOMAIN` и т.д.
- `TON_WALLET_ADDRESS` можно задать позже через `/admin` без редеплоя (сохраняется в БД)
- `BOT_TOKEN` / `ADMIN_BOT_TOKEN` — если пусто, боты отключаются, веб продолжает работать

Полный минимальный пример:

```ini
TONAPI_KEY=...
ADMIN_IDS=1896036065
TON_WALLET_ADDRESS=EQ... # можно задать позже в /admin
BOT_TOKEN=123456:токен # опционально, для Telegram ботов
ADMIN_PANEL_TOKEN=... # опционально, авто-генерится
```

### Правило «секреты только в панель»

Не-секретные настройки зашиты в код — блок `SITE_*` в начале `config.py`:
- `SITE_PUBLIC_URL`, `SITE_CONTACT_USERNAME`, `SITE_PAYMENT_LINK`, `SITE_CHANNELS`, `SITE_ADMIN_IDS`

ENV-переменные имеют приоритет и переопределяют код. Полный список — в `.env.example`.

## Локальный запуск

```bash
cp .env.example .env   # впиши токены
pip install -r requirements.txt
python main.py
```

Веб: `http://localhost:8080/` — витрина Mini App
API: `/api/products`, `/api/config`, `/admin?admin_token=...`

Для превью без Telegram: `ALLOW_DEV_AUTH=1` (на проде `0`).

## Оплата TONAPI

1. Клиент создает заказ → получает мемо `ORDER-123`
2. Переводит TON/GRAM на `TON_WALLET_ADDRESS` с комментарием `ORDER-123`
3. `tonapi_poll` каждые 30 сек проверяет блокчейн через TONAPI и автоподтверждает
4. Если кошелек не задан — ручное подтверждение в `/admin`
