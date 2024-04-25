import dataclasses

from rtorrent_rpc import RTorrent
from rtorrent_rpc import RTorrent as _RTorrent
from rtorrent_rpc.helper import parse_comment, parse_tags

r = RTorrent(address="scgi://127.0.0.1:5000")

print(r.system_list_methods())


@dataclasses.dataclass
class Tracker:
    hash: str
    index: int
    enabled: bool
    url: str


@dataclasses.dataclass(kw_only=False)
class Torrent:
    name: str
    hash: str
    directory_base: str
    tags: set[str]
    comment: str
    is_open: bool
    is_private: bool
    is_complete: bool
    is_hashing: bool
    state: int

    size_bytes: int


@dataclasses.dataclass(kw_only=False)
class File:
    name: str
    size: int


class RTorrent(_RTorrent):
    def get_files(self, info_hash: str) -> list[File]:
        """use json rpc incase there are emoji in filename"""

        rr = self.jsonrpc.call(
            "f.multicall", [info_hash, "", "f.path=", "f.size_bytes="]
        )

        return [File(name=r[0], size=r[1]) for r in rr]

    def get_trackers(self, hash: str) -> list[Tracker]:
        return [
            Tracker(
                hash=hash,
                index=i,
                enabled=x[0],
                url=x[1],
            )
            for i, x in enumerate(
                self.jsonrpc.call(
                    "t.multicall",
                    [hash, "", "t.is_enabled=", "t.url="],
                )
            )
        ]

    def get_torrents(self, *extras: str) -> dict[str, Torrent]:
        return {
            x[1]: Torrent(
                name=x[0],
                hash=x[1],
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
            for x in self.jsonrpc.call(
                "d.multicall2",
                [
                    "",
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
                ],
            )
        }


client = RTorrent("scgi://192.168.1.3:5000")
