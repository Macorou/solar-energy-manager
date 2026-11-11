"""A source whose clock is a few seconds ahead of SEM's still gives usable measures."""
from datetime import timedelta

import httpx

from app.connectors.home_assistant.client import HomeAssistantSource
from app.domain.measurements import CLOCK_TOLERANCE_S, Sample, late, utcnow
from app.settings import HomeAssistantConfig
from app.storage.database import SQLiteStore


def stamped(lead_s, now):
    return Sample(500, 'W', 'HA', now+timedelta(seconds=lead_s), now, checked_at=now)


def test_measure_stamped_within_the_clock_tolerance_is_usable():
    now = utcnow()
    assert stamped(CLOCK_TOLERANCE_S-1, now).usable(now, 30)
    assert not stamped(CLOCK_TOLERANCE_S+1, now).usable(now, 30)
    assert not late(stamped(CLOCK_TOLERANCE_S+1, now), now, 30)


async def read_grid(tmp_path, lead_s):
    store = SQLiteStore(tmp_path/'db')
    state = lambda: {'entity_id': 'sensor.grid', 'state': '500', 'attributes': {'unit_of_measurement': 'W'},
                     'last_updated': (utcnow()+timedelta(seconds=lead_s)).isoformat()}
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[state()])))
    source = HomeAssistantSource(HomeAssistantConfig(url='http://ha.test', grid_entity='sensor.grid'), 'token',
                                 http=http, journal=store.journal)
    await source.connect(); await source.connect()
    warnings = [e['message'] for e in store.journal.query(level='TRACE')['entries'] if e['level'] == 'WARN']
    return source.snapshot().grid, warnings


async def test_home_assistant_clock_slightly_ahead_is_accepted_without_warning(tmp_path):
    grid, warnings = await read_grid(tmp_path, 2)
    assert grid.usable(utcnow(), 30) and warnings == []


async def test_home_assistant_clock_far_ahead_is_refused_and_reported_once(tmp_path):
    grid, warnings = await read_grid(tmp_path, 45)
    assert not grid.usable(utcnow(), 30)
    assert len(warnings) == 1 and 'Horloge de Home Assistant en avance' in warnings[0]
