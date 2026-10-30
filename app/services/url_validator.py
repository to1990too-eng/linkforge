import ipaddress
import socket

from pydantic import HttpUrl, field_validator

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = {"http", "https"}


def _is_private_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # Не резолвится — пропускаем дальше (может быть валидный домен, недоступный из контейнера)
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return True
    return False


def validate_public_url(value: str) -> str:
    if len(value) > MAX_URL_LENGTH:
        raise ValueError(f"URL longer than {MAX_URL_LENGTH} chars")

    parsed = HttpUrl(value)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError("Only http/https allowed")
    if parsed.host is None:
        raise ValueError("URL must have a host")

    if _is_private_host(parsed.host):
        raise ValueError("Private/internal hosts are not allowed")

    return str(parsed)