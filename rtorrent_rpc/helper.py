import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import bencode2

__all__ = [
    "add_completed_resume_file",
    "get_torrent_info_hash",
    "parse_tags",
    "parse_comment",
]


def parse_tags(s: str) -> set[str]:
    """ruTorrent compatibility method to parse ``d.custom1`` as tags"""
    tags = set()
    for t in s.split(","):
        tt = t.strip()
        if tt:
            tags.add(tt)
    return tags


def parse_comment(s: str) -> str:
    """ruTorrent compatibility method to parse ``d.custom2`` as torrent comment"""
    if s.startswith("VRS24mrker"):
        return unquote(s.removeprefix("VRS24mrker"))
    return s


def get_torrent_info_hash(content: bytes) -> str:
    """get torrent info_hash in low case string"""
    data = bencode2.bdecode(content)
    return hashlib.sha1(bencode2.bencode(data[b"info"])).hexdigest()


def add_completed_resume_file(base_save_path: Path, torrent_content: bytes) -> bytes:
    """update torrent content, add resume data to torrent.

    based on [rtorrent_fast_resume.pl](https://github.com/rakshasa/rtorrent/blob/master/doc/rtorrent_fast_resume.pl)
    """
    data: dict[str, Any] = bencode2.bdecode(torrent_content, str_key=True)

    piece_length = data["info"][b"piece length"]
    files = []

    t_files = data["info"].get("files")

    piece_count = int(len(data["info"]["pieces"]) / 20)
    if t_files:
        for file in t_files:
            file_path = base_save_path.joinpath(*[p.decode() for p in file[b"path"]])
            if not file_path.exists():
                files.append({"complete": 0, "mtime": 0, "priority": 0})
                continue

            stat = file_path.lstat()
            if stat.st_size == file[b"length"]:
                files.append(
                    {
                        "complete": int(file["length"] / piece_length),
                        "mtime": int(stat.st_mtime),
                        "priority": 1,
                    }
                )
            else:
                files.append({"complete": 0, "mtime": 0, "priority": 1})
    else:
        try:
            stat = base_save_path.joinpath(data["info"]["name"].decode()).lstat()
        except FileNotFoundError:
            return torrent_content

        if stat.st_size == data["info"]["length"]:
            files.append(
                {"complete": piece_count, "mtime": int(stat.st_mtime), "priority": 1}
            )
        else:
            return torrent_content

    data["rtorrent"] = None
    del data["rtorrent"]

    data["libtorrent_resume"] = {"bitfield": piece_count, "files": files}

    return bencode2.bencode(data)
