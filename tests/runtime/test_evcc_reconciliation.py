import asyncio
from dataclasses import replace
from datetime import timedelta
import pytest

from app.domain.devices import DeviceState
from app.domain.measurements import Sample,utcnow
from app.domain.site import SiteSnapshot
from app.runtime.dispatcher import Dispatcher
from app.settings import DeviceConfig
from app.storage.database import SQLiteStore


def test_charger_confirmation_accepts_grid_read_eleven_microseconds_before_power(tmp_path):
    now=utcnow();sent=now-timedelta(seconds=10)
    dispatcher=Dispatcher(SQLiteStore(tmp_path/'db'))
    dispatcher.records['ev']={'id':'limit','action':'set_power','power_w':3680,'status':'accepted',
        'sent_at':sent.isoformat()}
    grid=Sample(4000,'W','HA',now,now,checked_at=now)
    power=Sample(3600,'W','OCPP',now,now,checked_at=now+timedelta(microseconds=11))
    snapshot=SiteSnapshot(now+timedelta(seconds=1),grid=grid,
        device_states={'ev':DeviceState('ev',power,'Charging',True)})
    assert dispatcher.reconcile(snapshot,{'ev':DeviceConfig(id='ev',name='EV',kind='charger')})==['ev']


def test_zero_current_suspension_can_be_observed_with_transaction_still_active(tmp_path):
    now=utcnow();dispatcher=Dispatcher(SQLiteStore(tmp_path/'db'))
    dispatcher.records['ev']={'id':'pause','action':'suspend','power_w':0,'status':'accepted',
        'sent_at':(now-timedelta(seconds=10)).isoformat()}
    power=Sample(0,'W','OCPP',now,now,checked_at=now)
    state=DeviceState('ev',power,'SuspendedEVSE',True,status_measured_at=now,
        transaction_active=True,start_pending=False)
    snapshot=SiteSnapshot(now,grid=Sample(500,'W','HA',now,now,checked_at=now),device_states={'ev':state})
    assert dispatcher.reconcile(snapshot,{'ev':DeviceConfig(id='ev',name='EV',kind='charger')})==['ev']


def test_charger_power_prefers_native_measurement_and_can_derive_it_from_current():
    from app.runtime.charger_measurements import select_power
    now=utcnow();native=Sample(3680,'W','OCPP',now,now,checked_at=now)
    ha=Sample(0,'W','HA',now-timedelta(days=1),now,checked_at=now)
    state=DeviceState('ev',native,'Charging',True)
    config=DeviceConfig(id='ev',name='EV',kind='charger')
    assert select_power(state,ha,config,now,30)==native
    state=replace(state,observed_power=None,currents={'L1':Sample(16,'A','OCPP',now,now,checked_at=now)})
    assert select_power(state,ha,config,now,30).value==3680


def test_fresh_offered_limit_confirms_cap_while_vehicle_is_waiting(tmp_path):
    now=utcnow();dispatcher=Dispatcher(SQLiteStore(tmp_path/'db'))
    dispatcher.records['ev']={'id':'limit','action':'set_power','power_w':3680,'status':'accepted',
        'sent_at':(now-timedelta(seconds=10)).isoformat()}
    power=Sample(0,'W','OCPP',now,now,checked_at=now)
    state=DeviceState('ev',power,'SuspendedEV',True,status_measured_at=now,
        offered_current=Sample(16,'A','OCPP Current.Offered',now,now,checked_at=now))
    snapshot=SiteSnapshot(now,grid=Sample(500,'W','HA',now,now,checked_at=now),device_states={'ev':state})
    assert dispatcher.reconcile(snapshot,{'ev':DeviceConfig(id='ev',name='EV',kind='charger')})==['ev']


def test_restart_retains_accepted_charger_cap_for_fresh_state_reconciliation(tmp_path):
    from app.settings import SettingsDocument
    store=SQLiteStore(tmp_path/'db')
    store.save_settings(SettingsDocument(devices=[DeviceConfig(id='ev',name='EV',kind='charger')]).model_dump(mode='json'))
    store.set('runtime_commands',{'ev':{'id':'cap','action':'set_power','status':'accepted','power_w':3680}})
    assert Dispatcher(store).records['ev']['status']=='accepted'


def test_fresh_native_suspended_state_confirms_zero_without_waiting_for_ha_power(tmp_path):
    from app.domain.measurements import Quality
    now=utcnow();dispatcher=Dispatcher(SQLiteStore(tmp_path/'db'))
    dispatcher.records['ev']={'id':'pause','action':'suspend','power_w':0,'status':'accepted',
        'sent_at':(now-timedelta(seconds=10)).isoformat()}
    power=Sample(0,'W','OCPP état SuspendedEVSE',now,now,Quality.ESTIMATED,checked_at=now)
    state=DeviceState('ev',power,'SuspendedEVSE',True,status_measured_at=now,transaction_active=True,start_pending=False)
    assert dispatcher.reconcile(SiteSnapshot(now,grid=Sample(500,'W','HA',now,now,checked_at=now),
        device_states={'ev':state}),{'ev':DeviceConfig(id='ev',name='EV',kind='charger')})==['ev']


@pytest.mark.parametrize('applied',[False,True])
async def test_observed_authorization_does_not_hide_unapplied_physical_limit(tmp_path,monkeypatch,applied):
    from types import SimpleNamespace
    from app.runtime.coordinator import Coordinator
    from app.settings import SettingsDocument
    from app.simulation.clock import SimulatedClock
    from app.domain.commands import CommandResult
    from app.api.devices import disarm
    clock=SimulatedClock(utcnow());now=clock.now();cap=16.9*230;calls=[]
    class Adapter:
        async def execute(self,intent):calls.append(intent);return CommandResult(intent.id,True)
    store=SQLiteStore(tmp_path/'db');adapter=Adapter()
    cfg=SettingsDocument(site_limit_w=11000,phase_control_enabled=True,phase_margin_a=1,
        devices=[DeviceConfig(id='ev',name='Wallbox',kind='charger',armed=True,mode='manual',
            min_power_w=1380,max_power_w=6000,grid_phases=['L1'],max_current_a=20)])
    store.save_settings(cfg.model_dump(mode='json'))
    store.set('manual_controls',{'ev':{'until':(now+timedelta(hours=1)).isoformat(),'previous_mode':'solar'}})
    store.set('runtime_commands',{'ev':{'id':'cap','device_id':'ev','action':'set_power','status':'accepted',
        'power_w':cap,'sent_at':(now-timedelta(seconds=10)).isoformat(),
        'expires_at':(now+timedelta(seconds=90)).isoformat(),
        'confirm_by':(now+timedelta(seconds=300)).isoformat(),'profile_persistent':True}})
    runtime=Coordinator(store,adapters={'ev':adapter});runtime.engine.clock=clock
    def frame(actual=20.3,grid=22.376,status='Charging'):
        stamp=clock.now();sample=lambda v,u='W':Sample(v,u,'OCPP',stamp,stamp,checked_at=stamp)
        return SiteSnapshot(stamp,grid=sample(5130.961),site_limit_w=11000,phase_control_enabled=True,
            phase_margin_a=1,phase_currents={'L1':sample(grid,'A')},phase_limits_a={'L1':20},
            device_states={'ev':DeviceState('ev',sample(actual*230),status,True,
                vehicle_connected=True,currents={'L1':sample(actual,'A')},
                offered_current=sample(16.9,'A'),status_measured_at=stamp,
                transaction_active=True,start_pending=False)})
    await runtime.tick(frame())
    assert runtime.dispatcher.records['ev']['status']=='observed'
    clock.advance(30);await runtime.tick(frame(16.9,18.976) if applied else frame())
    clock.advance(31);await runtime.tick(frame(16.9,18.976) if applied else frame())
    await asyncio.gather(*runtime.command_tasks.values())
    if applied:
        assert not calls
        assert not runtime.engine.charger_limit_faults
        return
    assert [c.action for c in calls]==['suspend']
    assert store.get('charger_limit_faults')==['ev']
    assert store.get('charger_limit_retry')['ev']['attempt']==1
    assert 'charger_limit_fault' in [e['kind'] for e in store.events()]
    # A restart keeps the pause: no new start before the automatic retry time.
    restarted=Coordinator(store,adapters={'ev':adapter});restarted.engine.clock=clock
    clock.advance(2);await restarted.tick(frame(0,2,'SuspendedEVSE'))
    await asyncio.gather(*restarted.command_tasks.values())
    assert not any(c.action=='set_power' for c in calls)
    # The explicit disarm workflow, after a fresh observed stop, still clears it at once.
    cfg.devices[0].mode='off';store.save_settings(cfg.model_dump(mode='json'))
    monkeypatch.setattr('app.api.devices.utcnow',clock.now)
    request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store,coordinator=restarted)))
    assert disarm('ev',request)['ok']
    assert store.get('charger_limit_faults')==[]
    assert not restarted.engine.charger_limit_faults
