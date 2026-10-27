import asyncio
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.api.devices import ManualRequest, manual, pause
from app.domain.commands import CommandResult
from app.domain.devices import DeviceState
from app.domain.measurements import Quality, Sample, utcnow
from app.domain.site import SiteSnapshot
from app.runtime.coordinator import Coordinator
from app.runtime.dispatcher import Dispatcher
from app.settings import DeviceConfig, SettingsDocument
from app.simulation.clock import SimulatedClock
from app.storage.database import SQLiteStore


def confirmation_frame(now):
    sent = now-timedelta(seconds=2)
    power = Sample(0,'W','HA',now-timedelta(days=1),now,checked_at=now)
    grid = Sample(700,'W','HA-grid',now-timedelta(days=1),now,checked_at=now)
    state = DeviceState('tank',power,connected=True,observed_state='off',
                        measured_at=now,temperature=28,target_temperature=55)
    return sent, SiteSnapshot(now,grid,device_states={'tank':state},site_limit_w=11000)


def pending_stop(tmp_path, sent):
    dispatcher=Dispatcher(SQLiteStore(tmp_path/'test.db'))
    dispatcher.records['tank']={'status':'accepted','sent_at':sent.isoformat(),
                               'power_w':0,'action':'suspend'}
    return dispatcher


def heater_config(kind='water_heater'):
    return DeviceConfig(id='tank',name='Test',kind=kind,target=55,
                        min_power_w=700,max_power_w=2570,armed=True,mode='manual')


def test_stop_accepts_fresh_native_off_and_currently_checked_unchanged_zero(tmp_path):
    now=utcnow(); sent, snapshot=confirmation_frame(now)
    dispatcher=pending_stop(tmp_path,sent)
    assert dispatcher.reconcile(snapshot,{'tank':heater_config()}) == ['tank']
    assert dispatcher.records['tank']['status'] == 'observed'
    assert snapshot.device_states['tank'].observed_power.measured_at == now-timedelta(days=1)


@pytest.mark.parametrize('invalid', ['native_on','native_offline','native_fault',
    'native_before_order','native_old','native_future','missing_native_date',
    'power_not_checked','power_checked_before_order','power_unavailable','power_nonzero',
    'grid_unavailable','grid_checked_before_power','grid_incoherent','charger'])
def test_old_zero_cannot_release_reservation_without_all_stop_evidence(tmp_path,invalid):
    now=utcnow(); sent,snapshot=confirmation_frame(now)
    state=snapshot.device_states['tank']; power=state.observed_power; grid=snapshot.grid
    if invalid=='native_on': state=replace(state,observed_state='on')
    elif invalid=='native_offline': state=replace(state,connected=False)
    elif invalid=='native_fault': state=replace(state,fault='provider_unavailable')
    elif invalid=='native_before_order': state=replace(state,measured_at=sent)
    elif invalid=='native_old':
        sent=now-timedelta(seconds=60); state=replace(state,measured_at=now-timedelta(seconds=40))
    elif invalid=='native_future': state=replace(state,measured_at=now+timedelta(seconds=1))
    elif invalid=='missing_native_date': state=replace(state,measured_at=None)
    elif invalid=='power_not_checked': power=replace(power,checked_at=None)
    elif invalid=='power_checked_before_order': power=replace(power,checked_at=sent)
    elif invalid=='power_unavailable': power=replace(power,quality=Quality.UNAVAILABLE)
    elif invalid=='power_nonzero': power=replace(power,value=650)
    elif invalid=='grid_unavailable': grid=replace(grid,quality=Quality.UNAVAILABLE)
    elif invalid=='grid_checked_before_power': grid=replace(grid,checked_at=now-timedelta(seconds=1))
    elif invalid=='grid_incoherent':
        sent=now-timedelta(seconds=10)
        grid=replace(grid,checked_at=now-timedelta(seconds=3))
        power=replace(power,checked_at=now-timedelta(seconds=6))
    state=replace(state,observed_power=power)
    snapshot=replace(snapshot,grid=grid,device_states={'tank':state})
    dispatcher=pending_stop(tmp_path,sent)
    config=heater_config('charger' if invalid=='charger' else 'water_heater')
    assert dispatcher.reconcile(snapshot,{'tank':config}) == []
    assert dispatcher.records['tank']['status'] == 'accepted'


def test_start_still_requires_new_electrical_effect_even_with_native_on(tmp_path):
    now=utcnow(); sent,snapshot=confirmation_frame(now)
    state=replace(snapshot.device_states['tank'],observed_state='on')
    dispatcher=pending_stop(tmp_path,sent)
    dispatcher.records['tank'].update(action='set_power',power_w=2570)
    assert dispatcher.reconcile(replace(snapshot,device_states={'tank':state}),{'tank':heater_config()}) == []


class NativeAdapter:
    def __init__(self, clock): self.calls=[]; self.last_command=None; self.clock=clock

    async def execute(self,intent):
        self.calls.append(intent.action)
        now=self.clock.now()
        if intent.action!='suspend' and self.last_command and (now-self.last_command).total_seconds()<60:
            return CommandResult(intent.id,False,error='native_cooldown')
        self.last_command=now
        return CommandResult(intent.id,True)


@pytest.mark.asyncio
async def test_manual_heat_after_restart_stop_reaches_one_start_and_measured_effect(tmp_path):
    store=SQLiteStore(tmp_path/'test.db'); clock=SimulatedClock(utcnow())
    device=heater_config().model_copy(update={'mode':'off_peak_solar'})
    store.save_settings(SettingsDocument(site_limit_w=11000,devices=[device]).model_dump(mode='json'))
    old=clock.now()-timedelta(minutes=10)
    store.set('runtime_commands',{'tank':{'id':'old','status':'unknown','action':'set_power',
        'power_w':2570,'sent_at':old.isoformat(),'expires_at':old.isoformat(),'confirm_by':old.isoformat()}})
    native=NativeAdapter(clock); runtime=Coordinator(store,adapters={'tank':native})
    runtime.engine.clock=clock
    request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store,coordinator=runtime)))

    def frame(connected=True, heating=False):
        now=clock.now(); _, snapshot=confirmation_frame(now)
        state=replace(snapshot.device_states['tank'],connected=connected,
                      observed_state='on' if heating else 'off')
        if heating:
            state=replace(state,observed_power=replace(state.observed_power,value=650,measured_at=now))
            snapshot=replace(snapshot,grid=replace(snapshot.grid,measured_at=now,value=1350))
        return replace(snapshot,device_states={'tank':state})

    await runtime.tick(frame(connected=False))
    await asyncio.gather(*runtime.command_tasks.values())
    assert native.calls == ['suspend']
    clock.advance(2)
    assert manual('tank',ManualRequest(),request)['ok']
    await runtime.tick(frame())
    await asyncio.gather(*runtime.command_tasks.values())
    assert runtime.dispatcher.records['tank']['status'] == 'observed'
    assert 'tank' not in runtime.reservations


    assert native.calls == ['suspend']
    assert 'Temporisation' in runtime.reasons['tank']
    assert store.load_settings()['devices'][0]['mode'] == 'manual'

    clock.advance(60)
    await runtime.tick(frame())
    await asyncio.gather(*runtime.command_tasks.values())
    assert native.calls == ['suspend','set_power']
    assert runtime.dispatcher.records['tank']['status'] == 'accepted'
    assert runtime.reservations['tank'].power_w == 2570

    # A second click extends the request without cancelling an unobserved start.
    manual('tank',ManualRequest(),request)
    await runtime.tick(frame())
    await asyncio.gather(*runtime.command_tasks.values())
    assert native.calls == ['suspend','set_power']
    clock.advance(2)
    await runtime.tick(frame(heating=True))
    assert runtime.dispatcher.records['tank']['status'] == 'observed'
    assert 'tank' not in runtime.reservations


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', ['pause', 'expired'])
async def test_pause_or_expired_manual_request_does_not_start_after_native_delay(tmp_path,cancel):
    store=SQLiteStore(tmp_path/'test.db'); clock=SimulatedClock(utcnow())
    device=heater_config().model_copy(update={'mode':'off'})
    store.save_settings(SettingsDocument(site_limit_w=11000,devices=[device]).model_dump(mode='json'))
    native=NativeAdapter(clock); native.last_command=clock.now()
    runtime=Coordinator(store,adapters={'tank':native}); runtime.engine.clock=clock
    request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store,coordinator=runtime)))
    manual('tank',ManualRequest(duration_minutes=1),request)
    await runtime.tick(confirmation_frame(clock.now())[1])
    assert not native.calls
    if cancel=='pause': pause('tank',request)
    clock.advance(62)
    await runtime.tick(confirmation_frame(clock.now())[1])
    await asyncio.gather(*runtime.command_tasks.values())
    assert not native.calls


@pytest.mark.parametrize('invalid', ['on','offline','fault','before_order','old','future','missing_date'])
def test_fresh_electrical_zero_cannot_bypass_invalid_native_stop_evidence(tmp_path,invalid):
    now=utcnow(); _,snapshot=confirmation_frame(now); sent=now-timedelta(seconds=60)
    state=snapshot.device_states['tank']
    state=replace(state,observed_power=replace(state.observed_power,measured_at=now))
    if invalid=='on': state=replace(state,observed_state='on')
    elif invalid=='offline': state=replace(state,connected=False)
    elif invalid=='fault': state=replace(state,fault='provider_unavailable')
    elif invalid=='before_order': state=replace(state,measured_at=sent)
    elif invalid=='old': state=replace(state,measured_at=now-timedelta(seconds=40))
    elif invalid=='future': state=replace(state,measured_at=now+timedelta(seconds=1))
    elif invalid=='missing_date': state=replace(state,measured_at=None)
    snapshot=replace(snapshot,grid=replace(snapshot.grid,measured_at=now),device_states={'tank':state})
    dispatcher=pending_stop(tmp_path,sent)
    assert dispatcher.reconcile(snapshot,{'tank':heater_config()}) == []
    assert dispatcher.records['tank']['status'] == 'accepted'


@pytest.mark.asyncio
async def test_in_flight_stop_keeps_reservation_and_cannot_queue_an_early_start(tmp_path):
    store=SQLiteStore(tmp_path/'test.db'); clock=SimulatedClock(utcnow())
    device=heater_config().model_copy(update={'mode':'off_peak_solar'})
    store.save_settings(SettingsDocument(site_limit_w=11000,devices=[device]).model_dump(mode='json'))
    old=clock.now()-timedelta(minutes=10)
    store.set('runtime_commands',{'tank':{'id':'old','status':'unknown','action':'set_power',
        'power_w':2570,'sent_at':old.isoformat(),'expires_at':old.isoformat(),'confirm_by':old.isoformat()}})
    entered,release=asyncio.Event(),asyncio.Event()

    class DelayedStop(NativeAdapter):
        async def execute(self,intent):
            if intent.action=='suspend': entered.set(); await release.wait()
            return await super().execute(intent)

    native=DelayedStop(clock); runtime=Coordinator(store,adapters={'tank':native})
    runtime.engine.clock=clock
    request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store,coordinator=runtime)))
    frame=confirmation_frame(clock.now())[1]
    disconnected=replace(frame,device_states={'tank':replace(frame.device_states['tank'],connected=False)})
    await runtime.tick(disconnected)
    try:
        await asyncio.wait_for(entered.wait(),2)
        clock.advance(2)
        manual('tank',ManualRequest(),request)
        batch=await runtime.tick(confirmation_frame(clock.now())[1])
        assert runtime.dispatcher.records['tank']['status'] == 'sending'
        assert runtime.reservations['tank'].power_w == 2570
        assert not any(command.action=='set_power' for command in batch.commands)
        assert 'Chauffe demandée' in runtime.reasons['tank']
    finally:
        release.set()
        await asyncio.gather(*runtime.command_tasks.values())
    clock.advance(2)
    await runtime.tick(confirmation_frame(clock.now())[1])
    assert native.calls == ['suspend']
    assert 'Temporisation' in runtime.reasons['tank']
    clock.advance(60)
    await runtime.tick(confirmation_frame(clock.now())[1])
    await asyncio.gather(*runtime.command_tasks.values())
    assert native.calls == ['suspend','set_power']
    assert runtime.dispatcher.records['tank']['status'] == 'accepted'
