"""最小化 backend：仅提供商城会话所需的 SSL/连接池（完整版见上游 LCSC3D）。"""
from __future__ import annotations

import ssl
from functools import lru_cache
from urllib.parse import urlsplit, unquote

import certifi
import urllib3


@lru_cache(maxsize=1)
def shared_ssl_context():
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


@lru_cache(maxsize=4)
def connection_pool(proxy=None):
    kwargs = dict(num_pools=8, maxsize=6, block=True, ssl_context=shared_ssl_context())
    if not proxy:
        return urllib3.PoolManager(**kwargs)
    proxy = proxy if '://' in proxy else 'http://' + proxy
    parsed = urlsplit(proxy)
    if parsed.username is not None:
        credentials = unquote(parsed.username) + ':' + unquote(parsed.password or '')
        kwargs['proxy_headers'] = urllib3.util.make_headers(proxy_basic_auth=credentials)
    return urllib3.ProxyManager(proxy, **kwargs)
