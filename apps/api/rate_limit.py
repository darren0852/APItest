"""Rate limiter using Redis fixed-window counter."""
import redis, os, time

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

class RateLimiter:
    def __init__(self, redis_url=None):
        self.r = redis.Redis.from_url(redis_url or REDIS_URL, decode_responses=True)

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Fixed-window counter. Returns (allowed, remaining)."""
        window = int(time.time() // window_seconds)
        counter_key = f"{key}:{window}"
        current = self.r.incr(counter_key)
        if current == 1:
            self.r.expire(counter_key, window_seconds)
        if current > limit:
            self.r.decr(counter_key)
            return False, 0
        return True, limit - current

    def increment_concurrency(self, key_id: int) -> int:
        redis_key = f"concurrency:{key_id}"
        current = int(self.r.incr(redis_key))
        self.r.expire(redis_key, 3600)
        return current

    def decrement_concurrency(self, key_id: int) -> int:
        redis_key = f"concurrency:{key_id}"
        current = int(self.r.get(redis_key) or 0)
        if current > 0:
            self.r.decr(redis_key)
        return max(current - 1, 0)

    def concurrency(self, key_id: int) -> int:
        return int(self.r.get(f"concurrency:{key_id}") or 0)

RATE_LIMITER = RateLimiter()
