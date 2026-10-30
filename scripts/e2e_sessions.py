"""Deterministic history for the disposable browser fixture only; never imported by app."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.storage.charging_sessions import SessionHistory


def seed_sessions(store):
    now=datetime.now(ZoneInfo('Europe/Paris'))
    month=now.replace(day=1,hour=10,minute=0,second=0,microsecond=0)
    with store.connection() as db:
        for index in range(56):
            start=month+timedelta(days=index%27,hours=index%8)
            if index==54:start=month-timedelta(days=20)
            if index==55:start=month.replace(year=month.year-1)
            energy=5+index/2
            solar=energy*(index%5)/4
            cost=(energy-solar)*.1654
            row=dict(id=f'e2e-session-{index}',source='local',
                device_id='session-wallbox' if index%3 else 'session-garage',
                device_name='Wallbox Pulsar Plus' if index%3 else 'Garage',
                vehicle_id='session-peugeot' if index%2 else 'session-other',
                vehicle_name='Peugeot e-208' if index%2 else 'Autre véhicule',
                started_at=start.isoformat(),ended_at=(start+timedelta(hours=3)).isoformat(),active=False,
                energy_kwh=energy,energy_partial=False,solar_kwh=solar,grid_kwh=energy-solar,unknown_kwh=0,
                solar_percent=100*solar/energy,cost_eur=cost,cost_partial=False,
                average_price_per_kwh=cost/energy,charge_duration_s=7200+index*20,duration_partial=False,
                soc_start=40,soc_start_source='captured',soc_end=60,soc_end_estimated=True,updated_at=start.isoformat())
            if index==53:row.update(solar_kwh=None,grid_kwh=None,unknown_kwh=energy,solar_percent=None,cost_eur=None,cost_partial=True)
            SessionHistory._write(db,row)
        # Regression fixture matching an upgraded, partially metered recharge.
        row.update(id='e2e-partial-history',vehicle_id='session-migrated',vehicle_name='Peugeot (session migrée)',
            device_id='session-wallbox',device_name='Wallbox Pulsar Plus',started_at=month.isoformat(),
            ended_at=(month+timedelta(hours=3)).isoformat(),energy_kwh=13.76,energy_partial=True,
            solar_kwh=0,grid_kwh=13.76,unknown_kwh=0,solar_percent=None,cost_eur=1.9,cost_partial=True,
            average_price_per_kwh=None,soc_start=None,soc_start_source='unavailable',soc_end=64)
        SessionHistory._write(db,row)
