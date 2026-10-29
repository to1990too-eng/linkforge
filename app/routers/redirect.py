from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings
from app.models.link import Link
from app.rabbit import publish_click
from app.redis_client import get_redis

router = APIRouter(tags=["redirect"])


@router.get("/{code}")
async def redirect(code: str) -> RedirectResponse:
    redis = get_redis()
    cache_key = f"link:{code}"

    # 1) Cache-Aside: сначала Redis
    original_url = await redis.get(cache_key)

    # 2) Cache miss — идём в БД
    if original_url is None:
        link = await Link.get_or_none(short_code=code)
        if link is None:
            raise HTTPException(status_code=404, detail="Link not found")
        original_url = link.original_url
        await redis.set(cache_key, original_url, ex=settings.cache_ttl_seconds)

    # 3) Асинхронно публикуем событие клика — не блокируем ответ
    await publish_click(code)

    return RedirectResponse(url=original_url, status_code=307)