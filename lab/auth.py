"""Account validation and bounded, thread-safe authentication rate limits."""

from collections import deque
import re
import threading
import time


def credentials(raw):
    username, password = raw.get("username"), raw.get("password")
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
        raise ValueError("Username must be 3–30 letters, numbers, or underscores.")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ValueError("Password must contain 8–128 characters.")
    return username, password


class AuthLimiter:
    """20 auth attempts / IP / 15 minutes; 10 / username / 15 minutes.

    One server process with multiple threads is deliberate: this in-memory
    limiter must share its counters. Persisted records have cross-process locks.
    """

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.buckets = {}
        self.lock = threading.Lock()

    def allow(self, address, username):
        now = self.clock()
        limits = [(f"ip:{address}", 20), (f"user:{username.lower()}", 10)]
        with self.lock:
            for key in list(self.buckets):
                bucket = self.buckets[key]
                while bucket and bucket[0] <= now - 900:
                    bucket.popleft()
                if not bucket:
                    del self.buckets[key]
            if any(len(self.buckets.get(key, ())) >= limit for key, limit in limits):
                return False
            # Bound memory even if an attacker rotates both usernames and IPs.
            if len(self.buckets) > 10000:
                return False
            for key, _ in limits:
                self.buckets.setdefault(key, deque()).append(now)
            return True
