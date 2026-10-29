from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

# Импортируем модуль с редиректом, чтобы патчить переменные внутри него
from app.routers import redirect as redirect_router
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
    fake.get = AsyncMock(return_value=None)  # по умолчанию кэш пустой
    fake.set = AsyncMock(return_value=True)

    # Патчим функцию get_redis, чтобы она возвращала наш мок
    monkeypatch.setattr(redirect_router, "get_redis", lambda: fake)
    return fake


@pytest.fixture
def mock_publish(monkeypatch):
    publisher = AsyncMock()
    # Патчим publish_click прямо в роутере редиректа
    monkeypatch.setattr(redirect_router, "publish_click", publisher)
    return publisher


@pytest.fixture
async def client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac