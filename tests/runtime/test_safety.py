from dataclasses import replace
from datetime import timedelta
import pytest
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock
from app.domain.devices import DeviceSpec,DeviceState
from app.domain.site import SiteSnapshot
from app.domain.measurements import Sample,utcnow
from app.domain.schedules import ChargeAuthorization


def test_unknown_managed_power_cannot_create_network_capacity():
    clock=SimulatedClock()
    sample=Sample(2000,'W','test',clock.now(),clock.now())
    snapshot=SiteSnapshot(clock.now(),sample,device_states={'ev':DeviceState('ev',connected=True)},site_limit_w=9000)
    batch=EnergyEngine(clock).evaluate(snapshot,[DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700)],
        {'ev':DevicePolicy('ev',mode='planned',armed=True)},
        {'ev':ChargeAuthorization('car',True,True,80,clock.now()+timedelta(hours=1))})
    assert not any(c.limit_w for c in batch.commands)


def test_heater_needs_its_whole_fixed_power_before_start():
    clock=SimulatedClock()
    sample=lambda value:Sample(value,'W','test',clock.now(),clock.now())
    snapshot=SiteSnapshot(clock.now(),sample(-900),device_states={'tank':DeviceState('tank',sample(0),connected=True)},site_limit_w=9000,export_margin_w=0)
    batch=EnergyEngine(clock).evaluate(snapshot,[DeviceSpec('tank','water_heater',min_power_w=600,max_power_w=2500)],
        {'tank':DevicePolicy('tank',armed=True,start_delay_s=0)},{})
    assert not any(c.limit_w for c in batch.commands)


def test_simulation_has_no_real_connector_or_settings_side_effect(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.settings import RuntimeSettings
    app=create_app(RuntimeSettings(data_dir=tmp_path))
    client=TestClient(app)
    client.post('/api/v1/setup',json={'token':(tmp_path/'bootstrap-token').read_text(),
        'username':'admin','password':'a-secure-test-password'})
    before=app.state.store.load_settings()
    result=client.post('/api/v1/simulation',json={'surplus_w':900}).json()
    assert result['simulation'] and result['commands'][0]['device_id']=='demo-tank'
    assert app.state.store.load_settings()==before
    assert app.state.coordinator.dispatcher.records=={}


def test_duplicate_ocpp_connector_or_meter_cannot_double_allocate():
    import pytest
    from app.settings import SettingsDocument,DeviceConfig
    device=DeviceConfig(id='a',name='a',kind='charger',charge_point_id='wallbox')
    with pytest.raises(ValueError,match='OCPP'):
        SettingsDocument(devices=[device,device.model_copy(update={'id':'b'})])
    with pytest.raises(ValueError,match='mesure'):
        SettingsDocument(home_assistant={'device_power_entities':{'a':'sensor.power','b':'sensor.power'}})


@pytest.mark.asyncio
async def test_expired_schedule_is_recorded_once_without_catchup(tmp_path):
    from app.runtime.coordinator import Coordinator
    from app.settings import SettingsDocument,VehicleConfig,ChargeProgram
    from app.storage.database import SQLiteStore
    from datetime import datetime,timezone
    from zoneinfo import ZoneInfo
    store=SQLiteStore(tmp_path/'db')
    config=SettingsDocument(vehicles=[VehicleConfig(id='car')],schedules=[ChargeProgram(id='work',vehicle_id='car')])
    store.save_settings(config.model_dump(mode='json'))
    runtime=Coordinator(store)
    before=datetime(2026,10,26,5,44,tzinfo=ZoneInfo('Europe/Paris')).astimezone(timezone.utc)
    await runtime.tick(SiteSnapshot(before))
    await runtime.tick(SiteSnapshot(before+timedelta(minutes=2)))
    await runtime.tick(SiteSnapshot(before+timedelta(minutes=3)))
    results=[e for e in store.events() if e['kind']=='schedule_incomplete']
    assert len(results)==1 and results[0]['details']['program_id']=='work'
