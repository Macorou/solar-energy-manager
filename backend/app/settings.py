from pathlib import Path
from datetime import time
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid',allow_inf_nan=False)


class RuntimeSettings(Model):
    data_dir: Path = Path('/data')
    secure_cookie: bool = False
    public_url: str = ''
    start_runtime: bool = False


class CloudSettings(Model):
    start_surplus_w: float = Field(0, ge=0)
    start_delay_s: float = Field(60, ge=0, le=86400)
    import_tolerance_w: float = Field(0, ge=0)
    stop_delay_s: float = Field(180, ge=0, le=86400)
    min_run_s: float = Field(0, ge=0, le=86400)
    restart_delay_s: float = Field(60, ge=0, le=86400)


class DeviceConfig(Model):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    name: str = Field(min_length=1, max_length=120)
    kind: Literal['charger', 'water_heater']
    mode: Literal['off', 'solar', 'planned', 'off_peak_solar', 'manual'] = 'off'
    armed: bool = False
    capabilities_verified: bool = False
    offline_behavior_verified: bool = False
    priority: int = Field(1, ge=1, le=100)
    min_power_w: float = Field(0, ge=0)
    max_power_w: float = Field(0, ge=0)
    min_current_a: int = Field(6, ge=1, le=80)
    max_current_a: int = Field(32, ge=1, le=80)
    phases: Literal[1, 3] = 1
    voltage: float = Field(230, ge=100, le=300)
    charge_point_id: str = ''
    allow_insecure_identity: bool = False
    connector_id: int = Field(1, ge=1)
    vehicle_id: str = ''
    gateway_id: str = ''
    target: float | None = None
    default_soc_target: float = Field(80, ge=1, le=100)
    confirmation_timeout_s: int = Field(90,ge=30,le=3600)
    cloud: CloudSettings = Field(default_factory=CloudSettings)

    @model_validator(mode='after')
    def limits(self):
        if self.max_power_w and self.max_power_w < self.min_power_w:
            raise ValueError('Maximum power must cover the minimum')
        if self.max_current_a < self.min_current_a:
            raise ValueError('Invalid current range')
        return self


class VehicleConfig(Model):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    name: str = 'Peugeot e-208'
    vin: str = ''
    capacity_kwh: float | None = Field(None, gt=0)
    efficiency: float = Field(0.9, gt=0, le=1)


class ChargeProgram(Model):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    name: str = 'Recharge'
    vehicle_id: str
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    earliest_start: str = '22:00'
    deadline: str = '05:45'
    target_soc: float = Field(80, ge=1, le=100)
    solar_early: bool = True
    solar_horizon_hours: float = Field(24, ge=0, le=168)
    enabled: bool = True

    @field_validator('earliest_start', 'deadline')
    @classmethod
    def clock_time(cls, value):
        time.fromisoformat(value)
        return value

    @field_validator('weekdays')
    @classmethod
    def days(cls, value):
        if not value or any(day not in range(7) for day in value):
            raise ValueError('Select days 0 to 6')
        return sorted(set(value))


class OffPeakWindow(Model):
    start: str
    end: str
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)))

    @field_validator('start', 'end')
    @classmethod
    def clock_time(cls, value):
        time.fromisoformat(value)
        return value

    @field_validator('weekdays')
    @classmethod
    def days(cls, value):
        if not value or any(day not in range(7) for day in value):
            raise ValueError('Invalid weekday')
        return sorted(set(value))


class HomeAssistantConfig(Model):
    url: str = ''
    grid_entity: str = ''
    solar_entity: str = ''
    invert_grid: bool = False
    device_power_entities: dict[str, str] = Field(default_factory=dict)


class PeugeotConfig(Model):
    username: str = ''
    client_id: str = ''
    country: str = 'fr'
    poll_interval_s: int = Field(900, ge=300)
    max_age_s: int = Field(1800, ge=300)


class AristonConfig(Model):
    username: str = ''
    poll_interval_s: int = Field(120, ge=60)
    max_age_s: int = Field(600, ge=60)


class SettingsDocument(Model):
    timezone: str = 'Europe/Paris'
    site_limit_w: float | None = Field(None, gt=0)
    export_margin_w: float = Field(100, ge=0)
    sample_max_age_s: int = Field(30, ge=5, le=3600)
    devices: list[DeviceConfig] = Field(default_factory=list)
    vehicles: list[VehicleConfig] = Field(default_factory=list)
    schedules: list[ChargeProgram] = Field(default_factory=list)
    off_peak: list[OffPeakWindow] = Field(default_factory=list)
    home_assistant: HomeAssistantConfig = Field(default_factory=HomeAssistantConfig)
    peugeot: PeugeotConfig = Field(default_factory=PeugeotConfig)
    ariston: AristonConfig = Field(default_factory=AristonConfig)

    @field_validator('timezone')
    @classmethod
    def timezone_exists(cls, value):
        try: ZoneInfo(value)
        except (KeyError,ValueError): raise ValueError('Fuseau horaire inconnu') from None
        return value

    @model_validator(mode='after')
    def references(self):
        for values in (self.devices, self.vehicles, self.schedules):
            if len({item.id for item in values}) != len(values):
                raise ValueError('Identifiers must be unique')
        vehicle_ids = {v.id for v in self.vehicles}
        if any(p.vehicle_id not in vehicle_ids for p in self.schedules):
            raise ValueError('A program must reference a registered vehicle')
        if any(d.vehicle_id and d.vehicle_id not in vehicle_ids for d in self.devices):
            raise ValueError('Unknown associated vehicle')
        connectors=[(d.charge_point_id,d.connector_id) for d in self.devices if d.kind=='charger' and d.charge_point_id]
        if len(set(connectors))!=len(connectors): raise ValueError('Connecteur OCPP déjà associé')
        meters=[v for v in self.home_assistant.device_power_entities.values() if v]
        if len(set(meters))!=len(meters) or self.home_assistant.grid_entity in meters:
            raise ValueError('Une mesure électrique ne peut représenter plusieurs postes')
        for i,one in enumerate(self.schedules):
            for two in self.schedules[i+1:]:
                if (one.enabled and two.enabled and one.vehicle_id==two.vehicle_id and one.deadline==two.deadline
                    and set(one.weekdays)&set(two.weekdays) and one.earliest_start!=two.earliest_start):
                    raise ValueError('Fenêtres réseau incompatibles pour une même échéance')
        return self
