from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
import asyncio
import httpx
import pytest

from app.connectors.home_assistant.client import HomeAssistantSource
from app.connectors.home_assistant.mapping import normalize_power
from app.connectors.peugeot.client import ProviderError
from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Quality, Sample, utcnow
from app.domain.schedules import ChargeAuthorization
from app.domain.site import SiteSnapshot
from app.domain.vehicles import VehicleTelemetry
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.runtime.coordinator import Coordinator
from app.runtime.dispatcher import Dispatcher
from app.settings import HomeAssistantConfig, SettingsDocument, VehicleConfig
from app.simulation.clock import SimulatedClock
from app.storage.database import SQLiteStore


def ha_power(value, now, old, entity='sensor.power'):
    return normalize_power({'entity_id': entity, 'state': str(value),
        'attributes': {'unit_of_measurement': 'W'}, 'last_reported': old.isoformat()}, now)


@pytest.mark.parametrize('kind,mode', [('water_heater','manual'), ('water_heater','solar'),
    ('water_heater','off_peak_solar'), ('charger','manual'), ('charger','solar'), ('charger','planned')])
def test_unchanged_ha_power_does_not_block_manual_or_automatic_start(kind, mode):
    clock = SimulatedClock(); now = clock.now(); old = now-timedelta(days=1)
    power = ha_power(0, now, old)
    grid = ha_power(-5000 if mode == 'solar' else 1000, now, old, 'sensor.grid')
    spec = DeviceSpec('device', kind, min_power_w=700 if kind == 'water_heater' else 1380,
                      max_power_w=2570 if kind == 'water_heater' else 3700)
    policy = DevicePolicy('device', mode=mode, armed=True, start_delay_s=0, off_peak=True,
        vehicle_id='car' if kind == 'charger' else '', manual_until=now+timedelta(minutes=30))
    snapshot = SiteSnapshot(now, grid, device_states={'device': DeviceState('device', power, connected=True)},
        vehicle_telemetry={'car': VehicleTelemetry(75,214,'disconnected',now,now,Quality.FRESH)},
        site_limit_w=11000, export_margin_w=100)
    auth = {'device': ChargeAuthorization('car',True,True,80,now+timedelta(hours=1))}
    batch = EnergyEngine(clock).evaluate(snapshot, [spec], {'device': policy}, auth)
    assert power.measured_at == old  # Never rewrite the provider's date.
    assert [(c.device_id,c.limit_w) for c in batch.commands] == [('device',spec.max_power_w)]


@pytest.mark.parametrize('mode', ['solar','planned'])
def test_recently_retrieved_old_soc_does_not_block_automatic_charge(mode):
    clock=SimulatedClock(); now=clock.now(); sample=lambda v: Sample(v,'W','test',now,now)
    telemetry=VehicleTelemetry(75,214,'disconnected',now-timedelta(hours=3),now,Quality.FRESH)
    snapshot=SiteSnapshot(now,sample(-5000),device_states={'ev':DeviceState('ev',sample(0),connected=True)},
        vehicle_telemetry={'car':telemetry},site_limit_w=11000)
    policy=DevicePolicy('ev',mode=mode,armed=True,vehicle_id='car',start_delay_s=0)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700)
    auth={'ev':ChargeAuthorization('car',True,True,80,now+timedelta(hours=1))}
    batch=EnergyEngine(clock).evaluate(snapshot,[spec],{'ev':policy},auth)
    assert not telemetry.fresh(now,1800)
    assert batch.commands and batch.commands[0].limit_w == 3700
    reached=replace(snapshot,vehicle_telemetry={'car':replace(telemetry,soc=80)})
    assert not EnergyEngine(clock).evaluate(reached,[spec],{'ev':policy},auth).commands


@pytest.mark.parametrize('value', ['unavailable','unknown','nan','inf'])
def test_invalid_ha_value_remains_unusable_even_after_recent_read(value):
    now=utcnow()
    assert not ha_power(value,now,now-timedelta(days=1)).usable(now,30)


def test_old_confirmation_and_unverified_old_sample_remain_unusable():
    now=utcnow(); old=now-timedelta(days=1)
    assert not ha_power(0,old,old).usable(now,30)
    assert not Sample(0,'W','unverified',old,now).usable(now,30)


def test_current_source_does_not_validate_future_or_missing_provider_time():
    now=utcnow()
    assert not ha_power(0,now,now+timedelta(minutes=1)).usable(now,30)
    assert not normalize_power({'entity_id':'sensor.power','state':'0',
        'attributes':{'unit_of_measurement':'W'}},now).usable(now,30)


def test_old_soc_cannot_be_used_after_loss_of_provider_contact():
    now=utcnow(); old=now-timedelta(days=1)
    value=VehicleTelemetry(75,214,'disconnected',old,now,Quality.FRESH)
    assert value.usable(now,1800) and not value.fresh(now,1800)
    assert not replace(value,quality=Quality.UNAVAILABLE).usable(now,1800)
    assert not replace(value,received_at=old).usable(now,1800)
    assert not replace(value,soc=101).usable(now,1800)


def test_rechecking_old_zero_is_not_physical_confirmation_of_a_command(tmp_path):
    now=utcnow(); old=now-timedelta(days=1); after=now+timedelta(seconds=1)
    dispatcher=Dispatcher(SQLiteStore(tmp_path/'test.db'))
    dispatcher.records['tank']={'status':'accepted','sent_at':now.isoformat(),
        'power_w':0,'action':'suspend'}
    power=ha_power(0,after,old)
    snapshot=SiteSnapshot(after,ha_power(1000,after,old,'sensor.grid'),
        device_states={'tank':DeviceState('tank',power,connected=True,observed_state='off')})
    assert power.usable(after,30)
    assert dispatcher.reconcile(snapshot,{})==[]
    assert dispatcher.records['tank']['status']=='accepted'


@pytest.mark.asyncio
async def test_ha_connection_failure_invalidates_unchanged_value():
    old=(utcnow()-timedelta(days=1)).isoformat(); failing=False
    def response(request):
        if failing: return httpx.Response(503)
        return httpx.Response(200,json=[{'entity_id':'sensor.grid','state':'0',
            'attributes':{'unit_of_measurement':'W'},'last_reported':old}])
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        source=HomeAssistantSource(HomeAssistantConfig(url='http://ha',grid_entity='sensor.grid'),'secret',http=http)
        await source.connect()
        assert source.snapshot().grid.usable(utcnow(),30)
        failing=True
        with pytest.raises(httpx.HTTPStatusError): await source.connect()
        assert not source.snapshot().grid.usable(utcnow(),30)


@pytest.mark.asyncio
async def test_peugeot_failure_keeps_display_value_but_disables_automatic_control(tmp_path):
    store=SQLiteStore(tmp_path/'test.db'); config=SettingsDocument(vehicles=[VehicleConfig(id='car')])
    store.save_settings(config.model_dump(mode='json'))
    async def fail(vin): raise ProviderError('reconnect_required')
    runtime=Coordinator(store,app=SimpleNamespace(state=SimpleNamespace(peugeot=SimpleNamespace(read_telemetry=fail))))
    runtime.telemetry['car']=VehicleTelemetry(75,214,'disconnected',utcnow(),utcnow(),Quality.FRESH)
    runtime.running=True
    task=asyncio.create_task(runtime.poll_vehicle(config.vehicles[0]))
    try:
        await asyncio.sleep(0)
        assert runtime.errors['vehicle_car']=='reconnect_required'
        assert runtime.telemetry['car'].soc==75
        assert runtime.telemetry['car'].quality==Quality.UNAVAILABLE
    finally:
        runtime.running=False;task.cancel();await asyncio.gather(task,return_exceptions=True)
