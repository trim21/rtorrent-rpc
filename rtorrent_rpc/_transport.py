from __future__ import annotations

import base64
import os
import socket
import ssl
import xmlrpc.client
from typing import Any, Protocol
from urllib.parse import urlparse

import certifi
import urllib3
from urllib3 import HTTPConnectionPool, HTTPHeaderDict, HTTPSConnectionPool

from rtorrent_rpc import _scgi as scgi


class Transport(Protocol):
    def request(self, body: bytes, content_type: str | None = None) -> bytes:
        """encode request data and return response body"""


_VALIDATE_ENV_KEY = "PY_RTORRENT_RPC_DISABLE_TLS_CERT"

class BadStatusError(Exception):
    status: int
    body: bytes

    def __init__(self, status: int, body: bytes):
        super().__init__(f"unexpected response status code {status} {body!r}")
        self.status = status
        self.body = body

class AuthError(Exception):
    message: str

    def __init__(self, message: str):
        super().__init__(f"invalid auth configuration: {message}")
        self.message = message

class _SCGITransport(Transport):
    def _connect(self) -> socket.socket:
        raise NotImplementedError

    def request(self, body: bytes, content_type: str | None = None) -> bytes:
        with self._connect() as conn:
            for chunk in scgi.encode_request(body, content_type):
                conn.sendall(chunk)

            chunks = []
            while True:
                chunk = conn.recv(4096)
                if chunk:
                    chunks.append(chunk)
                else:
                    break

        _res_header, res_body = scgi.parse_response(b"".join(chunks))

        return res_body


class _SCGIUnixTransport(_SCGITransport):
    __path: str
    __timeout: float | None

    __slots__ = ("__path", "__timeout")

    def __init__(self, path: str, timeout: float | None) -> None:
        self.__path = path
        self.__timeout = timeout

    def _connect(self) -> socket.socket:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.__path)
        sock.settimeout(self.__timeout)
        return sock


class _SCGITcpTransport(_SCGITransport):
    __host: str
    __port: int
    __timeout: float | None

    __slots__ = ("__host", "__path", "__timeout")

    def __init__(self, host: str, port: int, timeout: float | None) -> None:
        self.__host = host
        self.__port = port
        self.__timeout = timeout

    def _connect(self) -> socket.socket:
        return socket.create_connection(
            (self.__host, self.__port), timeout=self.__timeout
        )


class _HTTPTransport(Transport):
    _pool: HTTPConnectionPool

    def __init__(self, address: str, username: str | None, password: str | None, timeout: float | None) -> None:
        self.address = address
        u = urlparse(address)
        self.host = u.hostname
        self.headers = HTTPHeaderDict()
        self.port = u.port
        self.u = u
        assert self.host, "address missing host"

        if self.u.scheme == "http":
            if username or password:
                raise AuthError("Username or Password supplied, refusing to use them over HTTP")
            self._pool = HTTPConnectionPool(self.host, self.port, timeout=timeout)
        elif self.u.scheme == "https":
            if username and password:
                auth_string = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
                self.headers.add("Authorization", f"Basic {auth_string}")
            if os.environ.get(_VALIDATE_ENV_KEY) == "1":
                self._pool = HTTPSConnectionPool(
                    self.host, self.port,
                    timeout=timeout,
                    cert_reqs=ssl.CERT_NONE
                )

                # Since we want to connect to an insecure host, ignore the warning about it.
                urllib3.disable_warnings()
            else:
                self._pool = HTTPSConnectionPool(
                    self.host,
                    self.port,
                    ca_certs=certifi.where(),
                    cert_reqs=ssl.CERT_REQUIRED,
                    timeout=timeout
                )

    def request(self, body: bytes, content_type: str | None = None) -> bytes:
        if content_type:
            self.headers.add("Content-Type", content_type)

        res = self._pool.request(
            method="POST",
            url=self.address,
            body=body,
            redirect=False,
            headers=self.headers
        )

        res_body = res.data
        if res.status == 401 and self.headers.get("Authorization"):
            raise AuthError("Server refused username or password")
        if res.status == 401 and not self.headers.get("Authorization"):
            raise AuthError("Server requires Authorization, but none supplied")
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
