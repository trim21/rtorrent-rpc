from __future__ import annotations

import os
import socket
import ssl
import xmlrpc.client
from typing import Any, Protocol
from urllib.parse import urlparse

import certifi
from urllib3 import HTTPConnectionPool, HTTPSConnectionPool

from rtorrent_rpc import _scgi as scgi


class Transport(Protocol):
    def request(self, data: bytes, content_type: str | None = None) -> bytes:
        """encode request data and return response body"""


_VALIDATE_ENV_KEY = "PY_RTORRENT_RPC_DISABLE_TLS_CERT"


class BadStatusError(Exception):
    status: int
    body: bytes

    def __init__(self, status: int, body: bytes):
        super().__init__(f"unexpected response status code {status} {body}")
        self.status = status
        self.body = body


class _SCGITransport(Transport):
    __host: str
    __port: int

    __path: str | None

    __slots__ = ("__host", "__port", "__path")

    def __init__(self, address: str) -> None:
        u = urlparse(address)
        self.__path = None
        if u.hostname:
            # tcp
            assert u.port
            self.__host = u.hostname
            assert u.port, "scgi over tcp must have a port number"
            self.__port = u.port
        else:
            # unix domain
            self.__path = u.path

    def request(self, body: bytes, content_type: str | None = None) -> bytes:
        with self.__connect() as conn:
            for chunk in scgi.encode_request(body, content_type):
                conn.send(chunk)

            chunks = []
            while True:
                chunk = conn.recv(4096)
                if chunk:
                    chunks.append(chunk)
                else:
                    break

        res_header, res_body = scgi.parse_response(b"".join(chunks))

        return res_body

    def __connect(self) -> socket.socket:
        if self.__path:
            # unix domain socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.__path)
            return sock

        # tcp
        # we don't need to support scgi over tls, so just omit
        return socket.create_connection((self.__host, self.__port))


class _HTTPTransport(Transport):
    _pool: HTTPConnectionPool

    def __init__(self, address: str) -> None:
        self.address = address
        u = urlparse(address)
        assert u.hostname
        self.host = u.hostname
        self.port = u.port
        self.u = u

        if self.u.scheme == "http":
            self._pool = HTTPConnectionPool(self.host, self.port)
        elif self.u.scheme == "https":
            if os.environ.get(_VALIDATE_ENV_KEY) == "1":
                self._pool = HTTPSConnectionPool(self.host, self.port)
            else:
                self._pool = HTTPSConnectionPool(
                    self.host,
                    self.port,
                    ca_certs=certifi.where(),
                    cert_reqs=ssl.CERT_REQUIRED,
                )

    def request(self, body: bytes, content_type: str | None = None) -> bytes:
        headers = {}
        if content_type:
            headers["content-type"] = content_type

        res = self._pool.request(
            method="POST",
            url=self.address,
            body=body,
            redirect=False,
            headers=headers,
        )

        res_body = res.data
        if res.status not in (200, 204):
            raise BadStatusError(res.status, res_body)
        return res_body


class SCGIXmlTransport(xmlrpc.client.Transport):
    def __init__(self, *args: Any, transport: Transport, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._trx = transport

    def single_request(
        self,
        host: str | tuple[str, dict[str, str]],
        handler: str,
        request_body: Any,
        verbose: bool = False,
    ) -> Any:
        # Add SCGI headers to the request.
        return self._parse_response(self._trx.request(request_body))

    def _parse_response(self, response_data: bytes) -> Any:
        p, u = self.getparser()

        p.feed(response_data)
        p.close()

        return u.close()
