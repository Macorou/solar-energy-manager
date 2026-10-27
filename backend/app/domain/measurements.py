from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import math


class Quality(StrEnum):
    FRESH = 'fresh'
    STALE = 'stale'
    UNAVAILABLE = 'unavailable'
    ESTIMATED = 'estimated'


@dataclass(frozen=True)
class Sample:
    value: float | None
    unit: str
    source: str
    measured_at: datetime | None
    received_at: datetime
    quality: Quality = Quality.FRESH
    # A successful source read may confirm an unchanged state without changing
    # its provider timestamp (notably HA sensors remaining at zero).
    checked_at: datetime | None = None

    @property
    def availability_at(self) -> datetime | None:
        return self.checked_at or self.measured_at

    def usable(self, now: datetime, max_age_s: float) -> bool:
        return (self.value is not None and math.isfinite(self.value)
                and self.measured_at is not None and self.measured_at <= now
                and self.quality in (Quality.FRESH, Quality.ESTIMATED)
                and self.availability_at is not None
                and 0 <= (now - self.availability_at).total_seconds() <= max_age_s)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
