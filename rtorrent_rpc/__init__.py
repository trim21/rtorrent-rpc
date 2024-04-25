from __future__ import annotations

import time
import urllib
import urllib.parse
import xmlrpc.client
from collections.abc import Iterable
from typing import Any, Literal, Protocol
from urllib.parse import quote

import bencode2
from typing_extensions import NotRequired, TypeAlias, TypedDict

from rtorrent_rpc._jsonrpc import JSONRpc, JSONRpcError
from rtorrent_rpc._jsonrpc.transport import BadStatusError
from rtorrent_rpc._transport import SsciXmlTransport

__all__ = [
    "RTorrent",
    "MultiCall",
    "RutorrentCompatibilityDisabledError",
    "BadStatusError",
    "JSONRpcError",
]

Unknown: TypeAlias = Any


class RutorrentCompatibilityDisabledError(Exception):
    def __init__(self) -> None:
        super().__init__("you need enable ruTorrent compatibility to use this feature")


class MultiCall(TypedDict):
    methodName: str
    params: NotRequired[Any]


def _encode_tags(tags: Iterable[str] | None) -> str:
    if not tags:
        return ""

    return ",".join(sorted(quote(t) for t in {x.strip() for x in tags} if t))


class _DirectoryRpc(Protocol):
    def __call__(self, info_hash: str, /) -> str: ...

    def set(self, info_hash: str, value: str, /) -> None: ...


class _CustomSet(Protocol):
    def __call__(self, info_hash: str, key: str, /) -> str:
        """get download's custom value"""

    def set(self, info_hash: str, key: str, value: str, /) -> int:
        """set download's custom value"""


class _DownloadRpc(Protocol):
    """this is not a real class, it's a typing protocol for rpc typing"""

    def save_resume(self, info_hash: str) -> None:
        """save resume data"""

    def multicall2(self, _: Literal[""], view: str, *commands: str) -> Iterable[Any]:
        """run multiple rpc calls"""

    @property
    def directory_base(self) -> _DirectoryRpc:
        """base directory"""

    @property
    def directory(self) -> _DirectoryRpc:
        """directory"""

    @property
    def custom(self) -> _CustomSet: ...


class _SystemRpc(Protocol):
    """this is not a real class, it's a typing protocol for rpc typing"""

    def multicall(self, commands: list[MultiCall]) -> Any:
        """run multiple rpc calls"""


class _TrackerRpc(Protocol):
    """this is not a real class, it's a typing protocol for rpc typing"""

    def multicall(
        self, info_hash: str, _: Literal[""], *commands: str
    ) -> Iterable[Any]:
        """run multiple rpc calls"""

    def is_enabled(self, tracker_id: str) -> int:
        """tracker_id is in format ``{info_hash}:t{index}``"""


class _FileRpc(Protocol):
    """this is not a real class, it's a typing protocol for rpc typing"""

    def multicall(
        self, info_hash: str, _: Literal[""], *commands: str
    ) -> Iterable[Any]:
        """run multiple rpc calls"""


class RTorrent:
    """
    RTorrent rpc client

    .. code-block:: python

        rt = RTorrent('scgi://127.0.0.1:5000')
        rt = RTorrent('scgi:///home/ubuntu/.local/rtorrent.sock')

    If you are using ruTorrent or nginx scgi proxy, http(s) protocol are also supported

    .. code-block:: python

        rt = RTorrent('http://127.0.0.1')


    Underling ``xmlrpc.client.ServerProxy`` are exposed as instance property ``.rpc``,
    you can use ``rt.rpc`` for direct rpc call.

    :param address: rtorrent rpc address
    :param rutorrent_compatibility: compatibility for ruTorrent or flood.
    """

    rpc: xmlrpc.client.ServerProxy
    jsonrpc: JSONRpc

    def __init__(self, address: str, rutorrent_compatibility: bool = True):
        u = urllib.parse.urlparse(address)
        if u.scheme == "scgi":
            self.rpc = SCGIServerProxy(address)
        else:
            self.rpc = xmlrpc.client.ServerProxy(address)

        self.jsonrpc = JSONRpc(address=address)

        self.rutorrent_compatibility: bool = rutorrent_compatibility

    def get_session_path(self) -> str:
        """get current rtorrent session path"""
        return self.rpc.session.path()  # type: ignore

    def add_torrent_by_file(
        self,
        content: bytes,
        directory_base: str,
        tags: list[str] | None = None,
    ) -> None:
        """
        Add a torrent to the client by providing the torrent file content as bytes.

        Args:
            content: The content of the torrent file as bytes.
            directory_base: The base directory where the downloaded files will be saved.
            tags: A list of tags associated with the torrent. Defaults to None.
                This argument is compatible with ruTorrent and flood.
        """
        params: list[str | bytes] = [
            "",
            content,
            'd.tied_to_file.set=""',
            f'd.directory_base.set="{directory_base}"',
            # custom.addtime is used by ruTorrent and flood.
            f"d.custom.set=addtime,{int(time.time())}",
        ]

        if tags:
            if not self.rutorrent_compatibility:
                raise RutorrentCompatibilityDisabledError
            params.append(f'd.custom1.set="{_encode_tags(tags)}"')

        if self.rutorrent_compatibility:
            t = bencode2.bdecode(content)
            if b"comment" in t:
                params.append(
                    f'd.custom2.set="VRS24mrker{quote(t[b"comment"].decode().strip())}"'
                )

        self.rpc.load.raw_start_verbose(*params)  # type: ignore

    def stop_torrent(self, info_hash: str) -> None:
        """
        Stop and close a torrent.

        Args:
            info_hash (str): The info hash of the torrent to be stopped.

        Returns:
            None: This function does not return anything.
        """
        self.system.multicall(
            [
                MultiCall(methodName="d.stop", params=[info_hash]),
                MultiCall(methodName="d.close", params=[info_hash]),
            ]
        )

    def start_torrent(self, info_hash: str) -> None:
        self.system.multicall(
            [
                MultiCall(methodName="d.open", params=[info_hash]),
                MultiCall(methodName="d.start", params=[info_hash]),
            ]
        )

    def download_list(self) -> list[str]:
        """get list of info hash for current downloads"""
        return self.rpc.download_list()  # type: ignore

    @property
    def system(self) -> _SystemRpc:
        """method call with ``system`` prefix

        Example:

            .. code-block:: python

                rt.system.listMethods(...)
        """
        return self.rpc.system  # type: ignore

    def system_list_methods(self) -> list[str]:
        """get supported methods"""
        return self.rpc.system.listMethods()  # type: ignore

    @property
    def d(self) -> _DownloadRpc:
        """method call with ``d`` prefix

        Example:

            .. code-block:: python

                rt.d.save_resume(...)
                rt.d.open(...)
        """
        return self.rpc.d  # type: ignore

    def d_set_torrent_base_directory(self, info_hash: str, directory: str) -> None:
        """change base directory of a download.

        you may need to stop/close torrent first.
        """
        self.rpc.d.directory_base.set(info_hash, directory)

    def d_save_resume(self, info_hash: str) -> None:
        """alias of ``d.save_resume``"""
        self.rpc.d.save_resume(info_hash)

    def d_set_tags(self, info_hash: str, tags: Iterable[str]) -> None:
        """set download tags, work with flood and ruTorrent."""
        self.rpc.d.custom1.set(info_hash, _encode_tags(tags))

    def d_set_comment(self, info_hash: str, comment: str) -> None:
        """Set comment, work with flood and ruTorrent"""
        self.rpc.d.custom2.set(info_hash, "VRS24mrker" + quote(comment))

    def d_set_custom(self, info_hash: str, key: str, value: str) -> int:
        """set custom key value pair on download"""
        return self.d.custom.set(info_hash, key, value)

    def d_get_custom(self, info_hash: str, key: str) -> str:
        """get custom value by key, return empty str if key not set"""
        return self.d.custom(info_hash, key)

    def d_tracker_send_scrape(self, info_hash: str, delay: Unknown) -> None:
        self.rpc.d.tracker.send_scrape(info_hash, delay)

    @property
    def t(self) -> _TrackerRpc:
        """method call with ``t`` prefix

        Example:

            .. code-block:: python

                rt.t.is_enabled(...)
        """
        return self.rpc.t  # type: ignore

    def t_enable_tracker(self, info_hash: str, tracker_index: int) -> None:
        """enable a tracker of download"""
        self.rpc.t.is_enabled.set(f"{info_hash}:t{tracker_index}", 1)

    def t_disable_tracker(self, info_hash: str, tracker_index: int) -> None:
        """disable a tracker of download"""
        self.rpc.t.is_enabled.set(f"{info_hash}:t{tracker_index}", 0)

    def d_add_tracker(self, info_hash: str, url: str, *, group: int = 0) -> None:
        """add a tracker to download"""
        self.rpc.d.tracker.insert(info_hash, group, url)

    @property
    def f(self) -> _FileRpc:
        """method call with ``d`` prefix

        Example:

            .. code-block:: python

                rt.f.multicall("<info_hash>", "", "f.path=")
        """
        return self.rpc.f  # type: ignore


_methods = [
    "system.methodExist",
    "system.methodHelp",
    "system.methodSignature",
    "system.multicall",
    "system.shutdown",
    "system.capabilities",
    "system.getCapabilities",
    "add_peer",
    "and",
    "bind",
    "build_branch",
    "cat",
    "catch",
    "check_hash",
    "choke_group.down.heuristics",
    "choke_group.down.heuristics.set",
    "choke_group.down.max",
    "choke_group.down.max.set",
    "choke_group.down.max.unlimited",
    "choke_group.down.queued",
    "choke_group.down.rate",
    "choke_group.down.total",
    "choke_group.down.unchoked",
    "choke_group.general.size",
    "choke_group.index_of",
    "choke_group.insert",
    "choke_group.list",
    "choke_group.size",
    "choke_group.tracker.mode",
    "choke_group.tracker.mode.set",
    "choke_group.up.heuristics",
    "choke_group.up.heuristics.set",
    "choke_group.up.max",
    "choke_group.up.max.set",
    "choke_group.up.max.unlimited",
    "choke_group.up.queued",
    "choke_group.up.rate",
    "choke_group.up.total",
    "choke_group.up.unchoked",
    "close_low_diskspace",
    "close_untied",
    "compare",
    "connection_leech",
    "connection_seed",
    "convert.date",
    "convert.elapsed_time",
    "convert.gm_date",
    "convert.gm_time",
    "convert.kb",
    "convert.mb",
    "convert.throttle",
    "convert.time",
    "convert.xb",
    "d.accepting_seeders",
    "d.accepting_seeders.disable",
    "d.accepting_seeders.enable",
    "d.base_filename",
    "d.base_path",
    "d.bitfield",
    "d.bytes_done",
    "d.check_hash",
    "d.chunk_size",
    "d.chunks_hashed",
    "d.chunks_seen",
    "d.close",
    "d.close.directly",
    "d.complete",
    "d.completed_bytes",
    "d.completed_chunks",
    "d.connection_current",
    "d.connection_current.set",
    "d.connection_leech",
    "d.connection_leech.set",
    "d.connection_seed",
    "d.connection_seed.set",
    "d.create_link",
    "d.creation_date",
    "d.custom",
    "d.custom.if_z",
    "d.custom.items",
    "d.custom.keys",
    "d.custom.set",
    "d.custom1",
    "d.custom1.set",
    "d.custom2",
    "d.custom2.set",
    "d.custom3",
    "d.custom3.set",
    "d.custom4",
    "d.custom4.set",
    "d.custom5",
    "d.custom5.set",
    "d.custom_throw",
    "d.delete_link",
    "d.delete_tied",
    "d.directory",
    "d.directory.set",
    "d.directory_base",
    "d.directory_base.set",
    "d.disconnect.seeders",
    "d.down.choke_heuristics",
    "d.down.choke_heuristics.leech",
    "d.down.choke_heuristics.seed",
    "d.down.choke_heuristics.set",
    "d.down.rate",
    "d.down.sequential",
    "d.down.sequential.set",
    "d.down.total",
    "d.downloads_max",
    "d.downloads_max.set",
    "d.downloads_min",
    "d.downloads_min.set",
    "d.erase",
    "d.free_diskspace",
    "d.group",
    "d.group.name",
    "d.group.set",
    "d.hash",
    "d.hashing",
    "d.hashing_failed",
    "d.hashing_failed.set",
    "d.ignore_commands",
    "d.ignore_commands.set",
    "d.incomplete",
    "d.is_active",
    "d.is_hash_checked",
    "d.is_hash_checking",
    "d.is_meta",
    "d.is_multi_file",
    "d.is_not_partially_done",
    "d.is_open",
    "d.is_partially_done",
    "d.is_pex_active",
    "d.is_private",
    "d.left_bytes",
    "d.load_date",
    "d.loaded_file",
    "d.local_id",
    "d.local_id_html",
    "d.max_file_size",
    "d.max_file_size.set",
    "d.max_size_pex",
    "d.message",
    "d.message.set",
    "d.mode",
    "d.multicall.filtered",
    "d.multicall2",
    "d.name",
    "d.open",
    "d.pause",
    "d.peer_exchange",
    "d.peer_exchange.set",
    "d.peers_accounted",
    "d.peers_complete",
    "d.peers_connected",
    "d.peers_max",
    "d.peers_max.set",
    "d.peers_min",
    "d.peers_min.set",
    "d.peers_not_connected",
    "d.priority",
    "d.priority.set",
    "d.priority_str",
    "d.ratio",
    "d.resume",
    "d.save_full_session",
    "d.save_resume",
    "d.size_bytes",
    "d.size_chunks",
    "d.size_files",
    "d.size_pex",
    "d.skip.rate",
    "d.skip.total",
    "d.start",
    "d.state",
    "d.state_changed",
    "d.state_counter",
    "d.stop",
    "d.throttle_name",
    "d.throttle_name.set",
    "d.tied_to_file",
    "d.tied_to_file.set",
    "d.timestamp.finished",
    "d.timestamp.last_active",
    "d.timestamp.started",
    "d.tracker.insert",
    "d.tracker.send_scrape",
    "d.tracker_announce",
    "d.tracker_announce.force",
    "d.tracker_focus",
    "d.tracker_numwant",
    "d.tracker_numwant.set",
    "d.tracker_size",
    "d.try_close",
    "d.try_start",
    "d.try_stop",
    "d.up.choke_heuristics",
    "d.up.choke_heuristics.leech",
    "d.up.choke_heuristics.seed",
    "d.up.choke_heuristics.set",
    "d.up.rate",
    "d.up.total",
    "d.update_priorities",
    "d.uploads_max",
    "d.uploads_max.set",
    "d.uploads_min",
    "d.uploads_min.set",
    "d.views",
    "d.views.has",
    "d.views.push_back",
    "d.views.push_back_unique",
    "d.views.remove",
    "d.wanted_chunks",
    "dht",
    "dht.add_bootstrap",
    "dht.add_node",
    "dht.mode.set",
    "dht.port",
    "dht.port.set",
    "dht.statistics",
    "dht.throttle.name",
    "dht.throttle.name.set",
    "dht_port",
    "directory",
    "directory.default",
    "directory.default.set",
    "directory.watch.added",
    "download_list",
    "download_rate",
    "elapsed.greater",
    "elapsed.less",
    "encoding.add",
    "encoding_list",
    "encryption",
    "equal",
    "event.download.active",
    "event.download.closed",
    "event.download.erased",
    "event.download.finished",
    "event.download.hash_done",
    "event.download.hash_failed",
    "event.download.hash_final_failed",
    "event.download.hash_queued",
    "event.download.hash_removed",
    "event.download.inactive",
    "event.download.inserted",
    "event.download.inserted_new",
    "event.download.inserted_session",
    "event.download.opened",
    "event.download.paused",
    "event.download.resumed",
    "event.system.shutdown",
    "event.system.startup_done",
    "event.view.hide",
    "event.view.show",
    "execute",
    "execute.capture",
    "execute.capture_nothrow",
    "execute.nothrow",
    "execute.nothrow.bg",
    "execute.raw",
    "execute.raw.bg",
    "execute.raw_nothrow",
    "execute.raw_nothrow.bg",
    "execute.throw",
    "execute.throw.bg",
    "execute2",
    "d.completed_chunks",
    "d.frozen_path",
    "d.is_create_queued",
    "d.is_created",
    "d.is_open",
    "d.is_resize_queued",
    "d.last_touched",
    "d.match_depth_next",
    "d.match_depth_prev",
    "d.multicall",
    "d.offset",
    "d.path",
    "d.path_components",
    "d.path_depth",
    "d.prioritize_first",
    "d.prioritize_first.disable",
    "d.prioritize_first.enable",
    "d.prioritize_last",
    "d.prioritize_last.disable",
    "d.prioritize_last.enable",
    "d.priority",
    "d.priority.set",
    "d.range_first",
    "d.range_second",
    "d.set_create_queued",
    "d.set_resize_queued",
    "d.size_bytes",
    "d.size_chunks",
    "d.unset_create_queued",
    "d.unset_resize_queued",
    "false",
    "fi.filename_last",
    "fi.is_file",
    "file.append",
    "file.prioritize_toc",
    "file.prioritize_toc.first",
    "file.prioritize_toc.first.push_back",
    "file.prioritize_toc.first.set",
    "file.prioritize_toc.last",
    "file.prioritize_toc.last.push_back",
    "file.prioritize_toc.last.set",
    "file.prioritize_toc.set",
    "fs.homedir",
    "fs.homedir.nothrow",
    "fs.mkdir",
    "fs.mkdir.nothrow",
    "fs.mkdir.recursive",
    "fs.mkdir.recursive.nothrow",
    "greater",
    "group.insert",
    "group.insert_persistent_view",
    "group.seeding.ratio.command",
    "group.seeding.ratio.disable",
    "group.seeding.ratio.enable",
    "group2.seeding.ratio.max",
    "group2.seeding.ratio.max.set",
    "group2.seeding.ratio.min",
    "group2.seeding.ratio.min.set",
    "group2.seeding.ratio.upload",
    "group2.seeding.ratio.upload.set",
    "group2.seeding.view",
    "group2.seeding.view.set",
    "if",
    "import",
    "ip",
    "key_layout",
    "keys.layout",
    "keys.layout.set",
    "less",
    "load.normal",
    "load.raw",
    "load.raw_start",
    "load.raw_start_verbose",
    "load.raw_verbose",
    "load.start",
    "load.start_throw",
    "load.start_verbose",
    "load.throw",
    "load.verbose",
    "log.add_output",
    "log.append_file",
    "log.append_gz_file",
    "log.close",
    "log.execute",
    "log.open_file",
    "log.open_file_pid",
    "log.open_gz_file",
    "log.open_gz_file_pid",
    "log.rpc",
    "log.vmmap.dump",
    "match",
    "math.add",
    "math.avg",
    "math.cnt",
    "math.div",
    "math.max",
    "math.med",
    "math.min",
    "math.mod",
    "math.mul",
    "math.sub",
    "max_downloads",
    "max_downloads_div",
    "max_downloads_global",
    "max_memory_usage",
    "max_peers",
    "max_peers_seed",
    "max_uploads",
    "max_uploads_div",
    "max_uploads_global",
    "method.const",
    "method.const.enable",
    "method.erase",
    "method.get",
    "method.has_key",
    "method.insert",
    "method.insert.bool",
    "method.insert.c_simple",
    "method.insert.list",
    "method.insert.s_c_simple",
    "method.insert.simple",
    "method.insert.string",
    "method.insert.value",
    "method.list_keys",
    "method.redirect",
    "method.rlookup",
    "method.rlookup.clear",
    "method.set",
    "method.set_key",
    "method.use_deprecated",
    "method.use_deprecated.set",
    "method.use_intermediate",
    "method.use_intermediate.set",
    "min_downloads",
    "min_peers",
    "min_peers_seed",
    "min_uploads",
    "network.bind_address",
    "network.bind_address.set",
    "network.http.cacert",
    "network.http.cacert.set",
    "network.http.capath",
    "network.http.capath.set",
    "network.http.current_open",
    "network.http.dns_cache_timeout",
    "network.http.dns_cache_timeout.set",
    "network.http.max_open",
    "network.http.max_open.set",
    "network.http.proxy_address",
    "network.http.proxy_address.set",
    "network.http.ssl_verify_host",
    "network.http.ssl_verify_host.set",
    "network.http.ssl_verify_peer",
    "network.http.ssl_verify_peer.set",
    "network.listen.backlog",
    "network.listen.backlog.set",
    "network.listen.port",
    "network.local_address",
    "network.local_address.set",
    "network.max_open_files",
    "network.max_open_files.set",
    "network.max_open_sockets",
    "network.max_open_sockets.set",
    "network.open_files",
    "network.open_sockets",
    "network.port_open",
    "network.port_open.set",
    "network.port_random",
    "network.port_random.set",
    "network.port_range",
    "network.port_range.set",
    "network.proxy_address",
    "network.proxy_address.set",
    "network.receive_buffer.size",
    "network.receive_buffer.size.set",
    "network.scgi.dont_route",
    "network.scgi.dont_route.set",
    "network.scgi.open_local",
    "network.scgi.open_port",
    "network.send_buffer.size",
    "network.send_buffer.size.set",
    "network.tos.set",
    "network.total_handshakes",
    "network.xmlrpc.dialect.set",
    "network.xmlrpc.size_limit",
    "network.xmlrpc.size_limit.set",
    "not",
    "on_ratio",
    "or",
    "p.address",
    "p.banned",
    "p.banned.set",
    "p.call_target",
    "p.client_version",
    "p.completed_percent",
    "p.disconnect",
    "p.disconnect_delayed",
    "p.down_rate",
    "p.down_total",
    "p.id",
    "p.id_html",
    "p.is_encrypted",
    "p.is_incoming",
    "p.is_obfuscated",
    "p.is_preferred",
    "p.is_snubbed",
    "p.is_unwanted",
    "p.multicall",
    "p.options_str",
    "p.peer_rate",
    "p.peer_total",
    "p.port",
    "p.snubbed",
    "p.snubbed.set",
    "p.up_rate",
    "p.up_total",
    "pieces.hash.on_completion",
    "pieces.hash.on_completion.set",
    "pieces.hash.queue_size",
    "pieces.memory.block_count",
    "pieces.memory.current",
    "pieces.memory.max",
    "pieces.memory.max.set",
    "pieces.memory.sync_queue",
    "pieces.preload.min_rate",
    "pieces.preload.min_rate.set",
    "pieces.preload.min_size",
    "pieces.preload.min_size.set",
    "pieces.preload.type",
    "pieces.preload.type.set",
    "pieces.stats.total_size",
    "pieces.stats_not_preloaded",
    "pieces.stats_preloaded",
    "pieces.sync.always_safe",
    "pieces.sync.always_safe.set",
    "pieces.sync.queue_size",
    "pieces.sync.safe_free_diskspace",
    "pieces.sync.timeout",
    "pieces.sync.timeout.set",
    "pieces.sync.timeout_safe",
    "pieces.sync.timeout_safe.set",
    "port_random",
    "port_range",
    "print",
    "protocol.choke_heuristics.down.leech",
    "protocol.choke_heuristics.down.leech.set",
    "protocol.choke_heuristics.down.seed",
    "protocol.choke_heuristics.down.seed.set",
    "protocol.choke_heuristics.up.leech",
    "protocol.choke_heuristics.up.leech.set",
    "protocol.choke_heuristics.up.seed",
    "protocol.choke_heuristics.up.seed.set",
    "protocol.connection.leech",
    "protocol.connection.leech.set",
    "protocol.connection.seed",
    "protocol.connection.seed.set",
    "protocol.encryption.set",
    "protocol.pex",
    "protocol.pex.set",
    "proxy_address",
    "ratio.disable",
    "ratio.enable",
    "ratio.max",
    "ratio.max.set",
    "ratio.min",
    "ratio.min.set",
    "ratio.upload",
    "ratio.upload.set",
    "remove_untied",
    "scgi_local",
    "scgi_port",
    "schedule",
    "schedule2",
    "schedule_remove",
    "schedule_remove2",
    "scheduler.max_active",
    "scheduler.max_active.set",
    "scheduler.simple.added",
    "scheduler.simple.removed",
    "scheduler.simple.update",
    "session",
    "session.name",
    "session.name.set",
    "session.on_completion",
    "session.on_completion.set",
    "session.path",
    "session.path.set",
    "session.save",
    "session.use_lock",
    "session.use_lock.set",
    "start_tied",
    "stop_untied",
    "strings.choke_heuristics",
    "strings.choke_heuristics.download",
    "strings.choke_heuristics.upload",
    "strings.connection_type",
    "strings.encryption",
    "strings.ip_filter",
    "strings.ip_tos",
    "strings.log_group",
    "strings.tracker_event",
    "strings.tracker_mode",
    "system.api_version",
    "system.client_version",
    "system.cwd",
    "system.cwd.set",
    "system.daemon",
    "system.daemon.set",
    "system.env",
    "system.file.allocate",
    "system.file.allocate.set",
    "system.file.max_size",
    "system.file.max_size.set",
    "system.file.split_size",
    "system.file.split_size.set",
    "system.file.split_suffix",
    "system.file.split_suffix.set",
    "system.file_status_cache.prune",
    "system.file_status_cache.size",
    "system.files.closed_counter",
    "system.files.failed_counter",
    "system.files.opened_counter",
    "system.hostname",
    "system.library_version",
    "system.pid",
    "system.shutdown.normal",
    "system.shutdown.quick",
    "system.time",
    "system.time_seconds",
    "system.time_usec",
    "system.umask.set",
    "t.activity_time_last",
    "t.activity_time_next",
    "t.can_scrape",
    "t.disable",
    "t.enable",
    "t.failed_counter",
    "t.failed_time_last",
    "t.failed_time_next",
    "t.group",
    "t.id",
    "t.is_busy",
    "t.is_enabled",
    "t.is_enabled.set",
    "t.is_extra_tracker",
    "t.is_open",
    "t.is_usable",
    "t.latest_event",
    "t.latest_new_peers",
    "t.latest_sum_peers",
    "t.min_interval",
    "t.multicall",
    "t.normal_interval",
    "t.scrape_complete",
    "t.scrape_counter",
    "t.scrape_downloaded",
    "t.scrape_incomplete",
    "t.scrape_time_last",
    "t.success_counter",
    "t.success_time_last",
    "t.success_time_next",
    "t.type",
    "t.url",
    "throttle.down",
    "throttle.down.max",
    "throttle.down.rate",
    "throttle.global_down.max_rate",
    "throttle.global_down.max_rate.set",
    "throttle.global_down.max_rate.set_kb",
    "throttle.global_down.rate",
    "throttle.global_down.total",
    "throttle.global_up.max_rate",
    "throttle.global_up.max_rate.set",
    "throttle.global_up.max_rate.set_kb",
    "throttle.global_up.rate",
    "throttle.global_up.total",
    "throttle.ip",
    "throttle.max_downloads",
    "throttle.max_downloads.div",
    "throttle.max_downloads.div._val",
    "throttle.max_downloads.div._val.set",
    "throttle.max_downloads.div.set",
    "throttle.max_downloads.global",
    "throttle.max_downloads.global._val",
    "throttle.max_downloads.global._val.set",
    "throttle.max_downloads.global.set",
    "throttle.max_downloads.set",
    "throttle.max_peers.normal",
    "throttle.max_peers.normal.set",
    "throttle.max_peers.seed",
    "throttle.max_peers.seed.set",
    "throttle.max_unchoked_downloads",
    "throttle.max_unchoked_uploads",
    "throttle.max_uploads",
    "throttle.max_uploads.div",
    "throttle.max_uploads.div._val",
    "throttle.max_uploads.div._val.set",
    "throttle.max_uploads.div.set",
    "throttle.max_uploads.global",
    "throttle.max_uploads.global._val",
    "throttle.max_uploads.global._val.set",
    "throttle.max_uploads.global.set",
    "throttle.max_uploads.set",
    "throttle.min_downloads",
    "throttle.min_downloads.set",
    "throttle.min_peers.normal",
    "throttle.min_peers.normal.set",
    "throttle.min_peers.seed",
    "throttle.min_peers.seed.set",
    "throttle.min_uploads",
    "throttle.min_uploads.set",
    "throttle.unchoked_downloads",
    "throttle.unchoked_uploads",
    "throttle.up",
    "throttle.up.max",
    "throttle.up.rate",
    "to_date",
    "to_elapsed_time",
    "to_gm_date",
    "to_gm_time",
    "to_kb",
    "to_mb",
    "to_throttle",
    "to_time",
    "to_xb",
    "torrent_list_layout",
    "trackers.disable",
    "trackers.enable",
    "trackers.numwant",
    "trackers.numwant.set",
    "trackers.use_udp",
    "trackers.use_udp.set",
    "true",
    "try",
    "try_import",
    "ui.current_view",
    "ui.current_view.set",
    "ui.input.history.clear",
    "ui.input.history.size",
    "ui.input.history.size.set",
    "ui.status.throttle.down.set",
    "ui.status.throttle.up.set",
    "ui.throttle.global.step.large",
    "ui.throttle.global.step.large.set",
    "ui.throttle.global.step.medium",
    "ui.throttle.global.step.medium.set",
    "ui.throttle.global.step.small",
    "ui.throttle.global.step.small.set",
    "ui.torrent_list.layout",
    "ui.torrent_list.layout.set",
    "ui.unfocus_download",
    "upload_rate",
    "value",
    "view.add",
    "view.event_added",
    "view.event_removed",
    "view.filter",
    "view.filter.temp",
    "view.filter.temp.excluded",
    "view.filter.temp.excluded.set",
    "view.filter.temp.log",
    "view.filter.temp.log.set",
    "view.filter_all",
    "view.filter_download",
    "view.filter_on",
    "view.list",
    "view.persistent",
    "view.set",
    "view.set_not_visible",
    "view.set_visible",
    "view.size",
    "view.size_not_visible",
    "view.sort",
    "view.sort_current",
    "view.sort_new",
    "system.startup_time",
    "d.data_path",
    "d.session_file",
    "cfg.scrape_interval.active",
    "cfg.scrape_interval.active.set",
    "cfg.scrape_interval.idle",
    "cfg.scrape_interval.idle.set",
    "d.last_scrape.send_set",
]


class SCGIServerProxy(xmlrpc.client.ServerProxy):
    def __init__(
        self,
        uri: str,
        transport: xmlrpc.client.Transport | None = None,
        use_datetime: bool = False,
        use_builtin_types: bool = False,
        **kwargs: Any,
    ):
        u = urllib.parse.urlparse(uri)

        if u.scheme != "scgi":
            raise OSError("SCGIServerProxy Only Support XML-RPC over SCGI protocol")

        if transport is None:
            transport = SsciXmlTransport(
                use_datetime=use_datetime,
                address=uri,
                use_builtin_types=use_builtin_types,
            )

        # Feed some junk in here, but we'll fix it afterwards
        super().__init__(
            urllib.parse.urlunparse(u._replace(scheme="http")),
            transport=transport,
            **kwargs,
        )
