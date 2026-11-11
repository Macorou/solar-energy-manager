from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import math

# A device reading late by at most this much beyond its freshness limit lets a running
# device keep its current power (never more); a longer delay stops it as before.
MEASUREMENT_GRACE_S = 60
# A source clock (Home Assistant, the station) may run this much ahead of SEM's: a measure
# dated a few seconds in the future is still a measure. Its age is counted from its read.
CLOCK_TOLERANCE_S = 5


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
                and self.measured_at is not None
                and self.measured_at <= now+timedelta(seconds=CLOCK_TOLERANCE_S)
                and self.quality in (Quality.FRESH, Quality.ESTIMATED)
                and self.availability_at is not None
                and 0 <= (now - self.availability_at).total_seconds() <= max_age_s)


def late(sample: Sample | None, now: datetime, max_age_s: float) -> bool:
    """Valid but only delayed: within the grace period after its freshness limit."""
    return bool(sample and sample.value is not None and math.isfinite(sample.value)
                and sample.quality in (Quality.FRESH, Quality.ESTIMATED)
                and sample.measured_at is not None
                and sample.measured_at <= now+timedelta(seconds=CLOCK_TOLERANCE_S)
                and sample.availability_at is not None
                and 0 <= (now - sample.availability_at).total_seconds() <= max_age_s + MEASUREMENT_GRACE_S)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
