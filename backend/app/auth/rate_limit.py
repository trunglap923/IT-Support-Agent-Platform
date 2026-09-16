"""Redis-backed fixed-window protection for login attempts."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

LOGIN_BUCKET_PREFIX = "auth:login"
CONSUME_ATTEMPT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""


class LoginRateLimitUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LoginRateLimitExceeded(RuntimeError):
    retry_after_seconds: int


def login_bucket_key(*, email: str, client_identifier: str) -> str:
    normalized_email = email.strip().casefold()
    digest = hashlib.sha256(f"{client_identifier}\0{normalized_email}".encode()).hexdigest()
    return f"{LOGIN_BUCKET_PREFIX}:{digest}"


class LoginRateLimiter:
    def __init__(self, redis_client: Redis, *, max_attempts: int, window_seconds: int) -> None:
        self.redis = redis_client
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    async def consume(self, *, email: str, client_identifier: str) -> None:
        key = login_bucket_key(email=email, client_identifier=client_identifier)
        try:
            result = cast(
                list[int],
                await cast(
                    Awaitable[object],
                    self.redis.eval(
                        CONSUME_ATTEMPT_SCRIPT,
                        1,
                        key,
                        str(self.window_seconds),
                    ),
                ),
            )
        except (RedisError, TimeoutError) as error:
            raise LoginRateLimitUnavailable("Login protection is unavailable") from error
        count, ttl = int(result[0]), max(int(result[1]), 1)
        if count > self.max_attempts:
            raise LoginRateLimitExceeded(retry_after_seconds=ttl)

    async def reset(self, *, email: str, client_identifier: str) -> None:
        key = login_bucket_key(email=email, client_identifier=client_identifier)
        try:
            await self.redis.delete(key)
        except (RedisError, TimeoutError) as error:
            raise LoginRateLimitUnavailable("Login protection is unavailable") from error
