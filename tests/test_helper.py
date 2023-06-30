from pathlib import Path

from rtorrent_rpc.helper import get_torrent_info_hash


def test_get_torrent_info_hash():
    with Path(__file__).joinpath(
        "../fixtures/ubuntu-22.04.2-desktop-amd64.iso.torrent"
    ).resolve().open("rb") as f:
        assert (
            get_torrent_info_hash(f.read())
            == "a7838b75c42b612da3b6cc99beed4ecb2d04cff2"
        )
