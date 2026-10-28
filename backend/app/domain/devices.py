from dataclasses import dataclass, field
from datetime import datetime
from app.domain.measurements import Sample


@dataclass(frozen=True)
class DeviceSpec:
    id: str
    kind: str
    capabilities: tuple[str, ...] = ()
    min_power_w: float = 0
    max_power_w: float = 0
    priority: int = 1
    grid_phases: tuple[str,...] = ()
    voltage: float = 230
    min_current_a: int = 6
    max_current_a: int = 32


@dataclass(frozen=True)
class DeviceState:
    id: str
    observed_power: Sample | None = None
    observed_state: str = 'unknown'
    connected: bool = False
    fault: str | None = None
    target_reached: bool = False
    temperature: float | None = None
    target_temperature: float | None = None
    measured_at: datetime | None = None
    vehicle_connected: bool | None = None
    energy_wh: float | None = None
    energy_measured_at: datetime | None = None
    currents: dict[str,Sample] = field(default_factory=dict)


@dataclass(frozen=True)
class Reservation:
    device_id: str
    power_w: float
    command_id: str
    expires_at: datetime


@dataclass(frozen=True)
class CapabilityReport:
    supported: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()
    verified_at: datetime | None = None
    hardware_verified: bool = False
