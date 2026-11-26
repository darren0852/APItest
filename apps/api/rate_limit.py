"""Rate limiter using Redis fixed-window counter with in-memory fallback."""
import redis, os, time, threading

REDIS_URL = os.environ.get("REDIS_URL", "")

class RateLimiter:
    def __init__(self, redis_url=None):
        url = redis_url or REDIS_URL
        self.r = None
        self._mem: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()
        if url and os.getenv("USE_REDIS_RATE_LIMIT", "0") == "1":
            try:
                self.r = redis.Redis.from_url(
                    url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self.r.ping()
            except Exception:
                self.r = None

    def _mem_get(self, key: str) -> int:
        with self._lock:
            entry = self._mem.get(key)
            return entry[0] if entry else 0

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Fixed-window counter. Returns (allowed, remaining)."""
        window = int(time.time() // window_seconds)
        counter_key = f"{key}:{window}"
        if self.r is not None:
            try:
                current = self.r.incr(counter_key)
                if current == 1:
                    self.r.expire(counter_key, window_seconds)
                if current > limit:
                    self.r.decr(counter_key)
                    return False, 0
                return True, limit - current
            except Exception:
                pass
        with self._lock:
            current = self._mem.get(counter_key, (0, 0))[0] + 1
            self._mem[counter_key] = (current, window)
        if current > limit:
            with self._lock:
                self._mem[counter_key] = (current - 1, window)
            return False, 0
        return True, limit - current

    def increment_concurrency(self, key_id: int) -> int:
        redis_key = f"concurrency:{key_id}"
        if self.r is not None:
            try:
                current = int(self.r.incr(redis_key))
                self.r.expire(redis_key, 3600)
                return current
            except Exception:
                pass
        with self._lock:
            current = self._mem.get(redis_key, (0, 0))[0] + 1
            self._mem[redis_key] = (current, 0)
        return current

    def try_acquire_concurrency(self, key_id: int, limit: int = 5) -> bool:
        if limit <= 0:
            return False
        redis_key = f"concurrency:{key_id}"
        if self.r is not None:
            try:
                current = int(self.r.incr(redis_key))
                if current > limit:
                    self.r.decr(redis_key)
                    return False
                self.r.expire(redis_key, 3600)
                return True
            except Exception:
                pass
        with self._lock:
            current = self._mem.get(redis_key, (0, 0))[0] + 1
            if current > limit:
                return False
            self._mem[redis_key] = (current, 0)
        return True

    def decrement_concurrency(self, key_id: int) -> int:
        redis_key = f"concurrency:{key_id}"
        if self.r is not None:
            try:
                current = int(self.r.get(redis_key) or 0)
                if current > 0:
                    self.r.decr(redis_key)
                    return current - 1
                return 0
            except Exception:
                pass
        with self._lock:
            current = self._mem.get(redis_key, (0, 0))[0]
            if current > 0:
                self._mem[redis_key] = (current - 1, 0)
                return current - 1
        return 0

    def concurrency(self, key_id: int) -> int:
        redis_key = f"concurrency:{key_id}"
        if self.r is not None:
            try:
                return int(self.r.get(redis_key) or 0)
            except Exception:
                pass
        return self._mem_get(redis_key)

RATE_LIMITER = RateLimiter()
