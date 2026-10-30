from dataclasses import replace
from datetime import timedelta
import pytest

from app.runtime.charging import ChargingTracker
from app.storage.database import SQLiteStore
from test_charging_accounting import setup_tracker, frame


def records(store):
    # Exercise the persisted public repository, not tracker internals.
    from app.storage.charging_sessions import SessionHistory
    return SessionHistory(store).all()


def test_history_survives_next_plug_pause_and_restart(tmp_path):
    tracker, store, cfg = setup_tracker(tmp_path)
    from app.domain.measurements import utcnow
    now = utcnow()
    tracker.update(frame(now, 10000), cfg)
    tracker.update(frame(now+timedelta(seconds=30), 12000), cfg)
    pause = frame(now+timedelta(seconds=45), 12000)
    pause = replace(pause, device_states={'ev': replace(pause.device_states['ev'], observed_state='SuspendedEVSE')})
    tracker.update(pause, cfg)
    tracker = ChargingTracker(SQLiteStore(store.path))
    tracker.update(frame(now+timedelta(seconds=60), 13000), cfg)
    tracker.update(frame(now+timedelta(seconds=70), 13000, plugged=False), cfg)
    assert len(records(store)) == 1
    first = records(store)[0]
    assert first['energy_kwh'] == 3
    assert first['active'] is False
    tracker.update(frame(now+timedelta(seconds=90), 13000), cfg)
    assert len(records(store)) == 2
    assert next(s for s in records(store) if s['id']==first['id'])['energy_kwh'] == 3


def test_legacy_migration_is_idempotent_and_preserves_unknown_duration(tmp_path):
    tracker, store, cfg = setup_tracker(tmp_path)
    from app.domain.measurements import utcnow
    now = utcnow()
    tracker.update(frame(now, 10000), cfg)
    tracker.update(frame(now+timedelta(seconds=30), 12000), cfg)
    legacy = store.get('charging_sessions')
    for session in legacy.values():
        session.pop('charge_duration_s', None)
    with store.connection() as db:
        db.execute('DELETE FROM charging_history')
    store.set('charging_sessions', legacy)
    ChargingTracker(store)
    ChargingTracker(store)
    assert len(records(store)) == 1
    assert records(store)[0]['energy_kwh'] == 2
    assert records(store)[0]['charge_duration_s'] is None


def test_terminal_correction_updates_same_row_and_missing_meter_is_unknown(tmp_path):
    tracker, store, cfg = setup_tracker(tmp_path)
    from app.domain.measurements import utcnow
    now = utcnow()
    absent = frame(now, None)
    tracker.update(absent, cfg)
    assert records(store)[0]['energy_kwh'] is None
    tracker.update(frame(now+timedelta(seconds=10), 10000), cfg)
    tracker.update(frame(now+timedelta(seconds=30), 11000, plugged=False), cfg)
    terminal = frame(now+timedelta(seconds=40), 11200, plugged=False)
    terminal = replace(terminal, device_states={'ev': replace(terminal.device_states['ev'], energy_terminal=True)})
    tracker.update(terminal, cfg)
    assert len(records(store)) == 1
    assert records(store)[0]['energy_kwh'] == pytest.approx(1.2)


def test_vehicle_config_change_does_not_split_same_plug_history(tmp_path):
    tracker, store, cfg = setup_tracker(tmp_path)
    from app.domain.measurements import utcnow
    now = utcnow()
    tracker.update(frame(now, 10000), cfg)
    tracker.update(frame(now+timedelta(seconds=30), 11000), cfg)
    cfg.vehicles[0].vin = 'changed'
    tracker.update(frame(now+timedelta(seconds=45), 11500), cfg)
    tracker.update(frame(now+timedelta(seconds=60), 12000), cfg)
    assert len(records(store)) == 1
    assert records(store)[0]['energy_kwh'] == pytest.approx(2)


def test_absent_initial_meter_stays_partial_after_a_later_baseline(tmp_path):
    tracker, store, cfg = setup_tracker(tmp_path)
    from app.domain.measurements import utcnow
    now=utcnow()
    tracker.update(frame(now,None),cfg)
    tracker.update(frame(now+timedelta(seconds=60),12000),cfg)
    end=frame(now+timedelta(seconds=90),13000,plugged=False)
    end=replace(end,device_states={'ev':replace(end.device_states['ev'],energy_terminal=True)})
    tracker.update(end,cfg)
    assert records(store)[0]['energy_kwh']==1
    assert records(store)[0]['energy_partial'] is True
    assert records(store)[0]['cost_partial'] is True


def test_zero_without_final_meter_is_not_a_confirmed_empty_session(tmp_path):
    tracker, store, cfg = setup_tracker(tmp_path)
    from app.domain.measurements import utcnow
    now=utcnow()
    tracker.update(frame(now,10000),cfg)
    end=frame(now+timedelta(seconds=30),None,plugged=False)
    tracker.update(end,cfg)
    assert records(store)[0]['energy_partial'] is True


def test_duration_does_not_count_stale_charging_or_hide_network_gaps(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path)
    from app.domain.measurements import utcnow
    now=utcnow()
    first=frame(now,10000)
    tracker.update(first,cfg)
    for t in range(10,121,10):
        stale=replace(first,at=now+timedelta(seconds=t))
        tracker.update(stale,cfg)
    row=records(store)[0]
    assert row['charge_duration_s']<=cfg.sample_max_age_s
    assert row['duration_partial'] is True
    offline=replace(first,at=now+timedelta(seconds=130),device_states={'ev':replace(first.device_states['ev'],connected=False)})
    tracker.update(offline,cfg)
    assert records(store)[0]['active'] is True
    assert records(store)[0]['duration_partial'] is True


@pytest.mark.parametrize('offset,raw',[(-600,10000),(60,10000),(0,-1)])
def test_invalid_initial_index_does_not_hide_unmeasured_prefix(tmp_path,offset,raw):
    tracker,store,cfg=setup_tracker(tmp_path)
    from app.domain.measurements import utcnow
    now=utcnow();first=frame(now,raw)
    first=replace(first,device_states={'ev':replace(first.device_states['ev'],energy_measured_at=now+timedelta(seconds=offset))})
    tracker.update(first,cfg)
    tracker.update(frame(now+timedelta(seconds=60),12000),cfg)
    final=frame(now+timedelta(seconds=90),13000,plugged=False)
    tracker.update(replace(final,device_states={'ev':replace(final.device_states['ev'],energy_terminal=True)}),cfg)
    assert records(store)[0]['energy_partial'] is True


def test_later_transaction_cannot_clear_original_missing_prefix(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path)
    from app.domain.measurements import utcnow
    now=utcnow()
    tracker.update(frame(now,None),cfg)
    tracker.update(frame(now+timedelta(seconds=60),10000),cfg)
    final=frame(now+timedelta(seconds=120),12000,plugged=False)
    state=replace(final.device_states['ev'],energy_terminal=True,energy_transaction_id=42,
        energy_transaction_start_wh=11000,energy_transaction_started_at=now+timedelta(seconds=90))
    tracker.update(replace(final,device_states={'ev':state}),cfg)
    assert records(store)[0]['energy_partial'] is True
