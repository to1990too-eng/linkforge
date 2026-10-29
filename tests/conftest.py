from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

import app.redis_client as redis_module
import app.rabbit as rabbit_module
from app.main import app as fastapi_app


@pytest.fixture(autouse=True)
async def setup_db():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models.link"]},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


@pytest.fixture
def mock_redis(monkeypatch):
    fake = AsyncMock()
    fake.get = AsyncMock(return_value=None)  # всегда cache miss по умолчанию
    fake.set = AsyncMock(return_value=True)
    monkeypatch.setattr(redis_module, "redis_client", fake)
    return fake


@pytest.fixture
def mock_publish(monkeypatch):
    publisher = AsyncMock()
    monkeypatch.setattr(rabbit_module, "publish_click", publisher)
    return publisher


@pytest.fixture
async def client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac