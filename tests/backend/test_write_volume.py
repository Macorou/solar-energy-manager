"""The 2 s runtime loop must not rewrite unchanged state nor flood the journal."""
from dataclasses import replace
from datetime import timedelta
import json
import sqlite3
import pytest
from app.domain.measurements import utcnow
from app.storage.database import SQLiteStore
from test_charging_accounting import setup_tracker, frame


def observer(path):
    db = sqlite3.connect(path)
    # data_version changes only when another connection commits a write.
    return db, lambda: db.execute('PRAGMA data_version').fetchone()[0]


def test_identical_runtime_value_is_not_rewritten(tmp_path):
    store = SQLiteStore(tmp_path/'app.db')
    db, version = observer(tmp_path/'app.db')
    store.set('runtime_reservations', {'ev': {'power_w': 1380}})
    before = version()
    store.set('runtime_reservations', {'ev': {'power_w': 1380}})
    assert version() == before
    store.set('runtime_reservations', {})
    assert version() != before and store.get('runtime_reservations') == {}
    db.close()


def test_long_session_keeps_a_small_runtime_state_with_exact_energy(tmp_path):
    tracker, store, cfg = setup_tracker(tmp_path); start = utcnow()
    first = energy = 10000
    for second in range(0, 3*3600, 10):
        tracker.update(frame(start+timedelta(seconds=second), energy, stamp=start), cfg)
        energy += 5
    last = energy-5
    session = tracker.sessions['ev']
    assert len(session['contexts']) <= 2 and len(session['points']) <= 360
    assert len(json.dumps(store.get('charging_sessions'))) < 30000
    assert tracker.summary('ev')['energy_kwh'] == pytest.approx((last-first)/1000)
    assert tracker.summary('ev')['solar_percent'] == pytest.approx(50)


def test_clock_only_ticks_are_batched_but_meter_changes_are_saved_at_once(tmp_path):
    tracker, store, cfg = setup_tracker(tmp_path); now = utcnow()
    def unchanged_meter(second):
        tick = frame(now+timedelta(seconds=second), 10000, stamp=now)
        return replace(tick, device_states={'ev': replace(tick.device_states['ev'], energy_measured_at=now)})
    tracker.update(frame(now, 10000, stamp=now), cfg)
    tracker.update(unchanged_meter(2), cfg)  # The estimator settles its SOC representation once.
    db, version = observer(store.path)
    before = version()
    for second in (4, 6):
        tracker.update(unchanged_meter(second), cfg)
    assert version() == before
    tracker.update(frame(now+timedelta(seconds=8), 10300, stamp=now), cfg)
    assert version() != before
    db.close()
    from app.runtime.charging import ChargingTracker
    reopened = ChargingTracker(store)
    assert reopened.sessions['ev']['energy_wh'] == 300


def test_verbose_traces_cannot_evict_errors_and_purges_are_batched(tmp_path, monkeypatch):
    from app.diagnostics import journal
    monkeypatch.setattr(journal, 'MAX_ENTRIES', 5)
    monkeypatch.setattr(journal, 'MAX_VERBOSE_ENTRIES', 20)
    monkeypatch.setattr(journal, 'PURGE_EVERY', 10)
    log = SQLiteStore(tmp_path/'app.db').journal
    log.write('ERROR', 'ocpp:wallbox', 'Coupure nocturne')
    for i in range(500):
        log.write('TRACE', 'site', f'Réseau={i} W')
    page = log.query(level='TRACE', limit=500)
    levels = [entry['level'] for entry in page['entries']]
    assert levels.count('ERROR') == 1
    assert 20 <= levels.count('TRACE') <= 30
    assert page['entries'][-1]['message'] == 'Réseau=499 W'
    assert page['max_verbose_entries'] == 20 and page['max_entries'] == 5


@pytest.mark.asyncio
async def test_site_trace_is_periodic_unless_a_decision_changes(tmp_path):
    from app.runtime.coordinator import Coordinator
    _, store, cfg = setup_tracker(tmp_path); now = utcnow()
    cfg.devices[0].armed = True; cfg.devices[0].mode = 'solar'
    store.save_settings(cfg.model_dump(mode='json'))
    runtime = Coordinator(store)
    for second in range(0, 32, 2):
        await runtime.tick(frame(now+timedelta(seconds=second), 10000, stamp=now))
    traces = [e for e in store.journal.query(level='TRACE')['entries'] if e['message'].startswith('Réseau=')]
    assert len(traces) == 2
    await runtime.tick(frame(now+timedelta(seconds=32), 10000, stamp=now, plugged=False))
    traces = [e for e in store.journal.query(level='TRACE')['entries'] if e['message'].startswith('Réseau=')]
    assert len(traces) == 3
