import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from rtorrent_rpc._transport import _HTTPTransport


class _RecordHeaderHandler(BaseHTTPRequestHandler):
    headers_seen: ClassVar[list[dict[str, list[str]]]] = []

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("content-length", "0")))
        seen: dict[str, list[str]] = {}
        for name in ("Content-Type", "X-Api-Key", "Authorization"):
            values = self.headers.get_all(name)
            if values:
                seen[name.lower()] = values
        self.headers_seen.append(seen)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    _RecordHeaderHandler.headers_seen = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _RecordHeaderHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/RPC2"
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join()


def test_content_type_not_accumulated(server: str) -> None:
    t = _HTTPTransport(server, timeout=5, headers={"X-Api-Key": "key"})

    t.request(b"{}", "application/json")
    t.request(b"{}", "application/json")
    t.request(b"<xml/>", "text/xml")

    assert _RecordHeaderHandler.headers_seen == [
        {"x-api-key": ["key"], "content-type": ["application/json"]},
        {"x-api-key": ["key"], "content-type": ["application/json"]},
        {"x-api-key": ["key"], "content-type": ["text/xml"]},
    ]


def test_custom_headers(server: str) -> None:
    t = _HTTPTransport(server, timeout=5, headers={"Authorization": "Basic abc"})

    t.request(b"{}", "application/json")

    assert _RecordHeaderHandler.headers_seen[0]["authorization"] == ["Basic abc"]
