from datetime import datetime, timezone, timedelta
import asyncio
import json
import httpx
import pytest
import websockets


def test_power_units_sign_and_timestamp_are_preserved():
    from app.connectors.home_assistant.mapping import normalize_power
    now = datetime.now(timezone.utc)
    old = now-timedelta(minutes=2)
    state = {'entity_id':'sensor.grid','state':'1.5','attributes':{'unit_of_measurement':'kW'},
             'last_updated':old.isoformat()}
    power = normalize_power(state, now, invert=True)
    assert power.value == -1500
    assert power.measured_at == old
    assert not power.usable(now,30)
    state['state'] = 'unavailable'
    assert normalize_power(state, now).value is None


def test_project_return_entity_is_rejected_as_source():
    from app.connectors.home_assistant.mapping import normalize_power
    with pytest.raises(ValueError, match='loop|boucle'):
        normalize_power({'entity_id':'sensor.solar_energy_manager_grid','state':'123',
            'attributes':{'unit_of_measurement':'W'}}, datetime.now(timezone.utc))


async def test_real_websocket_updates_and_disconnect_invalidate_source():
    from app.connectors.home_assistant.client import HomeAssistantSource
    from app.settings import HomeAssistantConfig
    now = datetime.now(timezone.utc).isoformat()
    state = {'entity_id':'sensor.grid','state':'-500','attributes':{'unit_of_measurement':'W'},
             'last_updated':now}
    async def handler(ws):
        await ws.send(json.dumps({'type':'auth_required'}))
        auth = json.loads(await ws.recv())
        assert auth == {'type':'auth','access_token':'test-token'}
        await ws.send(json.dumps({'type':'auth_ok'}))
        subscription = json.loads(await ws.recv())
        assert subscription['event_type'] == 'state_changed'
        await ws.send(json.dumps({'type':'event','event':{'data':{'entity_id':'sensor.grid',
            'new_state':state | {'state':'-1200'}}}}))
        await asyncio.sleep(0.1)
    async with websockets.serve(handler,'127.0.0.1',0) as server:
        port = server.sockets[0].getsockname()[1]
        http = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200,json=[state])))
        source = HomeAssistantSource(HomeAssistantConfig(url=f'http://127.0.0.1:{port}',grid_entity='sensor.grid'), 'test-token', http=http)
        await source.connect()
        assert source.snapshot().grid.value == -500
        changed = asyncio.Event()
        async def update(snapshot):
            if snapshot.grid and snapshot.grid.value == -1200:
                changed.set()
        runner = asyncio.create_task(source.subscribe(update))
        await asyncio.wait_for(changed.wait(),2)
        assert source.snapshot().grid.value == -1200
        await source.close()
        runner.cancel()
        await asyncio.gather(runner,return_exceptions=True)
        assert not source.snapshot().grid.usable(datetime.now(timezone.utc),30)
        await http.aclose()
