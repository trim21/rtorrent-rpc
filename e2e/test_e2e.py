from pathlib import Path

from rtorrent_rpc import RTorrent


def test_unix_path():
    p = Path(__file__).joinpath("../..").joinpath("tests/fixtures/run/rtorrent.sock")
    t = RTorrent("scgi://" + p.resolve().as_posix())

    assert t.system_list_methods()
    assert t.jsonrpc.call("system.listMethods", [])


def test_tcp():
    t = RTorrent("scgi://127.0.0.1:5000")
    assert t.system_list_methods()

    assert t.system_list_methods()
    assert t.jsonrpc.call("system.listMethods", [])
