from __future__ import annotations

import xmlrpc.client
from typing import Any

from rtorrent_rpc._jsonrpc.transport import _SCGITransport


class SsciXmlTransport(xmlrpc.client.Transport):
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
        return self._parse_response(self._trx.request(request_body))

    def _parse_response(self, response_data: bytes) -> Any:
        p, u = self.getparser()

        p.feed(response_data)
        p.close()

        return u.close()
