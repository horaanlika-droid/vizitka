# Запуск на БотХосте — какие ENV указывать

## Коротко: минимальный набор для твоего случая (TONAPI_KEY есть)

В панели БотХоста в разделе **Переменные окружения / Environment Variables** укажи:

```env
# --- Боты (обязательно) ---
BOT_TOKEN=1234567890:AAH... твой токен от @BotFather
ADMIN_BOT_TOKEN=1234567890:AAH... можно тот же что и BOT_TOKEN, но лучше отдельный
ADMIN_IDS=1896036065  # твой Telegram ID, узнай через @userinfobot

# --- Веб (обязательно для БотХоста) ---
HOST=0.0.0.0
PORT=8080
PUBLIC_URL=https://твоё-имя.bothost.app  # БотХост выдаёт сам — вставь сюда
WEBAPP_URL=https://твоё-имя.bothost.app  # можно оставить пустым = PUBLIC_URL

# --- TONAPI (у тебя уже есть ключ) ---
TONAPI_KEY=твой_ключ_с_tonapi.io
TON_WALLET_ADDRESS=EQ... или UQ... твой TON кошелек куда принимать оплату
# если принимаешь именно GRAM Jetton, а не TON:
# GRAM_JETTON_MASTER=EQ... адрес мастера GRAM Jetton
# TONAPI_CHECK_INTERVAL=30

# --- Контакты ---
CONTACT_USERNAME=milayaqueen
PAYMENT_LINK=https://yoomoney.ru/to/4100119149767529
CHANNELS=chat_goddes

# --- Админка веб ---
ADMIN_PANEL_TOKEN=придумай_случайный_пароль_123  # для доступа к /admin?admin_token=...

# --- Режимы ---
RUN_WEB=1
RUN_CLIENT_BOT=1
RUN_ADMIN_BOT=1
LOG_LEVEL=INFO
```

### Что это даёт:
- `BOT_TOKEN` + `ADMIN_BOT_TOKEN` — запускаются оба бота (клиентский с игрой и админ-бот для подтверждения заказов)
- `PUBLIC_URL` — нужен для кнопки **🛍 ВИТРИНА** в боте (WebApp) и для webhook оплаты
- `TONAPI_KEY + TON_WALLET_ADDRESS` — **автопроверка платежей**: 
  1. Клиент создает заказ в витрине → получает memo `ORDER-123`
  2. Должен перевести TON/GRAM на твой кошелек с комментарием `ORDER-123`
  3. Каждые 30 сек бот через TONAPI проверяет последние транзакции и если находит memo — автоматически подтверждает заказ и пишет клиенту
  4. Если TONAPI не настроен — заказы падают в ручной режим и ты подтверждаешь их в админ-боте кнопкой ✅

## Полный список переменных (из .env.example)

| Переменная | Обязат.? | Описание |
|---|---|---|
| `BOT_TOKEN` | **да** | Токен основного бота |
| `ADMIN_BOT_TOKEN` | **да** | Токен админ-бота |
| `ADMIN_IDS` | **да** | ID админов через запятую |
| `PUBLIC_URL` | **да для веба** | Внешний https адрес от БотХоста |
| `PORT` / `HOST` | обычно ставит хостинг | `0.0.0.0:8080` |
| `TONAPI_KEY` | **да если хочешь авто-оплату** | Ключ с tonapi.io |
| `TON_WALLET_ADDRESS` | **да с TONAPI** | Кошелек EQ.../UQ... |
| `GRAM_JETTON_MASTER` | нет | Если принимаешь GRAM Jetton |
| `GRAM_WALLET_ADDRESS` | альтернатива TON_WALLET | То же что и TON_WALLET |
| `ADMIN_PANEL_TOKEN` | рекоменд. | Пароль для /admin |
| `CONTACT_USERNAME` | нет | Юзернейм без @ |
| `PAYMENT_LINK` | нет | Fallback ссылка YooMoney |
| `PAYMENTS_PROVIDER` | нет | `auto` / `gram` / `tonapi` / `manual` |
| `GRAM_API_BASE_URL` + `GRAM_API_KEY` | нет | Если у тебя свой платежный API |
| `ALLOW_DEV_AUTH` | нет | `0` на проде, `1` только для превью без Telegram |

## Команда запуска на БотХосте

- **Build command**: `pip install -r requirements.txt`
- **Start command**: `python main.py`
- **Python version**: 3.11+

Логи на старте покажут что запустилось:
```
=== vizitka config ===
web: run=True 0.0.0.0:8080 public=https://...
client_bot: run=True token=OK
admin_bot: run=True token=OK admins=[...]
payments: mode=tonapi gram_api=— tonapi=OK wallet=EQ...…
```

Если видишь `TONAPI poll включен` — всё ок, автопроверка работает.

## Проверка после деплоя

1. Открой `https://твоё-имя.bothost.app/` — должна открыться витрина
2. Открой `https://твоё-имя.bothost.app/api/products` — JSON со списком товаров
3. Открой `https://твоё-имя.bothost.app/admin?admin_token=твой_токен` — веб-админка
4. В Telegram напиши `/start` основному боту — должна появиться кнопка 🛍 ВИТРИНА

## Если TONAPI_KEY есть, но не работает

- Проверь что `TON_WALLET_ADDRESS` — именно тот кошелек, который ты дал в TONAPI dashboard
- Проверь что в TONAPI включен нужный network (mainnet)
- Для GRAM Jetton укажи `GRAM_JETTON_MASTER` — иначе бот будет искать любые входящие TON
- Мемо должно точно совпадать: `ORDER-123` (без пробелов)
- Логи БотХоста покажут `tonapi poll: проверяю X pending заказов`

## Если в логах `ModuleNotFoundError: No module named 'aiosqlite'` (или aiogram/aiohttp)

Это значит, что **build-команда не выполнилась** — БотХост не поставил пакеты из requirements.txt.

1. В панели БотХоста проверь **Build command**: должно быть `pip install -r requirements.txt`
2. Нажми **Redeploy / Пересобрать** (не просто Restart — rebuild)

Страховка: `main.py` теперь сам ставит недостающие пакеты при старте (до первого импорта).
В логах это видно так:

```
startup: не установлены пакеты: aiosqlite, ... — ставлю через pip
startup: зависимости установлены: aiosqlite, ...
```

Первый старт после этого занимает на 10–30 сек дольше (идёт pip install), это нормально.

Готово — копируй из `.env.example` и вставляй в БотХост.
