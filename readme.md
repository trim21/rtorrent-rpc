# Typed rtorrent rpc client

[![PyPI](https://img.shields.io/pypi/v/rtorrent-rpc)](https://pypi.org/project/rtorrent-rpc/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/rtorrent-rpc)](https://pypi.org/project/rtorrent-rpc/)

`rtorrent-rpc` is a python wrapper on top of rtorrent XML RPC protocol,
hosted on GitHub at [github.com/trim21/rtorrent-rpc](https://github.com/trim21/rtorrent-rpc)

## Introduction

```console
pip install rtorrent-rpc -U
```

## Contributing

All kinds of PRs (docs, feature, bug fixes and eta...) are most welcome.

## Quick Start

```python
from rtorrent_rpc import RTorrent

client = RTorrent(address='scgi://127.0.0.1:5000')
```

## License

`rtorrent-rpc` is licensed under the MIT license.
