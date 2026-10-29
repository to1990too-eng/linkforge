import pytest


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