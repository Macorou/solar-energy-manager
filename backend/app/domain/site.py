from dataclasses import dataclass, field
from datetime import datetime
from app.domain.measurements import Sample
from app.domain.devices import DeviceState, Reservation
from app.domain.vehicles import VehicleTelemetry


@dataclass(frozen=True)
class SiteSnapshot:
    at: datetime
    grid: Sample | None = None
    solar: Sample | None = None
    device_states: dict[str, DeviceState] = field(default_factory=dict)
    vehicle_telemetry: dict[str, VehicleTelemetry] = field(default_factory=dict)
    reservations: tuple[Reservation, ...] = ()
    site_limit_w: float | None = None
    export_margin_w: float = 100
    sample_max_age_s: float = 30
    transition_blocked: bool = False
    house: Sample | None = None
    phase_currents: dict[str,Sample | None] = field(default_factory=dict)
    phase_voltages: dict[str,Sample | None] = field(default_factory=dict)
    phase_powers: dict[str,Sample | None] = field(default_factory=dict)
    phase_limits_a: dict[str,float] = field(default_factory=dict)
    phase_control_enabled: bool = False
    phase_margin_a: float = 1
    price: Sample | None = None

