from typing import Literal
from pydantic import BaseModel, Field


class SessionQuery(BaseModel):
    period: Literal['month', 'year', 'total'] = 'month'
    year: int | None = Field(None, ge=1970, le=9998)
    month: int | None = Field(None, ge=1, le=12)
    vehicle_id: str | None = Field(None, max_length=64)
    device_id: str | None = Field(None, max_length=64)
    group: Literal['solar', 'charger', 'vehicle'] = 'solar'
    sort: Literal['date', 'charger', 'vehicle', 'energy', 'duration', 'solar', 'cost'] = 'date'
    direction: Literal['asc', 'desc'] = 'desc'
    page: int = Field(1, ge=1, le=1000000)
    page_size: int = Field(25, ge=1, le=100)
    include_empty: bool = False


class ChargingSession(BaseModel):
    id: str
    source: str
    device_id: str
    device_name: str
    vehicle_id: str
    vehicle_name: str
    started_at: str
    ended_at: str | None
    active: bool
    energy_kwh: float | None
    energy_partial: bool
    solar_kwh: float | None
    grid_kwh: float | None
    unknown_kwh: float | None
    solar_percent: float | None
    cost_eur: float | None
    cost_partial: bool
    average_price_per_kwh: float | None
    charge_duration_s: float | None
    duration_partial: bool
    soc_start: float | None = None
    soc_end: float | None = None
    soc_end_estimated: bool = False
    updated_at: str
    editable: bool


class Totals(BaseModel):
    count: int = 0
    energy_kwh: float = 0
    energy_partial: bool = False
    missing_energy_count: int = 0
    solar_kwh: float = 0
    grid_kwh: float = 0
    unknown_kwh: float = 0
    solar_percent: float | None = None
    cost_eur: float | None = None
    partial_cost_eur: float | None = None
    priced_energy_kwh: float = 0
    priced_count: int = 0
    cost_missing_count: int = 0
    average_price_per_kwh: float | None = None
    charge_duration_s: float | None = None
    duration_partial: bool = False


class Breakdown(BaseModel):
    id: str
    name: str
    totals: Totals


class Bucket(BaseModel):
    key: str
    energy: dict[str, float]
    cost: dict[str, float | None]
    totals: Totals


class Option(BaseModel):
    id: str
    name: str


class SolarYear(BaseModel):
    year: int
    months: list[Totals]
    totals: Totals


class SessionPage(BaseModel):
    items: list[ChargingSession]
    total: int
    page: int
    page_size: int
    totals: Totals
    buckets: list[Bucket]
    groups: list[Breakdown]
    by_vehicle: list[Breakdown]
    by_charger: list[Breakdown]
    solar_years: list[SolarYear]
    vehicles: list[Option]
    chargers: list[Option]
    available: dict[str, bool]
    timezone: str


class SessionEdit(BaseModel):
    vehicle_id: str = Field(max_length=64)
    confirm: Literal[True]


class SessionDelete(BaseModel):
    confirm: Literal[True]
