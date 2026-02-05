# Telegram‑бот Ferum — runbook

## 1) Где живёт бот

- Код: `apps/ferum_custom/telegram_bot`
- Процесс bench: `Procfile` (строка `telegram-bot: ...`)
- Логи bench:
  - `logs/telegram-bot.log`
  - `logs/telegram-bot.error.log`

## 2) Конфигурация (env)

Минимум:

- `FERUM_TELEGRAM_BOT_TOKEN`
- `FERUM_TELEGRAM_MODE=polling|webhook`

Для работы с ERP API:

- `FERUM_FRAPPE_BASE_URL`
- `FERUM_FRAPPE_API_KEY`
- `FERUM_FRAPPE_API_SECRET`

Webhook‑режим:

- `FERUM_TELEGRAM_WEBHOOK_URL` (публичный базовый URL, доступный Telegram)
- `FERUM_TELEGRAM_WEBHOOK_PATH` (по умолчанию `/tg-bot/webhook`)
- `FERUM_TELEGRAM_WEBHOOK_SECRET` (рекомендуется)
- `FERUM_TELEGRAM_WEBHOOK_HOST` (по умолчанию `0.0.0.0`)
- `FERUM_TELEGRAM_WEBHOOK_PORT` (по умолчанию `8080`)

Опционально:

- `FERUM_TELEGRAM_ALLOWED_CHAT_IDS` (через запятую)
- `FERUM_TELEGRAM_REQUIRE_REGISTRATION` (0/1)
- `FERUM_TELEGRAM_RESTART_BACKOFF_SECONDS` (секунды; по умолчанию 5)

## 3) Быстрая диагностика

1. Самотест (не печатает секреты):
   - `./env/bin/python apps/ferum_custom/telegram_bot/selftest.py`
2. Проверить, что webhook‑сервер жив:
   - `curl -s http://127.0.0.1:8080/tg-bot/health`
3. Проверить DNS резолвинг Telegram API:
   - `python -c "import socket; print(socket.getaddrinfo('api.telegram.org', 443)[:1])"`

## 4) Типовые причины «бот не отвечает»

1. **DNS сломан**: `api.telegram.org` не резолвится.
   - Частый симптом: `/etc/resolv.conf` указывает `nameserver 127.0.0.53` внутри контейнера без `systemd-resolved`.
   - Решение: настроить нормальные DNS‑серверы на уровне контейнера/VM (docker compose `dns: [...]`, правильный `/etc/resolv.conf`, или запуск systemd-resolved).
2. **Webhook недоступен Telegram**:
   - Нет публичного HTTPS‑доступа к `FERUM_TELEGRAM_WEBHOOK_URL + FERUM_TELEGRAM_WEBHOOK_PATH`.
   - Нет проксирования на `:8080`.
3. **Неверный токен** или токен отозван.
4. **Ошибки ERP API** (бот не может прочитать/создать данные) — см. `logs/telegram-bot.error.log`.

## 5) Рекомендации по режимам

- `polling` — проще для локальной разработки (не нужен публичный URL).
- `webhook` — лучше для продакшена (ниже задержки), но требует корректного прокси и DNS.
