from hashlib import sha256
import json
import redis
from authenticators import TokenInfo


class TokenCache:
    def __init__(self, host, port, ttl_seconds, prefix="tokencache."):
        self.redis = redis.Redis(host=host, port=port)
        self.ttl_seconds = ttl_seconds
        self.prefix = prefix

    def get(self, token: str) -> TokenInfo:
        key = self.get_key(token)
        data = self.redis.get(key)
        if data is None:
            raise KeyError("token not found")
        return TokenInfo(**json.loads(data))

    def set(self, token: str, token_info: TokenInfo):
        key = self.get_key(token)
        data = json.dumps(token_info.__dict__, separators=(",", ":"))
        self.redis.set(key, data, ex=self.ttl_seconds)

    def get_key(self, token):
        hashed_token = sha256(token.encode()).hexdigest()
        return self.prefix + hashed_token
