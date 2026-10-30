from unittest.mock import AsyncMock, patch

import pytest
from tortoise.exceptions import IntegrityError


# ==========================================
# 1. УСПЕШНЫЕ СЦЕНАРИИ (Happy Path)
# ==========================================

@pytest.mark.asyncio
async def test_create_link_success(client, mock_redis):
    resp = await client.post(
        "/api/v1/links", json={"original_url": "https://example.com/some/long/path"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["original_url"] == "https://example.com/some/long/path"
    assert len(data["short_code"]) == 7
    assert data["short_url"].endswith(data["short_code"])


@pytest.mark.asyncio
async def test_redirect_caches_and_publishes(client, mock_redis, mock_publish):
    # Создаем ссылку
    create = await client.post(
        "/api/v1/links", json={"original_url": "https://example.com/target"}
    )
    code = create.json()["short_code"]

    # Проверяем редирект (первый раз - cache miss, идем в БД)
    resp = await client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com/target"

    # Проверяем, что кеш записался и событие улетело в RabbitMQ
    mock_redis.set.assert_awaited_once()
    mock_publish.assert_awaited_once_with(code)

    # Эмулируем попадание в кеш (второй раз - cache hit)
    mock_redis.get.return_value = "https://example.com/target"
    resp2 = await client.get(f"/{code}", follow_redirects=False)
    assert resp2.status_code == 307
    # Убеждаемся, что в БД повторно не ходили (set не вызывался второй раз)
    assert mock_redis.set.await_count == 1


# ==========================================
# 2. НЕГАТИВНЫЕ СЦЕНАРИИ (404, SSRF)
# ==========================================

@pytest.mark.asyncio
async def test_redirect_not_found(client, mock_redis, mock_publish):
    resp = await client.get("/nonexistent", follow_redirects=False)
    assert resp.status_code == 404
    mock_publish.assert_not_called()


@pytest.mark.asyncio
async def test_stats_not_found(client, mock_redis):
    resp = await client.get("/api/v1/links/doesnot1/stats")
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_url", [
    "http://169.254.169.254/latest/meta-data/",  # AWS metadata SSRF
    "http://127.0.0.1/admin",  # Localhost
    "http://10.0.0.1/internal",  # Private IP
    "ftp://example.com/file",  # Bad scheme
])
async def test_create_link_rejects_bad_urls(client, mock_redis, bad_url):
    resp = await client.post("/api/v1/links", json={"original_url": bad_url})
    assert resp.status_code == 422


# ==========================================
# 3. ТЕСТЫ НА ГОНКИ И ДУБЛИ (Edge Cases)
# ==========================================

@pytest.mark.asyncio
async def test_create_link_retries_on_collision(client, mock_redis):
    """Проверяем, что при коллизии кода (IntegrityError) срабатывает ретрай."""
    from app.models.link import Link as LinkModel

    # Сохраняем оригинальный метод create
    real_create = LinkModel.create
    calls = {"n": 0}

    # Создаем "флаки" (нестабильный) метод: первый раз падает, второй - работает
    async def flaky_create(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("duplicate key")
        return await real_create(*args, **kwargs)

    # Подменяем метод create в модуле shortener
    with patch("app.services.shortener.Link.create", side_effect=flaky_create):
        resp = await client.post(
            "/api/v1/links", json={"original_url": "https://example.com/x"}
        )

    assert resp.status_code == 201
    assert calls["n"] == 2  # Убеждаемся, что было 2 вызова (1 падение + 1 успех)


@pytest.mark.asyncio
async def test_worker_deduplicates_messages(setup_db, mock_redis):
    """Проверяем, что воркер не накручивает клики при дублировании сообщений."""
    from app.models.link import Link as LinkModel
    from app.workers.stats_consumer import handle_message

    # Создаем тестовую ссылку в БД
    await LinkModel.create(short_code="abc1234", original_url="https://e.com")

    # Эмулируем поведение Redis SETNX:
    # Первый вызов возвращает True (ключ установлен), второй — None (ключ уже есть)
    state = {"seen": False}

    async def fake_set(key, value, nx=False, ex=None):
        if state["seen"]:
            return None
        state["seen"] = True
        return True

    # Подменяем метод set у нашего мока Redis
    mock_redis.set = AsyncMock(side_effect=fake_set)

    # Фейковый объект сообщения из RabbitMQ
    class FakeMessage:
        message_id = "msg-1"
        body = b'{"short_code": "abc1234"}'

        def process(self):
            # Заглушка для контекстного менеджера message.process()
            class Ctx:
                async def __aenter__(self_inner): return self_inner

                async def __aexit__(self_inner, *a): return False

            return Ctx()

    # Отправляем одно и то же сообщение дважды
    await handle_message(FakeMessage())
    await handle_message(FakeMessage())

    # Проверяем БД: клик должен засчитаться ТОЛЬКО ОДИН РАЗ
    refreshed = await LinkModel.get(short_code="abc1234")
    assert refreshed.click_count == 1