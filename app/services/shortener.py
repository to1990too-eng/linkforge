import logging
import secrets
import string

from tortoise.exceptions import IntegrityError

from app.models.link import Link

logger = logging.getLogger(__name__)

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_RETRIES = 5


def generate_code(length: int = CODE_LENGTH) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


async def create_unique_link(original_url: str) -> Link:
    """
    Пытаемся вставить ссылку. При коллизии кода ловим IntegrityError
    и ретраим с новым кодом. Уникальный индекс — гарант атомарности.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        code = generate_code()
        try:
            return await Link.create(short_code=code, original_url=original_url)
        except IntegrityError as exc:
            last_error = exc
            logger.warning(
                "short_code collision on attempt %d/%d for code=%s",
                attempt + 1, MAX_RETRIES, code,
            )
            continue
    raise RuntimeError("Could not create unique link") from last_error