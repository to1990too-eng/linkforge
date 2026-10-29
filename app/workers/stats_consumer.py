import asyncio
import json
import logging

from app.database import close_db, init_db
from app.models.link import Link
from app.rabbit import close_rabbit, get_queue, init_rabbit

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def handle_message(message) -> None:
    async with message.process():
        try:
            payload = json.loads(message.body.decode())
            code = payload["short_code"]
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Bad message: %s", exc)
            return

        link = await Link.get_or_none(short_code=code)
        if link is None:
            logger.info("Link %s not found, skipping", code)
            return

        link.click_count += 1
        await link.save(update_fields=["click_count"])
        logger.info("Click recorded for %s (total=%d)", code, link.click_count)


async def main() -> None:
    await init_db()
    await init_rabbit()
    queue = get_queue()
    logger.info("Stats consumer started, listening on %s", queue.name)

    try:
        await queue.consume(handle_message)
        await asyncio.Future()  # run forever
    finally:
        await close_rabbit()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())