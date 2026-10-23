import os
from pathlib import Path

import pytest
from urllib3.exceptions import MaxRetryError

from rtorrent_rpc import BadStatusError, RTorrent
from rtorrent_rpc.helper import gen_auth_header


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

def test_https_plain_no_auth():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = "1"
    t = RTorrent(address="https://127.0.0.1:8443/plain")

    assert t.jsonrpc.call("system.listMethods", [])

def test_https_basic_without_auth():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = "1"
    t = RTorrent(address="https://127.0.0.1:8443/basic")

    with pytest.raises(BadStatusError, match=r"unexpected response status code 401.*"):
        t.jsonrpc.call("system.listMethods", [])

def test_auth_header_basic():
    a = gen_auth_header("Basic", auth_data={"username": "test", "password": "test"})
    assert a == {"Authorization": "Basic dGVzdDp0ZXN0"}

def test_auth_header_bearer():
    a = gen_auth_header("Bearer", auth_data={"token": "test"})
    assert a == {"Authorization": "Bearer test"}

def test_auth_header_other():
    with pytest.raises(ValueError, match="Invalid authorization type"):
        gen_auth_header("Other", auth_data={"username": "test", "password": "test"})

def test_https_basic_with_ok_auth():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = "1"
    t = RTorrent(address="https://127.0.0.1:8443/basic", http_headers={"Authorization": "Basic dGVzdDp0ZXN0"})

    assert t.jsonrpc.call("system.listMethods", [])

def test_https_basic_with_wrong_auth():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = "1"
    t = RTorrent(address="https://127.0.0.1:8443/basic", http_headers={"Authorization": "Basic WRONG"})

    with pytest.raises(BadStatusError, match=r"unexpected response status code 401.*"):
        t.jsonrpc.call("system.listMethods", [])

def test_https_refuse_cert():
    os.environ["PY_RTORRENT_RPC_DISABLE_TLS_CERT"] = ""
    t = RTorrent(address="https://127.0.0.1:8443/plain")

    with pytest.raises(MaxRetryError, match="self-signed certificate"):
        t.jsonrpc.call("system.listMethods", [])
