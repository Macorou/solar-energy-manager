from dataclasses import dataclass
from datetime import datetime
from app.domain.measurements import Quality


@dataclass(frozen=True)
class VehicleTelemetry:
    soc: float | None = None
    range_km: float | None = None
    charging_state: str = 'unknown'
    measured_at: datetime | None = None
    received_at: datetime | None = None
    quality: Quality = Quality.UNAVAILABLE

    def fresh(self, now: datetime, max_age_s: float) -> bool:
        return (self.soc is not None and 0 <= self.soc <= 100
                and self.measured_at is not None
                and self.quality == Quality.FRESH
                and 0 <= (now - self.measured_at).total_seconds() <= max_age_s)
