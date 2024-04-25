from rtorrent_rpc import _scgi as scgi


def test_encode_request():
    assert b"".join(scgi.encode_request(b"<>", "application/xml")) == (
        b"53:"
        b"CONTENT_LENGTH\x002\x00"
        b"SCGI\x001\x00"
        b"CONTENT_TYPE\x00application/xml\x00"
        b","
        b"<>"
    )


def test_parse_response():
    assert scgi.parse_response(
        b"Content-Type: text/plain; charset=UTF-8\r\n"
        b"Status: 200 OK\r\n"
        b"Content-Length: 2\r\n"
        b"\r\n"
        b"42"
    ) == (
        {
            "status": "200 OK",
            "content-type": "text/plain; charset=UTF-8",
            "content-length": "2",
        },
        b"42",
    )
