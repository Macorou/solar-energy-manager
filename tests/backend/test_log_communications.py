import json
import httpx
import pytest
from app.storage.database import SQLiteStore
from app.connectors.home_assistant.client import HomeAssistantSource
from app.connectors.peugeot.client import PeugeotAdapter, ProviderError
from app.connectors.ocpp.server import Connection
from app.settings import HomeAssistantConfig


@pytest.mark.asyncio
async def test_ha_success_and_failure_are_visible_without_tokens(tmp_path):
    journal = SQLiteStore(tmp_path/'app.db').journal
    def transport(request):
        return httpx.Response(200, json=[{'entity_id':'sensor.grid', 'state':'834',
            'attributes':{'unit_of_measurement':'W'}, 'last_updated':'2026-10-30T20:00:00Z'}])
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        source = HomeAssistantSource(HomeAssistantConfig(url='http://ha.local', grid_entity='sensor.grid'),
                                     'private-ha-token', http=http, journal=journal)
        await source.connect()
        assert source.connected
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(401))) as http:
        source.http = http
        with pytest.raises(httpx.HTTPStatusError):
            await source.connect()
    entries = journal.query(level='TRACE')['entries']
    assert any(r['area']=='ha' and r['level']=='DEBUG' for r in entries)
    assert any(r['area']=='ha' and r['level']=='ERROR' and '401' in r['message'] for r in entries)
    assert 'private-ha-token' not in json.dumps(entries)


@pytest.mark.asyncio
async def test_peugeot_provider_errors_are_recorded_with_safe_operation_name(tmp_path):
    journal = SQLiteStore(tmp_path/'app.db').journal
    class Secrets:
        def get(self, key): return 'private-refresh'
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(401))) as http:
        adapter = PeugeotAdapter(Secrets(), http=http, journal=journal)
        with pytest.raises(ProviderError, match='reconnect_required'):
            await adapter.read_telemetry('VF3PRIVATE12345678')
    entries = journal.query(level='TRACE')['entries']
    assert any(r['area']=='peugeot' and r['level']=='ERROR' and '401' in r['message'] for r in entries)
    assert 'private-refresh' not in json.dumps(entries) and 'VF3PRIVATE12345678' not in json.dumps(entries)


@pytest.mark.asyncio
async def test_ocpp_transport_keeps_wire_unchanged_but_records_no_idtag(tmp_path):
    journal = SQLiteStore(tmp_path/'app.db').journal
    incoming = json.dumps([2, 'a', 'StartTransaction', {'connectorId':1, 'idTag':'private-rfid', 'meterStart':1000}])
    class Websocket:
        async def receive_text(self): return incoming
        async def send_text(self, value): self.value=value
    websocket = Websocket()
    transport = Connection(websocket, journal=journal, station_id='wallbox')
    assert await transport.recv() == incoming
    outgoing = json.dumps([3,'a',{'transactionId':12,'idTagInfo':{'status':'Accepted'}}])
    await transport.send(outgoing)
    assert websocket.value == outgoing
    entries = journal.query(level='TRACE')['entries']
    assert len(entries)==2
    assert all(e['area']=='ocpp:wallbox' for e in entries)
    assert 'StartTransaction' in entries[0]['message']
    assert 'private-rfid' not in json.dumps(entries)


def test_unvalidated_ocpp_fields_cannot_be_used_to_smuggle_sensitive_payloads(tmp_path):
    from app.diagnostics.ocpp import OcppDiagnostics
    journal = SQLiteStore(tmp_path/'app.db').journal
    wire = OcppDiagnostics(journal, 'wallbox')
    wire.record(json.dumps([2, 'a', 'MeterValues', {'meterValue':[{'sampledValue':[
        {'value':'VF3PRIVATE12345678', 'measurand':'private-rfid', 'unit':'private-token'}]}]}]), 'RX')
    wire.record(json.dumps([2, 'b', 'SetChargingProfile', {'csChargingProfiles':{'chargingSchedule':{
        'chargingSchedulePeriod':[{'limit':16,'private':'private-profile-secret'}], 'chargingRateUnit':'A'}}}]), 'TX')
    messages=json.dumps(journal.query(level='TRACE')['entries'])
    for secret in ('VF3PRIVATE12345678','private-rfid','private-token','private-profile-secret'):
        assert secret not in messages
    assert '16' in messages


@pytest.mark.asyncio
async def test_missing_ocpp_reply_is_logged_with_operation_without_changing_timeout(tmp_path):
    import asyncio
    from app.connectors.ocpp.station import Station
    from app.connectors.ocpp.registry import OcppRegistry
    from ocpp.v16 import call
    store=SQLiteStore(tmp_path/'app.db')
    class Transport:
        async def send(self, value): pass
    station=Station('wallbox',Transport(),OcppRegistry(store,lambda:[],lambda _:None))
    station._response_timeout=.01
    with pytest.raises(asyncio.TimeoutError):
        await station.call(call.TriggerMessage(requested_message='MeterValues'))
    entries=store.journal.query(level='ERROR')['entries']
    assert any('TriggerMessage' in e['message'] and 'TimeoutError' in e['message'] for e in entries)
