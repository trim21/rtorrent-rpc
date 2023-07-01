import hashlib
from pathlib import Path
from typing import Any

import bencodepy

__all__ = ["add_completed_resume_file", "get_torrent_info_hash"]


def get_torrent_info_hash(content: bytes) -> str:
    """get torrent info_hash in low case string"""
    data = bencodepy.bdecode(content)
    return hashlib.sha1(bencodepy.bencode(data[b"info"])).hexdigest()


def add_completed_resume_file(base_save_path: Path, torrent_content: bytes) -> bytes:
    """update torrent content, add resume data to torrent.

    based on [rtorrent_fast_resume.pl](https://github.com/rakshasa/rtorrent/blob/master/doc/rtorrent_fast_resume.pl)
    """
    data: dict[bytes, Any] = bencodepy.bdecode(torrent_content)

    piece_length = data[b"info"][b"piece length"]
    files = []

    t_files = data[b"info"].get(b"files")

    piece_count = int(len(data[b"info"][b"pieces"]) / 20)
    if t_files:
        for file in t_files:
            file_path = base_save_path.joinpath(*[p.decode() for p in file[b"path"]])
            if not file_path.exists():
                files.append({b"complete": 0, b"mtime": 0, b"priority": 0})
                continue

            stat = file_path.lstat()
            if stat.st_size == file[b"length"]:
                files.append(
                    {
                        b"complete": int(file[b"length"] / piece_length),
                        b"mtime": int(stat.st_mtime),
                        b"priority": 1,
                    }
                )
            else:
                files.append({b"complete": 0, b"mtime": 0, b"priority": 1})
    else:
        # return torrent_content
        stat = base_save_path.joinpath(data[b"info"][b"name"].decode()).lstat()
        if stat.st_size == data[b"info"][b"length"]:
            files.append(
                {b"complete": piece_count, b"mtime": int(stat.st_mtime), b"priority": 1}
            )
        else:
            return torrent_content

    data[b"rtorrent"] = None
    del data[b"rtorrent"]

    data[b"libtorrent_resume"] = {b"bitfield": piece_count, b"files": files}

    return bencodepy.bencode(data)
