from __future__ import annotations

from typing import Iterator

__all__ = ["encode_request", "parse_response"]

NULL = b"\x00"


def encode_request(body: bytes, content_type: str | None = None) -> Iterator[bytes]:
    length = len(body)

    header_items: list[bytes] = [
        *(b"CONTENT_LENGTH", NULL, str(length).encode(), NULL),
        *(b"SCGI", NULL, b"1", NULL),
    ]

    if content_type:
        header_items.extend((b"CONTENT_TYPE", NULL, content_type.encode(), NULL))

    header_len = sum(len(c) for c in header_items)

    yield str(header_len).encode()
    yield b":"
    yield from header_items
    yield b","
    yield body


def parse_response(res: bytes) -> tuple[dict[str, str], bytes]:
    """
    Args:
        res: should be full response bytes, including headers and body
    """
    raw_header, _, body = res.partition(b"\r\n\r\n")
    h = __parse_raw_headers(raw_header)
    assert int(h["content-length"].encode()) == len(body)
    return h, body


def __parse_raw_headers(raw: bytes) -> dict[str, str]:
    lines = raw.split(b"\r\n")
    d = {}
    for line in lines:
        key, value = line.split(b":")
        key = key.strip()
        d[key.decode().lower()] = value.strip().decode()
    return d
