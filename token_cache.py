from threading import Lock
from typing import NamedTuple
import time


class TokenCacheItem(NamedTuple):
    token_info: dict
    timestamp: int


class TokenCache:

    def __init__(self, ttl, timefunc=time.monotonic):
        self.lock = Lock()
        self.ttl = ttl
        self.data = {}
        self.timefunc = timefunc

    def get(self, token):
        with self.lock:
            item = self.data[token]
        if self.timefunc() - item.timestamp > self.ttl:
            raise KeyError(token)
        return item.token_info

    def set(self, token, token_info):
        item = TokenCacheItem(token_info=token_info, timestamp=self.timefunc())
        with self.lock:
            self.data[token] = item
