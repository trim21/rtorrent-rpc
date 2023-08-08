from rtorrent_rpc import RTorrent

r = RTorrent(address="scgi://127.0.0.1:5000")

print(r.system_list_methods())
