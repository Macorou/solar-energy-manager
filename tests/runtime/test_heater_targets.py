from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.chargers import ArmRequest
from app.api.water_heaters import arm
from app.connectors.ariston.client import AristonAdapter
from app.domain.commands import CommandIntent
from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Sample, utcnow
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.runtime.coordinator import Coordinator
from app.runtime.dispatcher import Dispatcher
from app.settings import DeviceConfig, SettingsDocument, OffPeakWindow
from app.simulation.clock import SimulatedClock
from app.storage.database import SQLiteStore
from test_ariston_lifecycle import configured_app, NativeHeater
from test_coordination import Adapter


def setup(mode='off_peak_solar'):
    clock=SimulatedClock(utcnow()); engine=EnergyEngine(clock)
    spec=DeviceSpec('tank','water_heater',min_power_w=700,max_power_w=2570)
    policy=DevicePolicy('tank',mode=mode,armed=True,off_peak=True,target=55,solar_target=70,
                        start_delay_s=10,stop_delay_s=30,restart_delay_s=0)
    return clock,engine,spec,policy


def frame(clock, power=0, grid=700, temperature=28):
    at=clock.now(); sample=lambda value:Sample(value,'W','HA',at,at,checked_at=at)
    state=DeviceState('tank',sample(power),'on' if power else 'off',True,
                      temperature=temperature,target_temperature=55,measured_at=at)
    return SiteSnapshot(at,sample(grid),device_states={'tank':state},site_limit_w=11000,export_margin_w=100)


def evaluate(engine,clock,spec,policy,**kw):
    return engine.evaluate(frame(clock,**kw),[spec],{'tank':policy},{})


def test_existing_configuration_preserves_network_target_and_inherits_solar():
    config=DeviceConfig.model_validate({'id':'tank','name':'Tank','kind':'water_heater','target':55})
    assert config.target==55 and config.solar_target is None
    restored=DeviceConfig.model_validate(config.model_dump(mode='json'))
    assert restored.target==55 and restored.solar_target is None


def test_hc_and_manual_use_network_target_without_surplus():
    clock,engine,spec,policy=setup()
    hc=evaluate(engine,clock,spec,policy)
    assert hc.commands[0].target_temperature==55
    assert hc.effective_targets['tank']==55 and hc.target_sources['tank']=='grid'
    manual=replace(policy,mode='manual',manual_until=clock.now()+timedelta(minutes=30))
    clock.advance(20)
    result=evaluate(EnergyEngine(clock),clock,spec,manual,grid=-5000)
    assert result.commands[0].target_temperature==55
    assert result.target_sources['tank']=='grid'


def test_solar_can_heat_above_network_goal_and_stops_at_solar_goal():
    clock,engine,spec,policy=setup('solar')
    assert not evaluate(engine,clock,spec,policy,grid=-3000,temperature=60).commands
    clock.advance(11)
    result=evaluate(engine,clock,spec,policy,grid=-3000,temperature=60)
    assert [(c.action,c.target_temperature) for c in result.commands]==[('set_power',70)]
    assert result.effective_targets['tank']==70 and result.target_sources['tank']=='solar'
    clock.advance(1)
    stopped=evaluate(engine,clock,spec,policy,power=2650,grid=-200,temperature=70)
    assert [c.action for c in stopped.commands]==['suspend']


def boosted():
    clock,engine,spec,policy=setup()
    evaluate(engine,clock,spec,policy)
    clock.advance(61)
    evaluate(engine,clock,spec,policy,power=2650,grid=-100)
    clock.advance(11)
    result=evaluate(engine,clock,spec,policy,power=2650,grid=-100)
    return clock,engine,spec,policy,result


def test_stable_solar_during_hc_changes_only_setpoint():
    *_,result=boosted()
    assert [(c.action,c.limit_w,c.target_temperature) for c in result.commands]==[('set_temperature',2570,70)]


@pytest.mark.parametrize('temperature',[50,60])
def test_cloud_grace_preserves_solar_target_then_reverts_or_stops(temperature):
    clock,engine,spec,policy,_=boosted()
    short=evaluate(engine,clock,spec,policy,power=2650,grid=1000,temperature=temperature)
    assert not short.commands and short.effective_targets['tank']==70
    clock.advance(31)
    end=evaluate(engine,clock,spec,policy,power=2650,grid=1000,temperature=temperature)
    assert end.effective_targets['tank']==55 and end.target_sources['tank']=='grid'
    assert [(c.action,c.target_temperature) for c in end.commands]==[
        ('set_temperature',55) if temperature<55 else ('suspend',None)]


def test_setpoint_update_waits_for_native_cooldown_without_restarting_power():
    clock,engine,spec,policy=setup()
    evaluate(engine,clock,spec,policy)
    wait=replace(policy,start_not_before=clock.now()+timedelta(seconds=60))
    evaluate(engine,clock,spec,wait,power=2650,grid=-100)
    clock.advance(11)
    assert not evaluate(engine,clock,spec,wait,power=2650,grid=-100).commands
    clock.advance(50)
    result=evaluate(engine,clock,spec,wait,power=2650,grid=-100)
    assert [(c.action,c.target_temperature) for c in result.commands]==[('set_temperature',70)]


@pytest.mark.asyncio
async def test_native_uses_immutable_intent_target_and_setpoint_only_does_not_power_on():
    native=NativeHeater(); native.water_heater_maximum_temperature=75
    config=DeviceConfig(id='tank',name='Tank',kind='water_heater',target=55,solar_target=70)
    adapter=AristonAdapter(config,device=native)
    result=await adapter.execute(CommandIntent('one','tank','set_temperature',2570,target_temperature=70))
    assert result.accepted and native.calls==[('target',70)]
    assert adapter.config.target==55


@pytest.mark.asyncio
async def test_native_rejects_solar_target_outside_device_bounds_before_any_command():
    native=NativeHeater()
    config=DeviceConfig(id='tank',name='Tank',kind='water_heater',target=55,solar_target=70)
    result=await AristonAdapter(config,device=native).execute(
        CommandIntent('one','tank','set_power',2570,target_temperature=70))
    assert not result.accepted and result.error=='native_temperature_limits_required'
    assert native.calls==[]


@pytest.mark.asyncio
async def test_arm_checks_both_temperature_targets_without_sending_commands(tmp_path):
    app,device,config=configured_app(tmp_path)
    device=device.model_copy(update={'armed':False,'target':55,'solar_target':70})
    config.devices=[device]; config.home_assistant.device_power_entities={'tank':'sensor.tank'}
    app.state.store.save_settings(config.model_dump(mode='json'))
    from app.api.water_heaters import adapter as get_adapter
    source=get_adapter(SimpleNamespace(app=app),device); native=source.device=NativeHeater()
    await source.connect(); await source.probe_capabilities()
    with pytest.raises(HTTPException) as error:
        arm('tank',ArmRequest(confirm_control=True,capabilities_verified=True,offline_behavior_verified=True),SimpleNamespace(app=app))
    assert error.value.status_code==409 and 'température' in error.value.detail
    assert native.calls==[]


@pytest.mark.parametrize('invalid',[None,'wrong_target','old_native','native_off','old_check','sending'])
def test_setpoint_confirmation_uses_native_readback_without_a_new_wattage_jump(tmp_path,invalid):
    now=utcnow(); sent=now-timedelta(seconds=5)
    power=Sample(2650,'W','HA',now-timedelta(minutes=2),now,checked_at=now)
    grid=Sample(3000,'W','HA',now-timedelta(minutes=1),now,checked_at=now)
    state=DeviceState('tank',power,'on',True,temperature=54,target_temperature=70,measured_at=now)
    dispatcher=Dispatcher(SQLiteStore(tmp_path/'test.db'))
    dispatcher.records['tank']={'status':'accepted','sent_at':sent.isoformat(),'power_w':2570,
                               'action':'set_temperature','target_temperature':70}
    if invalid=='wrong_target': state=replace(state,target_temperature=55)
    elif invalid=='old_native': state=replace(state,measured_at=sent)
    elif invalid=='native_off': state=replace(state,observed_state='off')
    elif invalid=='old_check': power=replace(power,checked_at=sent)
    elif invalid=='sending': dispatcher.records['tank']['status']='sending'
    snapshot=SiteSnapshot(now,grid,device_states={'tank':replace(state,observed_power=power)})
    config=DeviceConfig(id='tank',name='Tank',kind='water_heater',target=55,solar_target=70)
    assert dispatcher.reconcile(snapshot,{'tank':config}) == ([] if invalid else ['tank'])


def test_public_state_reports_selected_target_and_source(tmp_path):
    clock,engine,spec,policy,result=boosted()
    store=SQLiteStore(tmp_path/'test.db')
    store.save_settings(SettingsDocument(devices=[DeviceConfig(id='tank',name='Tank',kind='water_heater',target=55,solar_target=70)]).model_dump(mode='json'))
    runtime=Coordinator(store); runtime.engine=engine
    runtime.effective_targets=result.effective_targets; runtime.target_sources=result.target_sources
    snapshot=frame(clock,temperature=60)
    runtime.snapshot=replace(snapshot,device_states={'tank':replace(snapshot.device_states['tank'],target_reached=True)})
    public=runtime.public_state()['devices'][0]
    assert public['effective_target']==70 and public['target_source']=='solar'
    assert public['state']['target_reached'] is False


@pytest.mark.asyncio
async def test_runtime_observes_a_solar_setpoint_change_without_a_new_power_timestamp(tmp_path):
    import asyncio
    clock=SimulatedClock(utcnow()); store=SQLiteStore(tmp_path/'test.db')
    config=DeviceConfig(id='tank',name='Tank',kind='water_heater',mode='off_peak_solar',armed=True,
        target=55,solar_target=70,min_power_w=700,max_power_w=2570,cloud={'start_delay_s':0})
    store.save_settings(SettingsDocument(site_limit_w=11000,devices=[config],
        off_peak=[{'start':'00:00','end':'00:00'}]).model_dump(mode='json'))
    native=Adapter(); runtime=Coordinator(store,adapters={'tank':native}); runtime.engine.clock=clock
    await runtime.tick(frame(clock)); await asyncio.gather(*runtime.command_tasks.values())
    clock.advance(2)
    await runtime.tick(frame(clock,power=2650,grid=3000))
    assert runtime.dispatcher.records['tank']['status']=='observed'
    clock.advance(61)
    await runtime.tick(frame(clock,power=2650,grid=-100)); await asyncio.gather(*runtime.command_tasks.values())
    assert [(c.action,c.target_temperature) for c in native.calls]==[('set_power',55),('set_temperature',70)]
    record=runtime.dispatcher.records['tank']
    later=clock.now()+timedelta(seconds=2)
    snapshot=frame(SimulatedClock(later),power=2650,grid=-100)
    state=snapshot.device_states['tank']
    # The electrical value predates the setpoint command. Current HA checks and
    # a new native target readback prove the setpoint-only operation instead.
    state=replace(state,target_temperature=70,observed_power=replace(state.observed_power,
        measured_at=utcnow()-timedelta(minutes=2)))
    await runtime.tick(replace(snapshot,device_states={'tank':state}))
    assert runtime.dispatcher.records['tank']['status']=='observed'
    assert 'tank' not in runtime.reservations
    assert runtime.public_state()['devices'][0]['effective_target']==70
    assert len(native.calls)==2


@pytest.mark.asyncio
@pytest.mark.parametrize('maximum,expected',[(65,409),(75,200)])
async def test_editing_armed_heater_validates_new_solar_target_against_native_limits(tmp_path,maximum,expected):
    from fastapi.testclient import TestClient
    from app.api.water_heaters import adapter as get_adapter
    app,device,_=configured_app(tmp_path)
    source=get_adapter(SimpleNamespace(app=app),device); native=source.device=NativeHeater()
    native.water_heater_maximum_temperature=maximum
    await source.connect()
    client=TestClient(app)
    client.post('/api/v1/setup',json={'token':(tmp_path/'bootstrap-token').read_text(),
                                     'username':'admin','password':'test-password-long-enough'})
    settings=client.get('/api/v1/settings').json()
    settings['devices'][0]['solar_target']=70
    assert client.put('/api/v1/settings',json=settings).status_code==expected
    assert native.calls==[]


def test_continuous_stable_solar_heating_keeps_solar_target_when_hc_opens():
    clock,engine,spec,policy=setup()
    hp=replace(policy,off_peak=False)
    evaluate(engine,clock,spec,hp,grid=-3000,temperature=60)
    clock.advance(11)
    evaluate(engine,clock,spec,hp,grid=-3000,temperature=60)
    clock.advance(1)
    opening=evaluate(engine,clock,spec,policy,power=2650,grid=-100,temperature=60)
    assert opening.effective_targets['tank']==70
    assert not any(c.action=='suspend' for c in opening.commands)


@pytest.mark.asyncio
async def test_fast_boundary_stop_then_hours_without_solar_cannot_boost_next_hc(tmp_path):
    import asyncio
    clock=SimulatedClock(utcnow()); store=SQLiteStore(tmp_path/'test.db')
    config=DeviceConfig(id='tank',name='Tank',kind='water_heater',mode='off_peak_solar',armed=True,
        target=55,solar_target=70,min_power_w=700,max_power_w=2570,
        cloud={'start_delay_s':0,'stop_delay_s':30,'restart_delay_s':0})
    settings=SettingsDocument(site_limit_w=11000,devices=[config],off_peak=[{'start':'00:00','end':'00:00'}])
    store.save_settings(settings.model_dump(mode='json'))
    native=Adapter(); runtime=Coordinator(store,adapters={'tank':native}); runtime.engine.clock=clock
    async def tick(power,grid,temperature,target=55):
        current=frame(clock,power=power,grid=grid,temperature=temperature)
        current=replace(current,device_states={'tank':replace(current.device_states['tank'],target_temperature=target)})
        result=await runtime.tick(current); await asyncio.gather(*runtime.command_tasks.values()); return result
    await tick(0,700,28)
    clock.advance(2); await tick(2650,3000,28)
    clock.advance(61); await tick(2650,-100,54)
    clock.advance(2); await tick(2650,-100,54,70)
    settings.off_peak=[]; store.save_settings(settings.model_dump(mode='json'))
    clock.advance(2); await tick(2650,1000,60,70)
    clock.advance(2); await tick(0,1000,60,70)  # stop observed before any forced-off evaluation
    clock.advance(7200); await tick(0,1000,60,70)
    settings.off_peak=[OffPeakWindow(start='00:00',end='00:00')]
    # Validate the Pydantic model again after the controlled fixture update.
    store.save_settings(SettingsDocument.model_validate(settings.model_dump()).model_dump(mode='json'))
    clock.advance(1); result=await tick(0,1000,60,70)
    assert result.effective_targets['tank']==55 and result.target_sources['tank']=='grid'
    assert not any(c.action=='set_power' for c in result.commands)
