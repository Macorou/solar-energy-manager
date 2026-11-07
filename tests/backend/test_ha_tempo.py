import httpx
import pytest

from app.connectors.home_assistant.client import HomeAssistantSource
from app.settings import HomeAssistantConfig

TEMPO='sensor.rte_tempo_couleur_actuelle'


def st(name,value,unit='W'):
    return {'entity_id':name,'state':value,'attributes':{'unit_of_measurement':unit}}


async def source_for(states,entity=TEMPO):
    http=httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=states)))
    source=HomeAssistantSource(HomeAssistantConfig(url='http://ha.test',grid_entity='sensor.grid',tempo_entity=entity),'test-only',http=http)
    await source.connect()
    return source,http


@pytest.mark.asyncio
async def test_snapshot_exposes_raw_tempo_state():
    source,http=await source_for([st('sensor.grid','400'),st(TEMPO,'Rouge',None)])
    assert source.snapshot().tempo_state=='Rouge'
    source.connected=False
    assert source.snapshot().tempo_state is None
    await http.aclose()


@pytest.mark.asyncio
async def test_tempo_missing_or_unconfigured_is_none_and_connect_succeeds():
    source,http=await source_for([st('sensor.grid','400')])
    assert source.connected and source.snapshot().tempo_state is None
    await http.aclose()
    source,http=await source_for([st('sensor.grid','400'),st(TEMPO,'Rouge',None)],entity='')
    assert source.snapshot().tempo_state is None
    await http.aclose()


@pytest.mark.asyncio
async def test_snapshot_exposes_tempo_last_changed():
    from datetime import datetime,timezone
    state=st(TEMPO,'Rouge',None)|{'last_changed':'2026-11-07T05:00:19.123456+00:00'}
    source,http=await source_for([st('sensor.grid','400'),state])
    assert source.snapshot().tempo_changed_at==datetime(2026,11,7,5,0,19,123456,tzinfo=timezone.utc)
    source.states[TEMPO]=dict(state,last_changed='bad')
    assert source.snapshot().tempo_changed_at is None
    source.states[TEMPO]=st(TEMPO,'Rouge',None)
    assert source.snapshot().tempo_changed_at is None
    source.states[TEMPO]=state; source.connected=False
    assert source.snapshot().tempo_changed_at is None
    await http.aclose()
