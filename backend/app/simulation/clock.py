from datetime import datetime, timedelta, timezone
import time


class Clock:
    def now(self):
        return datetime.now(timezone.utc)

    def monotonic(self):
        return time.monotonic()


class SimulatedClock(Clock):
    def __init__(self, at=None):
        self.at = at or datetime(2026,10,26,12,tzinfo=timezone.utc)
        self.elapsed = 0

    def now(self):
        return self.at

    def monotonic(self):
        return self.elapsed

    def advance(self, seconds):
        self.elapsed += seconds
        self.at += timedelta(seconds=seconds)

