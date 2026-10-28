import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest

from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Sample, utcnow
from app.domain.schedules import ChargeAuthorization, ChargeOccurrence
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.runtime.coordinator import Coordinator
from app.scheduling.authorization import select_authorization
from app.settings import DeviceConfig, SettingsDocument
from app.simulation.clock import SimulatedClock
from app.storage.database import SQLiteStore
from test_coordination import Adapter


def setup_engine(kind):
    clock=SimulatedClock(utcnow()); engine=EnergyEngine(clock)
    spec=DeviceSpec('device',kind,min_power_w=600,max_power_w=600)
    policy=DevicePolicy('device',mode='off_peak_solar' if kind=='water_heater' else 'planned',
                        off_peak=True,armed=True,start_delay_s=20,stop_delay_s=300,min_run_s=600)
    return clock,engine,spec,policy


def snapshot(clock, power=600, grid=1000):
    at=clock.now(); sample=lambda v:Sample(v,'W','HA',at,at,checked_at=at)
    return SiteSnapshot(at,sample(grid),device_states={'device':DeviceState('device',sample(power),
        connected=True,observed_state='on' if power else 'off',measured_at=at)},site_limit_w=11000)


@pytest.mark.parametrize('kind',['water_heater','charger'])
@pytest.mark.parametrize('grid',[1000,-1000])
def test_network_close_sends_explicit_stop_without_cloud_or_min_run_delay(kind,grid):
    clock,engine,spec,policy=setup_engine(kind)
    auth={'device':ChargeAuthorization('car',True,True)}
    engine.evaluate(snapshot(clock),[spec],{'device':policy},auth)
    clock.advance(1)
    result=engine.evaluate(snapshot(clock,grid=grid),[spec],{'device':replace(policy,off_peak=False)},
                           {'device':ChargeAuthorization('car',False,True)})
    assert [(c.action,c.limit_w) for c in result.commands] == [('suspend',0)]
    assert result.reasons['device'] == ('Fin des heures creuses' if kind=='water_heater' else 'Fin du créneau réseau')


def test_manual_authorization_is_independent_of_tariff_close():
    clock,engine,spec,policy=setup_engine('water_heater')
    engine.evaluate(snapshot(clock),[spec],{'device':policy},{})
    manual=replace(policy,mode='manual',off_peak=False,manual_until=clock.now()+timedelta(minutes=30))
    result=engine.evaluate(snapshot(clock),[spec],{'device':manual},{})
    assert not any(c.action=='suspend' for c in result.commands)
    assert result.reasons['device']=='Commande manuelle'


def test_unarmed_device_is_not_commanded_at_network_close():
    clock,engine,spec,policy=setup_engine('water_heater')
    engine.evaluate(snapshot(clock),[spec],{'device':policy},{})
    result=engine.evaluate(snapshot(clock),[spec],{'device':replace(policy,off_peak=False,armed=False)},{})
    assert not result.commands


def test_earlier_deadline_does_not_hide_another_open_network_window():
    at=utcnow()
    earlier=ChargeOccurrence('a','a','car',at+timedelta(minutes=10),at-timedelta(hours=1),at+timedelta(hours=1),80)
    open_later=replace(earlier,id='b',program_id='b',network_start_at=at-timedelta(minutes=10),
                       deadline_at=at+timedelta(hours=2))
    assert select_authorization('car',at,[earlier,open_later],80).allow_grid
    assert select_authorization('car',earlier.deadline_at,[earlier,open_later],80).allow_grid


def runtime_setup(tmp_path):
    at=utcnow(); clock=SimulatedClock(at)
    end=(at+timedelta(minutes=2)).replace(second=0,microsecond=0)
    device=DeviceConfig(id='device',name='Tank',kind='water_heater',mode='off_peak_solar',armed=True,
        min_power_w=600,max_power_w=600,cloud={'start_delay_s':0,'stop_delay_s':300,'min_run_s':600,'restart_delay_s':60})
    store=SQLiteStore(tmp_path/'test.db')
    store.save_settings(SettingsDocument(timezone='UTC',site_limit_w=11000,devices=[device],
        off_peak=[{'start':(at-timedelta(hours=1)).strftime('%H:%M'),'end':end.strftime('%H:%M')}]).model_dump(mode='json'))
    adapter=Adapter(); runtime=Coordinator(store,adapters={'device':adapter}); runtime.engine.clock=clock
    return clock,end,store,adapter,runtime


@pytest.mark.asyncio
async def test_network_permission_survives_restart_and_stops_on_first_hp_tick(tmp_path):
    clock,end,store,adapter,runtime=runtime_setup(tmp_path)
    await runtime.tick(snapshot(clock)); await asyncio.gather(*runtime.command_tasks.values())
    assert store.get('runtime_network_authorizations',{}).get('device') is True
    # An observed heat may continue across a process restart, but the old HC authorization cannot.
    record=runtime.dispatcher.records['device']; record['status']='observed'; runtime.dispatcher.save()
    clock.advance((end-clock.now()).total_seconds())
    resumed=Coordinator(store,adapters={'device':adapter}); resumed.engine.clock=clock
    batch=await resumed.tick(snapshot(clock))
    await asyncio.gather(*resumed.command_tasks.values())
    assert [c.action for c in batch.commands] == ['suspend']
    assert [c.action for c in adapter.calls] == ['set_power','suspend']


@pytest.mark.asyncio
async def test_solar_cannot_restart_while_boundary_stop_is_unconfirmed(tmp_path):
    clock,end,store,adapter,runtime=runtime_setup(tmp_path)
    await runtime.tick(snapshot(clock)); await asyncio.gather(*runtime.command_tasks.values())
    clock.advance((end-clock.now()).total_seconds())
    await runtime.tick(snapshot(clock)); await asyncio.gather(*runtime.command_tasks.values())
    assert [c.action for c in adapter.calls] == ['set_power','suspend']
    clock.advance(70)
    await runtime.tick(snapshot(clock,grid=-1000)); await asyncio.gather(*runtime.command_tasks.values())
    assert [c.action for c in adapter.calls] == ['set_power','suspend']
    assert runtime.dispatcher.records['device']['status']=='accepted'
    clock.advance(1)
    await runtime.tick(snapshot(clock,power=0,grid=-1000))
    await asyncio.gather(*runtime.command_tasks.values())
    assert [c.action for c in adapter.calls] == ['set_power','suspend','set_power']


@pytest.mark.asyncio
async def test_boundary_stop_queues_behind_in_flight_start(tmp_path):
    clock,end,store,adapter,runtime=runtime_setup(tmp_path)
    entered,release=asyncio.Event(),asyncio.Event()
    original=adapter.execute
    async def delayed(intent):
        if intent.action=='set_power': entered.set(); await release.wait()
        return await original(intent)
    adapter.execute=delayed
    await runtime.tick(snapshot(clock))
    try:
        await asyncio.wait_for(entered.wait(),2)
        clock.advance((end-clock.now()).total_seconds())
        await runtime.tick(snapshot(clock))
    finally:
        release.set(); await asyncio.gather(*runtime.command_tasks.values())
    assert [c.action for c in adapter.calls] == ['set_power','suspend']
