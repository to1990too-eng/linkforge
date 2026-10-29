from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import close_db, init_db
from app.rabbit import close_rabbit, init_rabbit
from app.redis_client import close_redis, init_redis
from app.routers import links, redirect


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    await init_rabbit()
    try:
        yield
    finally:
        await close_rabbit()
        await close_redis()
        await close_db()


app = FastAPI(title="LinkForge", version="1.0.0", lifespan=lifespan)

app.include_router(links.router)
app.include_router(redirect.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}