from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from app.config import settings
from app.services.shortener import create_unique_link
from app.services.url_validator import validate_public_url

router = APIRouter(prefix="/api/v1/links", tags=["links"])


class LinkCreateRequest(BaseModel):
    original_url: str

    @field_validator("original_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        return validate_public_url(v)


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
    try:
        link = await create_unique_link(payload.original_url)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not allocate short code, try again",
        ) from exc

    return LinkCreateResponse(
        short_code=link.short_code,
        short_url=f"{settings.base_url}/{link.short_code}",
        original_url=link.original_url,
    )


@router.get("/{code}/stats", response_model=LinkStatsResponse)
async def get_stats(code: str) -> LinkStatsResponse:
    from app.models.link import Link
    link = await Link.get_or_none(short_code=code)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return LinkStatsResponse(
        short_code=link.short_code,
        original_url=link.original_url,
        click_count=link.click_count,
    )