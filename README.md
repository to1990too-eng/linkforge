![CI](https://github.com/1990too-eng/linkforge/actions/workflows/ci.yml/badge.svg)

# LinkForge 🔗

Асинхронный микросервис для сокращения ссылок на FastAPI.

## ✨ Возможности

- Создание коротких ссылок с уникальным кодом (7 символов, base62).
- Быстрый редирект через **Cache-Aside** (Redis, TTL 1 час).
- Асинхронный подсчёт кликов через **RabbitMQ** + фоновый воркер.
- Уникальный индекс на `short_code` в MySQL.
- Полное покрытие тестами (pytest + httpx + AsyncMock, SQLite in-memory).

## 🧱 Стек

| Слой            | Технология                 |
|-----------------|----------------------------|
| Язык            | Python 3.11                |
| API             | FastAPI (async)            |
| ORM             | Tortoise-ORM               |
| БД              | MySQL 8                    |
| Кеш             | Redis 7                    |
| Брокер          | RabbitMQ 3 (management)    |
| Тесты           | pytest, httpx, AsyncMock   |
| Инфраструктура  | Docker, docker-compose     |

## 🚀 Запуск

```bash
cp .env.example .env          # при необходимости поправь значения
docker compose up -d --build
```

- API: http://localhost:8000/docs
- RabbitMQ UI: http://localhost:15672 (guest/guest)

### Локальный запуск без app-контейнера

```bash
docker compose up -d mysql redis rabbitmq
uvicorn app.main:app --reload
python -m app.workers.stats_consumer   # отдельным терминалом
```

### Тесты

```bash
pytest -v
```

## 📊 Пример использования

```bash
curl -X POST http://localhost:8000/api/v1/links \
  -H "Content-Type: application/json" \
  -d '{"original_url": "https://example.com/very/long/path"}'

curl -i http://localhost:8000/<short_code>
curl http://localhost:8000/api/v1/links/<short_code>/stats
```

## 🎯 Как проект закрывает требования вакансии

| Требование                | Реализация                                                                                   |
|---------------------------|----------------------------------------------------------------------------------------------|
| Микросервисность          | HTTP-слой и воркер статистики разделены, общаются через RabbitMQ                             |
| Асинхронность             | FastAPI + `redis.asyncio` + `aio-pika` + Tortoise-ORM                                        |
| Кеширование               | Паттерн Cache-Aside в Redis, TTL 1 час                                                       |
| Брокеры сообщений         | Очередь `link_clicks`, durable exchange `link_events`, отдельный consumer                    |
| Индексы в БД              | `UNIQUE INDEX` на `short_code` — редирект без Full Table Scan                                |
| Тестирование              | pytest, `httpx.ASGITransport`, `AsyncMock` для Redis/Rabbit, SQLite in-memory                |
| Безопасность секретов     | Всё в `.env`, в репозиторий только `.env.example`                                            |
| Контейнеризация           | `docker-compose.yml` с healthcheck-ами + multi-stage-friendly `Dockerfile`                   |

## 🧠 Почему так

- **Почему RabbitMQ?** Редирект должен отдаваться за миллисекунды. Запись статистики — не критичный путь, поэтому публикуем событие в очередь, а воркер пишет в БД в фоне.
- **Почему Redis?** Популярные ссылки не должны бить в MySQL. Cache-Aside с TTL 1 час.
- **Почему уникальный индекс?** Без него редирект = Full Table Scan → падение под нагрузкой.
- **Почему `publish_click` не падает без брокера?** Редирект важнее статистики — graceful degradation.

## 📁 Структура

См. `app/` — роутеры, модели, клиенты Redis/RabbitMQ, воркер. Тесты в `tests/`.