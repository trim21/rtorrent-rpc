from pathlib import Path

from rtorrent_rpc import RTorrent


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
