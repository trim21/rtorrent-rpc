import pytest
import os

from pathlib import Path
from urllib3.exceptions import MaxRetryError
from rtorrent_rpc import RTorrent
from rtorrent_rpc._transport import BadAuthConfiguration

def test_unix_path():
    p = Path(__file__, "../fixtures/run/rtorrent.sock").resolve()

    assert p.exists(), "please start developing container in 'e2e/fixtures' first"

    t = RTorrent("scgi://" + p.as_posix())

    assert t.system_list_methods()
    assert t.jsonrpc.call("system.listMethods", [])


def test_tcp():
    t = RTorrent("scgi://127.0.0.1:5001")

    assert t.system_list_methods()
    assert t.jsonrpc.call("system.listMethods", [])

def test_http_plain_no_auth():
    t = RTorrent(address="http://127.0.0.1:8080/plain")
    assert t.jsonrpc.call("system.listMethods", [])

def test_http_plain_with_auth():
    with pytest.raises(BadAuthConfiguration) as exc:
        t = RTorrent(address="http://127.0.0.1:8080/plain", username="test", password="test")
        t.jsonrpc.call("system.listMethods", [])

    assert "Username or Password supplied, refusing to use them over HTTP" in str(exc.value)

def test_https_plain_no_auth():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = "1"
    t = RTorrent(address="https://127.0.0.1:8443/plain")
    assert t.jsonrpc.call("system.listMethods", [])

def test_https_basic_without_auth():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = "1"
    with pytest.raises(BadAuthConfiguration) as exc:
        t = RTorrent(address="https://127.0.0.1:8443/basic")
        t.jsonrpc.call("system.listMethods", [])

    assert "Server requires Authorization, but none supplied" in str(exc.value)

def test_https_basic_with_ok_auth():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = "1"
    t = RTorrent(address="https://127.0.0.1:8443/basic", username="test", password="test")
    t.jsonrpc.call("system.listMethods", [])

def test_https_basic_with_wrong_auth():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = "1"

    with pytest.raises(BadAuthConfiguration) as exc:
        t = RTorrent(address="https://127.0.0.1:8443/basic", username="test", password="WRONG")
        t.jsonrpc.call("system.listMethods", [])

    assert "Server refused username or password" in str(exc.value)

def test_https_refuse_cert():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = ""

    with pytest.raises(MaxRetryError) as exc:
        t = RTorrent(address="https://127.0.0.1:8443/plain")
        t.jsonrpc.call("system.listMethods", [])

    assert "self-signed certificate" in str(exc.value)