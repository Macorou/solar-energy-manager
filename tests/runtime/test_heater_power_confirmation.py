"""The HA power meter confirms a heater order as soon as it shows the change.

The Ariston cloud is read every few minutes and lags behind the heater: on
2026-11-10 a stop took 5 min to be confirmed (and held the car meanwhile)
although the dedicated power meter showed 0 W after 30 s.
"""
import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest

from app.domain.devices import DeviceState
from app.domain.measurements import Sample, utcnow
from app.domain.site import SiteSnapshot
from app.runtime.coordinator import Coordinator
from app.runtime.dispatcher import Dispatcher
from app.settings import SettingsDocument
from app.simulation.clock import SimulatedClock
from app.storage.database import SQLiteStore

from tests.runtime.test_manual_heating_cycle import NativeAdapter, heater_config


def frame(now, power, native='on', native_at=None, target=55, power_at=None):
    """Grid and power read together at `now`; the native (cloud) read is older."""
    sample = Sample(power,'W','HA',power_at or now,now,checked_at=now)
    grid = Sample(700+power,'W','HA-grid',now,now,checked_at=now)
    state = DeviceState('tank',sample,connected=True,observed_state=native,
                        measured_at=native_at or now-timedelta(minutes=3),temperature=53,target_temperature=target)
    return SiteSnapshot(now,grid,device_states={'tank':state},site_limit_w=11000)


def pending(tmp_path, action, sent, before):
    dispatcher = Dispatcher(SQLiteStore(tmp_path/'test.db'))
    dispatcher.records['tank'] = {'status':'accepted','sent_at':sent.isoformat(),'action':action,
        'power_w':2570 if action=='set_power' else 0,'target_temperature':55 if action=='set_power' else None,
        'power_before_w':before}
    return dispatcher


def test_stop_of_a_heating_heater_is_confirmed_by_its_meter_before_the_cloud(tmp_path):
    now = utcnow(); dispatcher = pending(tmp_path,'suspend',now-timedelta(seconds=30),2737)
    assert dispatcher.reconcile(frame(now,0),{'tank':heater_config()}) == ['tank']
    assert dispatcher.records['tank']['status'] == 'observed'
    assert dispatcher.records['tank']['effect'] == 'power'


@pytest.mark.parametrize('before,power,power_age_s', [
    (None,0,0),   # unknown before the order: an unchanged zero proves nothing
    (0,0,0),      # already idle (thermostat): idem
    (15,0,0),
    (2737,650,0), # still drawing
    (2737,0,40),  # zero measured before the order
])
def test_stop_needs_a_drop_measured_after_the_order(tmp_path, before, power, power_age_s):
    now = utcnow(); dispatcher = pending(tmp_path,'suspend',now-timedelta(seconds=30),before)
    snapshot = frame(now,power,power_at=now-timedelta(seconds=power_age_s))
    assert dispatcher.reconcile(snapshot,{'tank':heater_config()}) == []
    assert dispatcher.records['tank']['status'] == 'accepted'


def test_start_of_an_idle_heater_is_confirmed_by_its_meter_before_the_cloud(tmp_path):
    now = utcnow(); dispatcher = pending(tmp_path,'set_power',now-timedelta(seconds=30),0)
    assert dispatcher.reconcile(frame(now,2711,native='off'),{'tank':heater_config()}) == ['tank']
    assert dispatcher.records['tank']['effect'] == 'power'


@pytest.mark.parametrize('case', ['before_unknown','already_drawing','other_target','too_much','offline','fault'])
def test_start_without_a_clear_new_draw_still_waits_for_the_cloud(tmp_path, case):
    now = utcnow()
    dispatcher = pending(tmp_path,'set_power',now-timedelta(seconds=30),
                         {'before_unknown':None,'already_drawing':650}.get(case,0))
    snapshot = frame(now,5000 if case=='too_much' else 2711,native='off',target=50 if case=='other_target' else 55)
    state = snapshot.device_states['tank']
    if case=='offline': state = replace(state,connected=False)
    if case=='fault': state = replace(state,fault='provider_unavailable')
    snapshot = replace(snapshot,device_states={'tank':state})
    assert dispatcher.reconcile(snapshot,{'tank':heater_config()}) == []


@pytest.mark.asyncio
async def test_meter_confirmed_stop_is_sent_again_if_the_heater_draws_again(tmp_path):
    store = SQLiteStore(tmp_path/'test.db'); clock = SimulatedClock(utcnow())
    device = heater_config().model_copy(update={'mode':'off'})
    store.save_settings(SettingsDocument(site_limit_w=11000,devices=[device]).model_dump(mode='json'))
    native = NativeAdapter(clock); runtime = Coordinator(store,adapters={'tank':native})
    runtime.engine.clock = clock
    await runtime.tick(frame(clock.now(),2737))
    await asyncio.gather(*runtime.command_tasks.values())
    assert native.calls == ['suspend']
    assert runtime.dispatcher.records['tank']['power_before_w'] == 2737
    clock.advance(30)
    await runtime.tick(frame(clock.now(),0))
    record = runtime.dispatcher.records['tank']
    assert record['status'] == 'observed' and record['effect'] == 'power'
    assert not runtime.snapshot.transition_blocked
    # The cloud still says on and the meter shows a new draw: the stop did not hold.
    clock.advance(60)
    await runtime.tick(frame(clock.now(),2700))
    await asyncio.gather(*runtime.command_tasks.values())
    assert native.calls == ['suspend','suspend']
