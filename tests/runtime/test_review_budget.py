from datetime import timedelta
from dataclasses import replace
import pytest
from app.domain.devices import DeviceState,DeviceSpec,Reservation
from app.domain.measurements import Sample
from app.domain.site import SiteSnapshot
from app.domain.schedules import ChargeAuthorization
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock


@pytest.mark.parametrize('network',[False,True])
def test_existing_lower_priority_reservation_is_protected_before_allocation(network):
    clock=SimulatedClock();sample=lambda v:Sample(v,'W','test',clock.now(),clock.now())
    snapshot=SiteSnapshot(clock.now(),sample(6000 if network else -3000),
        device_states={k:DeviceState(k,sample(0),connected=True) for k in ('a','b')},
        reservations=(Reservation('b',3000,'pending',clock.now()+timedelta(seconds=90)),),
        site_limit_w=9000,export_margin_w=0)
    specs=[DeviceSpec(k,'charger',min_power_w=1380,max_power_w=3000,priority=i) for i,k in enumerate(('a','b'),1)]
    policies={k:DevicePolicy(k,mode='planned' if network else 'solar',armed=True,start_delay_s=0) for k in ('a','b')}
    auth={k:ChargeAuthorization(k,True,True,80) for k in ('a','b')} if network else {}
    batch=EnergyEngine(clock).evaluate(snapshot,specs,policies,auth)
    assert not any(c.device_id=='a' and c.limit_w for c in batch.commands)


def test_incoherent_samples_cannot_invent_more_solar_after_start():
    clock=SimulatedClock();now=clock.now()
    sample=lambda v,t:Sample(v,'W','test',t,now)
    snapshot=SiteSnapshot(now, sample(-2000,now-timedelta(seconds=10)),
        device_states={'ev':DeviceState('ev',sample(2000,now),connected=True)},site_limit_w=9000,export_margin_w=0)
    batch=EnergyEngine(clock).evaluate(snapshot,[DeviceSpec('ev','charger',min_power_w=1380,max_power_w=5000)],
        {'ev':DevicePolicy('ev',armed=True,start_delay_s=0)}, {})
    assert not any(c.limit_w and c.limit_w>2000 for c in batch.commands)
