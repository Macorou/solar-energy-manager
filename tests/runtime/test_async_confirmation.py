from dataclasses import replace
from datetime import timedelta

import pytest

from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Quality, Sample, utcnow
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.runtime.dispatcher import Dispatcher
from app.settings import DeviceConfig
from app.simulation.clock import SimulatedClock
from app.storage.database import SQLiteStore


def frame(tmp_path, kind='water_heater', grid_offset=-16):
    now=utcnow(); sent=now-timedelta(seconds=30)
    power=Sample(2650,'W','HA-tank',now-timedelta(seconds=5),now,checked_at=now)
    grid=Sample(3000,'W','HA-grid',now+timedelta(seconds=grid_offset),now,checked_at=now)
    state=DeviceState('device',power,observed_state='on',connected=True,
                      temperature=54,target_temperature=55,measured_at=now)
    snapshot=SiteSnapshot(now,grid,device_states={'device':state},site_limit_w=11000)
    dispatcher=Dispatcher(SQLiteStore(tmp_path/'test.db'))
    dispatcher.records['device']={'status':'accepted','sent_at':sent.isoformat(),
                                  'power_w':2570,'action':'set_power'}
    config=DeviceConfig(id='device',name='Device',kind=kind,target=55)
    return dispatcher,snapshot,config


@pytest.mark.parametrize('kind',['water_heater','charger'])
@pytest.mark.parametrize('grid_offset',[-16,-1])
def test_checked_ha_frame_confirms_effect_despite_asynchronous_provider_dates(tmp_path,kind,grid_offset):
    dispatcher,snapshot,config=frame(tmp_path,kind,grid_offset)
    assert dispatcher.reconcile(snapshot,{'device':config}) == ['device']
    assert dispatcher.records['device']['status'] == 'observed'


@pytest.mark.parametrize('invalid',['old_effect','old_checks','future_check','grid_before_check',
                                   'unavailable','raw_mixed_frame','sending'])
def test_current_check_does_not_replace_physical_start_evidence(tmp_path,invalid):
    dispatcher,snapshot,config=frame(tmp_path)
    state=snapshot.device_states['device']; power=state.observed_power; grid=snapshot.grid
    if invalid=='old_effect': power=replace(power,measured_at=snapshot.at-timedelta(minutes=2))
    elif invalid=='old_checks': power=replace(power,checked_at=snapshot.at-timedelta(minutes=2))
    elif invalid=='future_check': power=replace(power,checked_at=snapshot.at+timedelta(seconds=1))
    elif invalid=='grid_before_check': grid=replace(grid,checked_at=snapshot.at-timedelta(seconds=1))
    elif invalid=='unavailable': power=replace(power,quality=Quality.UNAVAILABLE)
    elif invalid=='raw_mixed_frame':
        power=replace(power,checked_at=None); grid=replace(grid,checked_at=None)
    elif invalid=='sending': dispatcher.records['device']['status']='sending'
    snapshot=replace(snapshot,grid=grid,device_states={'device':replace(state,observed_power=power)})
    assert dispatcher.reconcile(snapshot,{'device':config}) == []


def test_pending_confirmation_has_its_own_reason_when_electrical_checks_are_coherent(tmp_path):
    _,snapshot,_=frame(tmp_path)
    engine=EnergyEngine(SimulatedClock(snapshot.at)); engine.requested['device']=2570
    spec=DeviceSpec('device','water_heater',min_power_w=2570,max_power_w=2570)
    policy=DevicePolicy('device',mode='off_peak_solar',armed=True,off_peak=True,target=55)
    result=engine.evaluate(replace(snapshot,transition_blocked=True),[spec],{'device':policy},{})
    # A heater already running loses nothing: it keeps its own reason.
    assert result.reasons['device'] == 'Chauffe heures creuses'
    assert not result.commands
    idle=EnergyEngine(SimulatedClock(snapshot.at))
    result=idle.evaluate(replace(snapshot,transition_blocked=True),[spec],{'device':policy},{})
    assert result.reasons['device'] == 'Commande en attente de confirmation : démarrage différé'
    assert [c.action for c in result.commands] != ['set_power']
