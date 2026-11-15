"""A RemoteStart the station accepts but never opens must not block SEM for the night.

2026-11-15, 00:26: the Wallbox accepted RemoteStartTransaction and stayed in Finishing without a
StartTransaction. The start stayed pending forever, so the stop sent at 00:27 could never be
confirmed and SEM refused every command until the car was unplugged.
"""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.connectors.ocpp.registry import START_PENDING_S, ChargerAdapter, OcppRegistry
from app.connectors.ocpp.station import Station
from app.domain.commands import CommandIntent
from app.domain.measurements import Sample, utcnow
from app.domain.site import SiteSnapshot
from app.runtime.dispatcher import Dispatcher
from app.settings import DeviceConfig, SettingsDocument
from app.storage.database import SQLiteStore

CONFIG = DeviceConfig(id='ev', name='EV', kind='charger', charge_point_id='box', armed=True, mode='planned',
                      capabilities_verified=True, offline_behavior_verified=True)


def finishing(tmp_path, started_s_ago):
    """The station ended its session, then accepted a RemoteStart `started_s_ago` seconds ago."""
    store = SQLiteStore(tmp_path/'db'); store.save_settings(SettingsDocument(devices=[CONFIG]).model_dump(mode='json'))
    registry = OcppRegistry(store, lambda: [CONFIG], lambda _: None)
    station = Station('box', None, registry); registry.stations['box'] = station
    registry.pending_start['ev'] = {'state': 'accepted', 'at': (utcnow()-timedelta(seconds=started_s_ago)).isoformat()}
    station.status(1, 'NoError', 'Finishing', timestamp=utcnow().isoformat())
    return store, registry


@pytest.mark.parametrize('age,pending', [(5, True), (START_PENDING_S-5, True), (START_PENDING_S+1, False)])
def test_an_accepted_start_without_session_stops_being_pending_after_a_minute(tmp_path, age, pending):
    store, registry = finishing(tmp_path, age)
    assert registry.state('ev').start_pending is pending
    assert ('ev' in registry.pending_start) is pending
    warnings = [e['message'] for e in store.journal.query(areas=('ocpp:box',))['entries'] if e['level'] == 'WARN']
    assert warnings == ([] if pending else ['Démarrage accepté par la borne sans ouverture de session : abandonné'])


def test_the_stop_sent_after_an_ignored_start_is_confirmed(tmp_path):
    store, registry = finishing(tmp_path, START_PENDING_S+10)
    now = utcnow(); sent = now-timedelta(seconds=30)
    state = registry.state('ev')
    snapshot = SiteSnapshot(now, Sample(400, 'W', 'HA-grid', now, now, checked_at=now), device_states={'ev': state},
                            site_limit_w=11000)
    dispatcher = Dispatcher(store)
    dispatcher.records['ev'] = {'id': 'stop', 'status': 'accepted', 'action': 'suspend', 'power_w': 0,
        'sent_at': sent.isoformat(), 'expires_at': (sent+timedelta(seconds=90)).isoformat(),
        'confirm_by': (sent+timedelta(seconds=90)).isoformat(), 'reason': 'Courant réel de recharge indisponible'}
    assert dispatcher.reconcile(snapshot, {'ev': CONFIG}) == ['ev']
    assert dispatcher.records['ev']['status'] == 'observed'


def test_a_recent_start_still_protects_the_stop_confirmation(tmp_path):
    store, registry = finishing(tmp_path, 5)
    now = utcnow(); sent = now-timedelta(seconds=2)
    snapshot = SiteSnapshot(now, Sample(400, 'W', 'HA-grid', now, now, checked_at=now),
                            device_states={'ev': registry.state('ev')}, site_limit_w=11000)
    dispatcher = Dispatcher(store)
    dispatcher.records['ev'] = {'id': 'stop', 'status': 'accepted', 'action': 'suspend', 'power_w': 0,
        'sent_at': sent.isoformat(), 'expires_at': (sent+timedelta(seconds=90)).isoformat(),
        'confirm_by': (sent+timedelta(seconds=90)).isoformat(), 'reason': 'x'}
    assert dispatcher.reconcile(snapshot, {'ev': CONFIG}) == []


@pytest.mark.asyncio
async def test_a_new_offer_asks_for_a_session_again_after_an_ignored_start(tmp_path):
    store, registry = finishing(tmp_path, START_PENDING_S+1)
    calls = []
    class Box:
        async def call(self, payload): calls.append(type(payload).__name__); return SimpleNamespace(status='Accepted')
    registry.stations['box'] = Box()
    result = await ChargerAdapter(registry, CONFIG).execute(
        CommandIntent('a', 'ev', 'set_power', 3680, utcnow()+timedelta(seconds=90)))
    assert result.accepted and calls.count('RemoteStartTransaction') == 1


@pytest.mark.asyncio
async def test_the_night_block_clears_itself(tmp_path):
    """The stop of 00:27, still unconfirmed hours later: the next tick confirms it and lifts the block."""
    from app.runtime.coordinator import Coordinator
    store, registry = finishing(tmp_path, 3600)
    sent = utcnow()-timedelta(minutes=50)
    store.set('runtime_commands', {'ev': {'id': 'stop', 'device_id': 'ev', 'status': 'accepted', 'action': 'suspend',
        'power_w': 0, 'sent_at': sent.isoformat(), 'expires_at': (sent+timedelta(seconds=90)).isoformat(),
        'confirm_by': (sent+timedelta(seconds=90)).isoformat(), 'reason': 'Courant réel de recharge indisponible'}})
    class Adapter:
        async def execute(self, _): raise AssertionError('No physical command is needed')
        async def request_status(self): return True
    runtime = Coordinator(store, adapters={'ev': Adapter()})
    runtime.errors['ev'] = 'Résultat de commande inconnu : vérification requise'
    runtime.engine.requested['ev'] = 0
    now = utcnow()
    state = registry.state('ev')
    await runtime.tick(SiteSnapshot(now, Sample(400, 'W', 'HA-grid', now, now, checked_at=now),
                                    device_states={'ev': state}, site_limit_w=11000))
    assert runtime.dispatcher.records['ev']['status'] == 'observed'
    assert 'ev' not in runtime.errors
    assert not runtime.reasons['ev'].startswith('Vérification requise')
