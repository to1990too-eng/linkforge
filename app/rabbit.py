import json
import uuid
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue

from app.config import settings

QUEUE_NAME = "link_clicks"
EXCHANGE_NAME = "link_events"

_connection: AbstractConnection | None = None
_channel: AbstractChannel | None = None
_queue: AbstractQueue | None = None


async def init_rabbit() -> None:
    global _connection, _channel, _queue

    # Устанавливаем соединение
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)

    # mypy теперь знает, что это AbstractChannel
    _channel = await _connection.channel()

    exchange = await _channel.declare_exchange(
        EXCHANGE_NAME, ExchangeType.DIRECT, durable=True
    )

    # mypy теперь знает, что это AbstractQueue
    _queue = await _channel.declare_queue(QUEUE_NAME, durable=True)

    await _queue.bind(exchange, routing_key=QUEUE_NAME)


async def close_rabbit() -> None:
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None


async def publish_click(short_code: str) -> None:
    if _channel is None:
        return  # graceful degradation: без брокера редирект всё равно работает

    # _channel здесь точно не None, mypy это понимает
    exchange = await _channel.get_exchange(EXCHANGE_NAME)

    payload: dict[str, Any] = {"short_code": short_code}
    await exchange.publish(
        Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            message_id=str(uuid.uuid4()),  # ключ для идемпотентности
        ),
        routing_key=QUEUE_NAME,
    )


def get_queue() -> AbstractQueue:
    if _queue is None:
        raise RuntimeError("RabbitMQ is not initialized")
    return _queue