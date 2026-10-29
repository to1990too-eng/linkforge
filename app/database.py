from tortoise import Tortoise

from app.config import settings


async def init_db() -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["app.models.link"]},
    )
    await Tortoise.generate_schemas()


async def close_db() -> None:
    await Tortoise.close_connections()