import pytest

from unittest.mock import AsyncMock, patch

from tortoise.exceptions import IntegrityError

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
async def test_redirect_not_found(client, mock_redis, mock_publish):
    resp = await client.get("/nonexistent", follow_redirects=False)
    assert resp.status_code == 404
    mock_publish.assert_not_called()


@pytest.mark.asyncio
async def test_redirect_caches_and_publishes(client, mock_redis, mock_publish):
    create = await client.post(
        "/api/v1/links", json={"original_url": "https://example.com/target"}
    )
    code = create.json()["short_code"]
    cache_key = f"link:{code}"  # Такой же ключ, как в роутере

    # Первый редирект: cache miss → идём в БД, кешируем, публикуем событие
    resp = await client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://example.com/target"

    # Проверяем, что стучались в кэш с правильным ключом
    mock_redis.get.assert_awaited_once_with(cache_key)

    # Проверяем, что записали в кэш (можно проверить точные аргументы, если нужно)
    mock_redis.set.assert_awaited_once()

    # Проверяем, что событие клика опубликовано
    mock_publish.assert_awaited_once_with(code)

    # Второй редирект: эмулируем попадание в кеш
    mock_redis.get.return_value = "https://example.com/target"
    resp2 = await client.get(f"/{code}", follow_redirects=False)
    assert resp2.status_code == 307

    # Убеждаемся, что в БД/Redis повторно не писали (set вызван только 1 раз за оба запроса)
    assert mock_redis.set.await_count == 1


@pytest.mark.asyncio
async def test_create_link_retries_on_collision(client, mock_redis):
    real_create = __import__("app.models.link", fromlist=["Link"]).Link.create
    calls = {"n": 0}

    async def flaky_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("duplicate key")
        return await real_create(**kwargs)

    with patch("app.services.shortener.Link.create", side_effect=flaky_create):
        resp = await client.post(
            "/api/v1/links", json={"original_url": "https://example.com/x"}
        )
    assert resp.status_code == 201
    assert calls["n"] == 2