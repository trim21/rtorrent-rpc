from __future__ import annotations

import xmlrpc.client
from typing import Any

from rtorrent_rpc.jsonrpc import _SCGITransport
from rtorrent_rpc.scgi import parse_response


class SCGITransport(xmlrpc.client.Transport):
    def __init__(self, *args: Any, address: str, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._trx = _SCGITransport(address)

    def single_request(
        self,
        host: str | tuple[str, dict[str, str]],
        handler: str,
        request_body: Any,
        verbose: bool = False,
    ) -> Any:
        # Add SCGI headers to the request.
        return self._parse_response(self._trx.request(request_body, "application/xml"))

    def _parse_response(self, response_data: bytes) -> Any:

        header, body = parse_response(response_data)

        p, u = self.getparser()

        p.feed(body)
        p.close()

        return u.close()
