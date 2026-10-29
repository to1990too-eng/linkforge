import json
import uuid
from typing import Any

import aio_pika
from aio_pika import Channel, Connection, ExchangeType, Message, Queue

from app.config import settings

QUEUE_NAME = "link_clicks"
EXCHANGE_NAME = "link_events"

_connection: Connection | None = None
_channel: Channel | None = None
_queue: Queue | None = None


async def init_rabbit() -> None:
    global _connection, _channel, _queue
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await _connection.channel()
    exchange = await _channel.declare_exchange(
        EXCHANGE_NAME, ExchangeType.DIRECT, durable=True
    )
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
    exchange = await _channel.get_exchange(EXCHANGE_NAME)
    payload: dict[str, Any] = {"short_code": short_code}
    await exchange.publish(
        Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            message_id=str(uuid.uuid4()),
        ),
        routing_key=QUEUE_NAME,
    )


def get_queue() -> Queue:
    if _queue is None:
        raise RuntimeError("RabbitMQ is not initialized")
    return _queue