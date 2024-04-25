"""json rpc implement for rtorrent


!! This is not a general propose json-rpc client.
"""

import json
import threading
from typing import Any
from urllib.parse import urlparse

from rtorrent_rpc._jsonrpc.transport import Transport, _HTTPTransport, _SCGITransport

try:
    import orjson
except ImportError:
    orjson = None  # type: ignore[assignment]

if orjson is None:

    def _decode_json(o: bytes) -> Any:
        return json.loads(o)

    def _encode_json(o: Any) -> bytes:
        return json.dumps(o).encode()

else:

    def _decode_json(o: bytes) -> Any:
        return orjson.loads(o)

    def _encode_json(o: Any) -> bytes:
        return orjson.dumps(o)


__all__ = ["JSONRpcError", "JSONRpc"]


class JSONRpcError(Exception):
    code: int
    message: str
    data: Any
    id: int

    def __init__(self, code: int, message: str, data: Any, id: int):
        super().__init__(code, message)

        self.code = code
        self.message = message
        self.data = data
        self.id = id


class JSONRpc:
    _id: int
    _lock: threading.Lock
    _transport: Transport

    __slots__ = ("__host", "__port", "_id", "_lock", "_transport")

    def __init__(self, address: str):
        url = urlparse(address)

        if url.scheme == "scgi":
            self._transport = _SCGITransport(address)
        elif url.scheme in ("http", "https"):
            self._transport = _HTTPTransport(address)
        else:
            raise ValueError(f"unsupported protocol {url.scheme}")

        self._id = 0
        self._lock = threading.Lock()

    def call(self, method: str, params: Any = None) -> Any:
        with self._lock:
            id = self._id
            # unlikely to have 100w concurrent request...
            self._id = (self._id + 1) % 1000000

        req = _encode_json(
            {"jsonrpc": "2.0", "id": id, "method": method, "params": params}
        )

        res = self._transport.request(req, "application/json")

        data = _decode_json(res)

        assert data["id"] == id, "response.id doesn't match request.id"

        if "error" in data:
            raise JSONRpcError(
                data["error"]["code"],
                data["error"]["message"],
                data["error"].get("data"),
                data["id"],
            )

        return data["result"]
