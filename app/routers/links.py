from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl

from app.config import settings
from app.models.link import Link
from app.services.shortener import generate_code

router = APIRouter(prefix="/api/v1/links", tags=["links"])


class LinkCreateRequest(BaseModel):
    original_url: HttpUrl


class LinkCreateResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str


class LinkStatsResponse(BaseModel):
    short_code: str
    original_url: str
    click_count: int


@router.post("", response_model=LinkCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_link(payload: LinkCreateRequest) -> LinkCreateResponse:
    # Пробуем сгенерировать уникальный код (коллизии крайне редки, но обрабатываем)
    for _ in range(5):
        code = generate_code()
        if not await Link.exists(short_code=code):
            break
    else:
        raise HTTPException(status_code=500, detail="Could not generate unique code")

    link = await Link.create(short_code=code, original_url=str(payload.original_url))
    return LinkCreateResponse(
        short_code=link.short_code,
        short_url=f"{settings.base_url}/{link.short_code}",
        original_url=link.original_url,
    )


@router.get("/{code}/stats", response_model=LinkStatsResponse)
async def get_stats(code: str) -> LinkStatsResponse:
    link = await Link.get_or_none(short_code=code)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return LinkStatsResponse(
        short_code=link.short_code,
        original_url=link.original_url,
        click_count=link.click_count,
    )