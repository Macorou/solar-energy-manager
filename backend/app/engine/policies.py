from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DevicePolicy:
    device_id: str
    mode: str = 'solar'
    start_surplus_w: float = 0
    start_delay_s: float = 60
    import_tolerance_w: float = 0
    stop_delay_s: float = 180
    min_run_s: float = 0
    restart_delay_s: float = 60
    target: float | None = None
    armed: bool = False
    vehicle_id: str = ''
    soc_max_age_s: float = 1800
    manual_until: datetime | None = None
    off_peak: bool = False
    start_not_before: datetime | None = None
    solar_target: float | None = None

