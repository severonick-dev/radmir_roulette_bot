# Деплой на сервер (Ubuntu 24.04)

Бот работает на **long-polling** — SSL/webhook/nginx для него **не нужны**
(достаточно исходящего интернета к Telegram). Домен `proxels-web.ru` и его
SSL уже настроены; понадобятся позже, если перейдём на webhook (см. конец).

## 0. Что нужно
- сервер `62.109.31.233`, SSH-порт `2222`, Ubuntu 24.04
- репозиторий `github.com/severonick-dev/radmir_roulette_bot`
- ключи: `BOT_TOKEN` (Telegram), `AI_API_KEY` (RouterAI), свой Telegram ID (`ADMIN_IDS`)

## 1. Подключиться
```bash
ssh -p 2222 root@62.109.31.233
```

## 2. Системные пакеты
```bash
apt update
apt install -y git python3-venv python3-pip fonts-dejavu-core
```
`fonts-dejavu-core` — чтобы подписи на схеме зала были кириллицей, а не `▯▯`.

## 3. Склонировать репозиторий
```bash
git clone https://github.com/severonick-dev/radmir_roulette_bot.git /opt/radmir-bot
cd /opt/radmir-bot
```
Если репозиторий приватный — git спросит логин: вместо пароля вставь
Personal Access Token (GitHub → Settings → Developer settings → PAT),
либо сделай репозиторий публичным.

## 4. Виртуальное окружение и зависимости
```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## 5. Создать .env (секреты; в git его нет)
```bash
cat > /opt/radmir-bot/.env <<'EOF'
BOT_TOKEN=8803444070:AAEvxsdHjZkdpn61mhibN8VloCllIuXMFpo
ADMIN_IDS=ВПИШИ_СВОЙ_TELEGRAM_ID
DATABASE_URL=sqlite+aiosqlite:///./radmir.db
ANALYSIS_WINDOW=300
AI_API_KEY=sk-eYb0Ds7hmEcR2tHHrK5DRNr5EfMYT1Jz
AI_BASE_URL=https://routerai.ru/api/v1
AI_MODEL=deepseek/deepseek-v4-flash
AI_MAX_TOKENS=2000
AI_TEMPERATURE=0.3
PUBLIC_URL=https://proxels-web.ru
LOG_LEVEL=INFO
EOF
nano /opt/radmir-bot/.env   # впиши свой ADMIN_IDS (узнать у @userinfobot)
```
> DB-файл `radmir.db` создастся в `/opt/radmir-bot` (WorkingDirectory сервиса).

## 6. Проверить запуск вручную
```bash
.venv/bin/python -m src.bot.main
```
Ожидаем `Бот запущен: @caz_gospodryad_bot`. Открой бота в Telegram, `/start`.
Останови `Ctrl+C` и переходи к сервису.

## 7. systemd-сервис (автозапуск + перезапуск при падении)
```bash
cp /opt/radmir-bot/deploy/radmir-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now radmir-bot
systemctl status radmir-bot     # active (running)
journalctl -u radmir-bot -f     # логи в реальном времени
```

## Обновление после изменений в репозитории
```bash
cd /opt/radmir-bot && git pull && .venv/bin/pip install -r requirements.txt && systemctl restart radmir-bot
```

## Тесты на сервере (опционально)
```bash
.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q
```

## Если Telegram недоступен с сервера (RU-хостинг)
Симптом в логах: `TelegramNetworkError: Request timeout error` на `getUpdates`
(короткие запросы вроде `get_me` проходят, а long-poll виснет). Это троттлинг
`api.telegram.org` со стороны провайдера/РКН. Решение — прокси:
```bash
# в .env добавить рабочий SOCKS5/HTTP прокси (вне RU-фильтрации):
#   TELEGRAM_PROXY=socks5://user:pass@host:port
nano /opt/radmir-bot/.env
.venv/bin/pip install -r requirements.txt   # подтянет aiohttp-socks
systemctl restart radmir-bot
```
Альтернатива — держать бота на не-RU VDS (тогда прокси не нужен).

## ВАЖНО: один поллер за раз
Telegram отдаёт апдейты только одному процессу. Пока сервис запущен, не
запускай бота с тем же токеном где-то ещё (локально) — будет `409 Conflict`.

---

## (Позже) переход на webhook через proxels-web.ru
Нужен, только если захотим убрать polling. Тогда: nginx проксирует
`https://proxels-web.ru/tg/<секрет>` → локальный порт бота, а в коде
`start_polling` меняем на `bot.set_webhook(...)` + aiohttp-сервер aiogram.
SSL на домене уже есть (Let's Encrypt). Для MVP это не требуется.
