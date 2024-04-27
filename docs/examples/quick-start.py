import dataclasses

from rtorrent_rpc import RTorrent
from rtorrent_rpc.helper import parse_comment, parse_tags

r = RTorrent(address="scgi://127.0.0.1:5000")

print(r.system_list_methods())
print(r.rpc.system.listMethods())

# only if your rtorrent support jsonrpc!
print(r.jsonrpc.call("system.listMethods"))


@dataclasses.dataclass
class Torrent:
    name: str
    info_hash: str
    directory_base: str
    tags: set[str]
    comment: str
    is_open: bool
    is_private: bool
    is_complete: bool
    is_hashing: bool
    state: int

    size_bytes: int


def get_torrents() -> dict[str, Torrent]:
    return {
        x[1]: Torrent(
            name=x[0],
            info_hash=x[1],
            directory_base=x[2],
            tags=parse_tags(x[3]),
            comment=parse_comment(x[4]),
            is_open=x[5],
            size_bytes=x[6],
            is_private=x[7],
            state=x[8],
            is_complete=x[9],
            is_hashing=x[10],
        )
        for x in r.d.multicall2(
            "",  # required by rpc, doesn't know why
            "default",
            "d.name=",
            "d.hash=",
            "d.directory_base=",
            "d.custom1=",
            "d.custom2=",
            "d.is_open=",
            "d.size_bytes=",
            "d.is_private=",
            "d.state=",
            "d.complete=",
            "d.hashing=",
        )
    }


@dataclasses.dataclass(kw_only=False)
class File:
    name: str
    size: int


def get_files(info_hash: str) -> list[File]:
    """use json rpc incase there are emoji in filename"""

    files = r.f.multicall(info_hash, "", "f.path=", "f.size_bytes=")

    return [File(name=f[0], size=f[1]) for f in files]


@dataclasses.dataclass
class Tracker:
    info_hash: str
    index: int
    enabled: bool
    url: str


def get_trackers(info_hash: str) -> list[Tracker]:
    return [
        Tracker(
            info_hash=info_hash,
            index=i,
            enabled=x[0],
            url=x[1],
        )
        for i, x in enumerate(r.t.multicall(info_hash, "", "t.is_enabled=", "t.url="))
    ]
