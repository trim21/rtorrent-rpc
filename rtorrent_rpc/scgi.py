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
import socket
import urllib
import urllib.parse
import xmlrpc.client
from typing import Any

__all__ = ["SCGITransport", "SCGIServerProxy"]

NULL = b"\x00"


class SCGITransport(xmlrpc.client.Transport):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def encode_scgi_headers(self, content_length: int) -> bytes:
        # Need to use an ordered dict because content length MUST be the first
        #  key present in the encoded headers.
        headers = {
            b"CONTENT_LENGTH": str(content_length).encode("utf-8"),
            b"SCGI": b"1",
        }

        encoded = NULL.join(k + NULL + v for k, v in headers.items()) + NULL
        length = str(len(encoded)).encode("utf-8")
        return length + b":" + encoded

    def single_request(
        self,
        host: str | tuple[str, dict[str, str]],
        handler: str,
        request_body: Any,
        verbose: bool = False,
    ) -> Any:
        # Add SCGI headers to the request.
        header = self.encode_scgi_headers(len(request_body))

        with self.__connect(host, handler) as sock:
            sock.send(header)
            sock.send(b",")
            sock.send(request_body)
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
        p, u = self.getparser()

        header, s, body = response_data.partition(b"\r\n\r\n")

        if verbose:
            print("body:", repr(body))

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


def splitport(hostport: str) -> tuple[str, int]:
    """
    splitport('host:port') --> 'host', 'port'.

    This functionality use to (sort of) be provided by urllib as
     `urllib.splithost` in python2, but has since been removed.
    """

    host, _, port = hostport.partition(":")
    return host, int(port)
