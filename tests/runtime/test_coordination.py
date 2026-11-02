import asyncio
from dataclasses import replace
from datetime import timedelta
import pytest
from app.runtime.coordinator import Coordinator
from app.runtime.dispatcher import Dispatcher
from app.domain.commands import CommandIntent,CommandResult
from app.domain.devices import DeviceState
from app.domain.measurements import Sample,utcnow
from app.domain.site import SiteSnapshot
from app.storage.database import SQLiteStore
from app.settings import SettingsDocument,DeviceConfig


class Adapter:
    def __init__(self, delay=0): self.calls=[]; self.delay=delay
    async def execute(self,intent):
        self.calls.append(intent)
        await asyncio.sleep(self.delay)
        return CommandResult(intent.id,True)


def environment(tmp_path):
    store=SQLiteStore(tmp_path/'test.db')
    cfg=SettingsDocument(site_limit_w=9000,export_margin_w=0,devices=[DeviceConfig(id='tank',
        name='Ballon',kind='water_heater',armed=True,mode='solar',min_power_w=600,max_power_w=600,
        cloud={'start_delay_s':0})])
    store.save_settings(cfg.model_dump(mode='json'))
    adapter=Adapter()
    runtime=Coordinator(store,adapters={'tank':adapter})
    now=utcnow()
    sample=lambda value:Sample(value,'W','test',now,now)
    snapshot=SiteSnapshot(now,sample(-1000),device_states={'tank':DeviceState('tank',sample(0),connected=True)},
                          site_limit_w=9000,export_margin_w=0)
    return runtime,adapter,snapshot


@pytest.mark.asyncio
async def test_concurrent_ticks_send_only_one_start_and_reserve_until_new_measurement(tmp_path):
    runtime,adapter,snapshot=environment(tmp_path)
    await asyncio.gather(runtime.tick(snapshot),runtime.tick(snapshot))
    await asyncio.gather(*list(runtime.command_tasks.values()))
    assert len(adapter.calls)==1
    assert runtime.reservations['tank'].power_w==600
    assert runtime.dispatcher.records['tank']['status']=='accepted'
    now=utcnow()+timedelta(seconds=1)
    sample=Sample(600,'W','test',now,now)
    observed=replace(snapshot,at=now,grid=replace(snapshot.grid,measured_at=now,received_at=now),
        device_states={'tank':DeviceState('tank',sample,connected=True)})
    await runtime.tick(observed)
    assert 'tank' not in runtime.reservations
    assert runtime.dispatcher.records['tank']['status']=='observed'


@pytest.mark.asyncio
async def test_timeout_is_unknown_and_restart_does_not_replay(tmp_path):
    store=SQLiteStore(tmp_path/'db')
    dispatcher=Dispatcher(store,timeout_s=.01)
    adapter=Adapter(delay=.2)
    intent=CommandIntent('one','tank','set_power',600,utcnow()+timedelta(seconds=90))
    await dispatcher.dispatch(intent,adapter)
    assert dispatcher.records['tank']['status']=='unknown'
    recovered=Dispatcher(store)
    assert recovered.records['tank']['status']=='unknown'
    await recovered.dispatch(intent,adapter)
    assert len(adapter.calls)==1


def test_generic_settings_cannot_bypass_arming_and_manual_is_local(tmp_path):
    from app.main import create_app
    from app.settings import RuntimeSettings
    from fastapi.testclient import TestClient
    app=create_app(RuntimeSettings(data_dir=tmp_path))
    client=TestClient(app)
    client.post('/api/v1/setup',json={'token':(tmp_path/'bootstrap-token').read_text(),
        'username':'admin','password':'a-secure-test-password'})
    settings=client.get('/api/v1/settings').json()
    settings['devices']=[DeviceConfig(id=i,name=i,kind='water_heater').model_dump(mode='json') for i in ['one','two']]
    assert client.put('/api/v1/settings',json=settings).status_code==200
    settings['devices'][0]['armed']=True
    assert client.put('/api/v1/settings',json=settings).status_code==409
    assert client.post('/api/v1/devices/one/manual',json={'duration_minutes':30}).status_code==409
    # Simulate a previously commissioned device; API still owns the mode transition.
    app.state.store.save_settings(settings)
    assert client.post('/api/v1/devices/one/manual',json={'duration_minutes':30}).status_code==200
    result=client.get('/api/v1/settings').json()['devices']
    assert result[0]['mode']=='manual' and result[1]['mode']=='off'


@pytest.mark.asyncio
async def test_pause_during_pending_start_is_sent_after_start_finishes(tmp_path):
    runtime,adapter,snapshot=environment(tmp_path)
    entered,release=asyncio.Event(),asyncio.Event()
    async def execute(intent):
        adapter.calls.append(intent)
        if intent.action=='set_power': entered.set();await release.wait()
        return CommandResult(intent.id,True)
    adapter.execute=execute
    await runtime.tick(snapshot)
    await entered.wait()
    settings=runtime.store.load_settings();settings['devices'][0]['mode']='off';runtime.store.save_settings(settings)
    await runtime.tick(snapshot)
    release.set()
    await asyncio.gather(*runtime.command_tasks.values())
    assert [c.action for c in adapter.calls]==['set_power','suspend']
    assert runtime.dispatcher.records['tank']['action']=='suspend'


@pytest.mark.asyncio
async def test_ariston_confirmation_waits_for_cloud_poll_and_keeps_reservation(tmp_path):
    runtime,adapter,snapshot=environment(tmp_path)
    settings=runtime.store.load_settings();settings['devices'][0]['target']=55;runtime.store.save_settings(settings)
    snapshot=replace(snapshot,device_states={'tank':replace(snapshot.device_states['tank'],observed_state='off',target_temperature=55)})
    await runtime.tick(snapshot);await asyncio.gather(*runtime.command_tasks.values())
    later=snapshot.at+timedelta(seconds=91)
    power=Sample(600,'W','test',later,later)
    grid=Sample(-400,'W','test',later,later)
    stale_cloud=replace(snapshot,at=later,grid=grid,device_states={'tank':replace(snapshot.device_states['tank'],observed_power=power)})
    batch=await runtime.tick(stale_cloud)
    assert not any(c.action=='suspend' for c in batch.commands)
    assert 'tank' in runtime.reservations
    at_poll=later+timedelta(seconds=30)
    fresh=replace(stale_cloud,at=at_poll,grid=replace(grid,measured_at=at_poll,received_at=at_poll),
        device_states={'tank':replace(stale_cloud.device_states['tank'],observed_state='on',
            observed_power=replace(power,measured_at=at_poll,received_at=at_poll))})
    await runtime.tick(fresh)
    assert runtime.dispatcher.records['tank']['status']=='observed'


@pytest.mark.asyncio
@pytest.mark.parametrize('device_first',[True,False])
async def test_mixed_measurement_transition_cannot_release_reserved_watts(tmp_path,device_first):
    runtime,adapter,snapshot=environment(tmp_path)
    await runtime.tick(snapshot);await asyncio.gather(*runtime.command_tasks.values())
    later=utcnow()+timedelta(seconds=10)
    new_power=Sample(600,'W','test',later,later)
    new_grid=Sample(-400,'W','test',later,later)
    mixed=replace(snapshot,at=later,grid=snapshot.grid if device_first else new_grid,
        device_states={'tank':replace(snapshot.device_states['tank'],observed_power=new_power if device_first else snapshot.device_states['tank'].observed_power)})
    await runtime.tick(mixed)
    assert 'tank' in runtime.reservations
    coherent=replace(mixed,grid=new_grid,device_states={'tank':replace(mixed.device_states['tank'],observed_power=new_power)})
    await runtime.tick(coherent)
    assert runtime.dispatcher.records['tank']['status']=='observed'
