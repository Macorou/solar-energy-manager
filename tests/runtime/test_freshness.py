from dataclasses import replace
from datetime import timedelta
from app.domain.devices import DeviceSpec
from app.domain.vehicles import VehicleTelemetry
from app.domain.measurements import Quality
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock
from app.domain.devices import DeviceState
from app.domain.site import SiteSnapshot
from app.domain.measurements import Sample


def test_old_retrieved_battery_allows_automatic_charge_and_manual_is_time_limited():
    clock=SimulatedClock()
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700)
    policy=DevicePolicy('ev',armed=True,vehicle_id='car',start_delay_s=0)
    stale=VehicleTelemetry(40,200,'charging',clock.now()-timedelta(hours=2),clock.now(),Quality.FRESH)
    sample=lambda value:Sample(value,'W','test',clock.now(),clock.now())
    snapshot=SiteSnapshot(clock.now(),sample(-2000),device_states={'ev':DeviceState('ev',sample(2000),connected=True)},
        vehicle_telemetry={'car':stale},site_limit_w=9000,export_margin_w=0)
    batch=EnergyEngine(clock).evaluate(snapshot,[spec],{'ev':policy},{})
    assert batch.commands[0].limit_w>0
    manual=replace(policy,mode='manual',manual_until=clock.now()+timedelta(minutes=30))
    assert EnergyEngine(clock).evaluate(snapshot,[spec],{'ev':manual},{}).commands[0].limit_w>0
    assert EnergyEngine(clock).evaluate(snapshot,[spec],{'ev':replace(manual,manual_until=clock.now())},{}).commands[0].action=='suspend'
