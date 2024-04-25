# rtorrent_xmlrpc
# (c) 2011 Roger Que <alerante@bellsouth.net>
# Updated for python3 by Daniel Bowring <contact@danielb.codes>
#
# Python module for interacting with rtorrent's XML-RPC interface
# directly over SCGI, instead of through an HTTP server intermediary.
# Inspired by Glenn Washburn's xmlrpc2scgi.py [1], but subclasses the
# built-in xmlrpclib classes so that it is compatible with features
# such as MultiCall objects.
#
# [1] <http://libtorrent.rakshasa.no/wiki/UtilsXmlrpc2scgi>
from __future__ import annotations

import functools
import socket
import urllib
import urllib.parse
import xmlrpc.client
from typing import Any, Iterator

__all__ = ["SCGITransport", "SCGIServerProxy", "encode_request", "parse_response"]

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


class SCGITransport(xmlrpc.client.Transport):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def single_request(
        self,
        host: str | tuple[str, dict[str, str]],
        handler: str,
        request_body: Any,
        verbose: bool = False,
    ) -> Any:
        # Add SCGI headers to the request.
        with self.__connect(host, handler) as sock:
            for chunk in encode_request(request_body):
                sock.send(chunk)
            with sock.makefile(mode="rb", errors="strict") as res:
                return self._parse_response(res.read(), verbose)

    def __connect(
        self,
        host: str | tuple[str, dict[str, str]],
        handler: str,
    ) -> socket.socket:
        if host:  # tcp
            # maybe a host:port string, or host, x509 info
            # we don't need to support scgi over tls, so just omit
            if not isinstance(host, str):
                raise ValueError("scgi over tls is not supported")
            host, port = splitport(host)
            return socket.create_connection((host, port))
        # unix domain socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(handler)
        return sock

    def _parse_response(self, response_data: bytes, verbose: bool) -> Any:

        header, body = parse_response(response_data)

        if verbose:
            print("body:", repr(body))

        p, u = self.getparser()

        p.feed(body)
        p.close()

        return u.close()


class SCGIServerProxy(xmlrpc.client.ServerProxy):
    def __init__(
        self,
        uri: str,
        transport: xmlrpc.client.Transport | None = None,
        use_datetime: bool = False,
        use_builtin_types: bool = False,
        **kwargs: Any,
    ):
        u = urllib.parse.urlparse(uri)

        if u.scheme != "scgi":
            raise OSError("SCGIServerProxy Only Support XML-RPC over SCGI protocol")

        if transport is None:
            transport = SCGITransport(
                use_datetime=use_datetime, use_builtin_types=use_builtin_types
            )

        # Feed some junk in here, but we'll fix it afterwards
        super().__init__(
            urllib.parse.urlunparse(u._replace(scheme="http")),
            transport=transport,
            **kwargs,
        )


@functools.lru_cache
def splitport(hostport: str) -> tuple[str, int]:
    """
    splitport('host:port') --> 'host', 'port'.

    This functionality use to (sort of) be provided by urllib as
     `urllib.splithost` in python2, but has since been removed.
    """

    host, _, port = hostport.partition(":")
    return host, int(port)
