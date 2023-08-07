import io

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
#
import socket
import string
import urllib
import urllib.parse
import xmlrpc.client
from typing import Any

__all__ = ["SCGITransport", "SCGIServerProxy"]

NULL = b"\x00"


class SCGITransport(xmlrpc.client.Transport):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.verbose = False

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
        self, host: str, handler: str, request_body: bytes, verbose: bool = False
    ) -> Any:
        # Add SCGI headers to the request.
        header = self.encode_scgi_headers(len(request_body))
        scgi_request = header + b"," + request_body

        sock = None

        try:
            if host:
                host, port = splitport(host)
                addr_info = socket.getaddrinfo(
                    host, port, socket.AF_INET, socket.SOCK_STREAM
                )
                sock = socket.socket(*addr_info[0][:3])
                sock.connect(addr_info[0][4])
            else:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(handler)

            self.verbose = verbose

            sock.send(scgi_request)
            return self.parse_response(sock.makefile(encoding="utf-8"))
        finally:
            if sock:
                sock.close()

    def response_split_header(self, response):
        try:
            index = response.index("\n")
            while response[index + 1] not in string.whitespace:
                index = response.index("\n", index + 1)

        except (ValueError, IndexError) as e:
            msg = "Unable to split response into header and body sections"
            raise ValueError(msg) from e

        offset = 2  # Know at least the following character is whitespace
        try:
            while response[index + offset] in string.whitespace:
                offset += 1
        except IndexError:
            return response, ""  # Reached the end - there is no body

        # Split by and remove the whitespace
        return response[:index], response[index + offset :]

    def parse_response(self, response: io.TextIOBase) -> tuple[Any]:  # type: ignore
        p, u = self.getparser()

        response_body = ""
        while True:
            data = response.read(1024)
            if not data:
                break
            response_body += data

        # Remove SCGI headers from the response.
        response_header, response_body = self.response_split_header(response_body)

        if self.verbose:
            print("body:", repr(response_body))

        p.feed(response_body)
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
        super().__init__("http://thiswillbe/overwritten", transport=transport, **kwargs)

        # Fix the result of the junk above
        # The names are weird here because of name mangling. See:
        #  https://docs.python.org/3/tutorial/classes.html#private-variables
        self._ServerProxy__host, self._ServerProxy__handler = u.netloc, u.path

        if not self._ServerProxy__handler:
            self._ServerProxy__handler = "/"


def is_non_digit(character: str) -> bool:
    return character not in string.digits


def splitport(hostport: str) -> tuple[str, str | None]:
    """
    splitport('host:port') --> 'host', 'port'.

    This functionality use to (sort of) be provided by urllib as
     `urllib.splithost` in python2, but has since been removed.
    """

    try:
        host, port = hostport.split(":", 1)  # ValueError if there is no colon
    except ValueError:
        return hostport, None

    # Port should contain only digits
    if any(map(is_non_digit, port)):
        return hostport, None

    return host, port
