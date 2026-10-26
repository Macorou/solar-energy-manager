from dataclasses import dataclass
from datetime import datetime
from app.settings import ChargeProgram


@dataclass(frozen=True)
class ChargeOccurrence:
    id: str
    program_id: str
    vehicle_id: str
    network_start_at: datetime
    solar_start_at: datetime
    deadline_at: datetime
    target_soc: float
    state: str = 'pending'


@dataclass(frozen=True)
class ChargeAuthorization:
    vehicle_id: str
    allow_grid: bool = False
    allow_solar: bool = False
    target_soc: float = 80
    expires_at: datetime | None = None
    reason: str = ''
