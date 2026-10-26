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

    def usable(self, now: datetime, max_age_s: float) -> bool:
        return (self.value is not None and math.isfinite(self.value)
                and self.measured_at is not None
                and self.quality in (Quality.FRESH, Quality.ESTIMATED)
                and 0 <= (now - self.measured_at).total_seconds() <= max_age_s)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
