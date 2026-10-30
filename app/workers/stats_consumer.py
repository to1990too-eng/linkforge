import asyncio
import json
import logging

from app.database import close_db, init_db
from app.models.link import Link
from app.rabbit import close_rabbit, get_queue, init_rabbit
from app.redis_client import close_redis, get_redis, init_redis

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Время жизни ключа идемпотентности (24 часа)
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


async def handle_message(message) -> None:
    # message.process() автоматически делает ACK при успешном выходе
    # и NACK (возврат в очередь) при возникновении исключения
    async with message.process():
        message_id = message.message_id

        if not message_id:
            logger.warning("Message without message_id, skipping deduplication")
        else:
            redis = get_redis()
            dedup_key = f"idempotency:click:{message_id}"

            # Redis SET с параметрами NX (только если ключа нет) и EX (время жизни).
            # Возвращает True, если ключ был установлен (первая обработка).
            # Возвращает None, если ключ уже существовал (дубликат).
            is_first_time = await redis.set(
                dedup_key, "1", nx=True, ex=IDEMPOTENCY_TTL_SECONDS
            )

            if not is_first_time:
                logger.info("Duplicate message %s detected, skipping", message_id)
                return  # Выходим, сообщение будет удалено из очереди (ACK)

        # Парсинг тела сообщения
        try:
            payload = json.loads(message.body.decode())
            code = payload["short_code"]
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Bad message format: %s", exc)
            return

        # Обновление статистики в БД
        link = await Link.get_or_none(short_code=code)
        if link is None:
            logger.info("Link %s not found, skipping", code)
            return

        link.click_count += 1
        await link.save(update_fields=["click_count"])
        logger.info("Click recorded for %s (total=%d)", code, link.click_count)


async def main() -> None:
    await init_db()
    await init_redis()
    await init_rabbit()

    queue = get_queue()
    logger.info("Stats consumer started, listening on queue: %s", queue.name)

    try:
        await queue.consume(handle_message)
        await asyncio.Future()  # Блокируем event loop навсегда, чтобы воркер работал
    finally:
        logger.info("Shutting down stats consumer...")
        await close_rabbit()
        await close_redis()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())