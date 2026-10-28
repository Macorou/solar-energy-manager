from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CommandIntent:
    id: str
    device_id: str
    action: str
    limit_w: float | None = None
    expires_at: datetime | None = None
    reason: str = ''
    target_temperature: float | None = None


@dataclass(frozen=True)
class CommandResult:
    id: str
    accepted: bool
    observed: bool = False
    error: str | None = None
    checked_at: datetime | None = None
