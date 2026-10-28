from dataclasses import replace
from datetime import timedelta

import httpx
import pytest

from app.connectors.home_assistant.client import HomeAssistantSource
from app.domain.measurements import Sample, utcnow
from app.domain.site import SiteSnapshot
from app.engine.budget import power_coherent
from app.runtime.coordinator import Coordinator
from app.settings import HomeAssistantConfig, SettingsDocument
from app.storage.database import SQLiteStore


def entity(name,value,unit='W'):
    return {'entity_id':name,'state':str(value),'attributes':{'unit_of_measurement':unit},
            'last_updated':(utcnow()-timedelta(hours=2)).isoformat()}


@pytest.mark.asyncio
@pytest.mark.parametrize('value,unit,expected',[(0,'W',0),(5.2,'kW',5200)])
async def test_optional_house_sensor_is_normalized_with_original_date_and_current_check(value,unit,expected):
    states=[entity('sensor.grid',400),entity('sensor.house',value,unit)]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=states))) as http:
        source=HomeAssistantSource(HomeAssistantConfig(url='http://ha.test',grid_entity='sensor.grid',house_entity='sensor.house'),'test-only',http=http)
        await source.connect(); snapshot=source.snapshot()
        assert snapshot.house.value==expected and snapshot.house.usable(snapshot.at,30)
        assert snapshot.house.measured_at<snapshot.at-timedelta(hours=1)
        assert snapshot.house.checked_at>=snapshot.at-timedelta(seconds=1)
        await source.close()
        assert not source.snapshot().house.usable(utcnow(),30)


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid',['missing','unavailable','wrong_unit','negative','feedback'])
async def test_invalid_display_sensor_does_not_break_grid_control(invalid):
    house=entity('sensor.house',700)
    if invalid=='unavailable': house['state']='unavailable'
    elif invalid=='wrong_unit': house['attributes']['unit_of_measurement']='kWh'
    elif invalid=='negative': house['state']='-1'
    elif invalid=='feedback': house['attributes']['source']='solar_energy_manager'
    states=[entity('sensor.grid',400)]+([] if invalid=='missing' else [house])
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=states))) as http:
        source=HomeAssistantSource(HomeAssistantConfig(url='http://ha.test',grid_entity='sensor.grid',house_entity='sensor.house'),'test-only',http=http)
        await source.connect(); snapshot=source.snapshot()
        assert source.connected and snapshot.grid.usable(snapshot.at,30)
        assert snapshot.house is None or not snapshot.house.usable(snapshot.at,30)
        assert power_coherent(snapshot)


def test_house_mapping_and_sample_are_exposed_without_changing_control_budget(tmp_path):
    now=utcnow(); store=SQLiteStore(tmp_path/'db')
    settings=SettingsDocument(home_assistant={'house_entity':'sensor.house'})
    store.save_settings(settings.model_dump(mode='json'))
    runtime=Coordinator(store)
    runtime.snapshot=SiteSnapshot(now,grid=Sample(400,'W','grid',now,now),
        house=Sample(0,'W','sensor.house',now-timedelta(days=1),now,checked_at=now))
    public=runtime.public_state()
    assert public['house_configured'] is True
    assert public['house']['value']==0 and public['house']['usable'] is True
    assert store.load_settings()['home_assistant']['house_entity']=='sensor.house'
    assert power_coherent(replace(runtime.snapshot,house=None))==power_coherent(runtime.snapshot)


def test_old_configuration_keeps_calculation_selected(tmp_path):
    config=HomeAssistantConfig.model_validate({'grid_entity':'sensor.grid','solar_entity':'sensor.solar'})
    assert config.house_entity==''
