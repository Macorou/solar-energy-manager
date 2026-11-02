from datetime import datetime, timezone, timedelta
import httpx
import pytest
from app.connectors.peugeot.client import PeugeotAdapter, ProviderError
from app.connectors.peugeot.telemetry import parse_telemetry


class Secrets:
    def __init__(self): self.values = {'peugeot_refresh': 'private-refresh'}
    def get(self, key): return self.values.get(key)
    def set(self, key, value): self.values[key] = value


@pytest.mark.asyncio
async def test_refresh_rotation_and_source_timestamp_are_preserved():
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if 'access_token' in request.url.path:
            assert b'private-refresh' in request.content
            return httpx.Response(200, json={'access_token':'access','refresh_token':'rotated','expires_in':3600})
        if request.url.path.endswith('/vehicles'):
            return httpx.Response(200,json={'_embedded':{'vehicles':[{'id':'provider-id','vin':'VIN'}]}})
        assert request.headers['authorization'] == 'Bearer access'
        return httpx.Response(200,json={'energy':[{'type':'Electric','level':67,'autonomy':210,
            'updatedAt':'2026-10-26T09:00:00Z','charging':{'status':'InProgress'}}]})
    secrets = Secrets()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        adapter = PeugeotAdapter(secrets, http=http)
        value = await adapter.read_telemetry('VIN')
        assert secrets.get('peugeot_refresh') == 'rotated'
        assert value.soc == 67 and value.range_km == 210
        assert value.measured_at.hour == 9
        assert not value.fresh(datetime(2026,10,26,12,tzinfo=timezone.utc),1800)
        await adapter.read_telemetry('VIN')
        assert calls.count('/connectedcar/v4/user/vehicles/provider-id/status') == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('status,code', [(400,'reconnect_required'),(429,'rate_limited')])
async def test_provider_errors_never_expose_response_secrets(status, code):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(status,
        json={'error':'invalid_grant','description':'private-refresh'}))) as http:
        adapter = PeugeotAdapter(Secrets(),http=http)
        with pytest.raises(ProviderError) as result: await adapter.refresh_access()
        assert str(result.value) == code
        with pytest.raises(ProviderError): await adapter.refresh_access()


@pytest.mark.asyncio
async def test_auth_callback_rejects_wrong_state_before_exchange():
    adapter = PeugeotAdapter(Secrets())
    challenge = adapter.begin_auth()
    assert 'state=' in challenge['url']
    with pytest.raises(ProviderError, match='invalid_callback'):
        await adapter.complete_auth('mymap://oauth2redirect/fr?code=secret&state=wrong')
    await adapter.close()


def test_invalid_or_missing_provider_time_is_not_fresh():
    for energy in ({'level':45}, {'level':101,'updatedAt':'2026-10-26T09:00:00Z'}):
        sample = parse_telemetry({'energy':[dict(type='Electric', **energy)]})
        assert not sample.fresh(datetime.now(timezone.utc),1800)
