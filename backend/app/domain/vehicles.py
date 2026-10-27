from dataclasses import dataclass
from datetime import datetime
import math
from app.domain.measurements import Quality


@dataclass(frozen=True)
class VehicleTelemetry:
    soc: float | None = None
    range_km: float | None = None
    charging_state: str = 'unknown'
    measured_at: datetime | None = None
    received_at: datetime | None = None
    quality: Quality = Quality.UNAVAILABLE

    def usable(self, now: datetime, max_age_s: float) -> bool:
        """A valid old SOC may still be the provider's current available value."""
        return (self.soc is not None and math.isfinite(self.soc) and 0 <= self.soc <= 100
                and self.measured_at is not None and self.measured_at <= now
                and self.received_at is not None
                and self.quality in (Quality.FRESH, Quality.STALE)
                and 0 <= (now - self.received_at).total_seconds() <= max_age_s)

    def fresh(self, now: datetime, max_age_s: float) -> bool:
        return (self.soc is not None and 0 <= self.soc <= 100
                and self.measured_at is not None
                and self.quality == Quality.FRESH
                and 0 <= (now - self.measured_at).total_seconds() <= max_age_s)
