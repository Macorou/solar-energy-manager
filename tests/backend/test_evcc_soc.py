"""EVCC MIT estimator vectors (9404d82/core/soc/estimator_test.go) and SEM integration."""
from dataclasses import replace
from datetime import timedelta

import pytest


def test_original_evcc_estimation_vectors_and_energy_resets():
    from app.engine.evcc_soc import SocEstimator
    estimator = SocEstimator(8.5)
    vectors = [
        (0, 0., 0., 10000), (0, 20., 20., 10000),
        (123, 20., 21.23, 10000), (1000, 20., 30., 10000),
        (1100, 31., 31., 10000), (1200, 32., 32., 10000),
        (1900, 39., 39., 10000), (2000, 40., 40., 10000),
        (6000, 80., 80., 10000), (0, 25., 25., 10000),
        (2500, 25., 50., 10000), (0, 50., 50., 10000),
        (4990, 50., 99.9, 10000), (5000, 50., 100., 10000),
        (5001, 50., 100., 10000), (0, 20., 20., 10000),
        (1000, 30., 30., 10000), (1000, 50., 50., 8500),
    ]
    for energy, fetched, expected, capacity in vectors:
        assert estimator.soc(fetched, energy) == pytest.approx(expected)
        assert estimator.virtual_capacity == pytest.approx(capacity)


def test_original_evcc_missing_and_zero_soc_vectors():
    from app.engine.evcc_soc import SocEstimator
    estimator = SocEstimator(8.5)
    for fetched, energy, expected in [
        (None,100,0), (20,0,20), (20,100,21), (None,200,22),
        (20,200,22), (None,50,22), (25,400,25), (None,50,25), (None,500,26),
    ]:
        assert estimator.soc(fetched,energy) == pytest.approx(expected)
    zero=SocEstimator(8.5)
    assert zero.soc(0,5000)==0
    assert zero.soc(None,5100)==1


def test_evcc_state_round_trip_does_not_recount_energy():
    from app.engine.evcc_soc import SocEstimator
    estimator=SocEstimator(50)
    assert estimator.soc(60,0)==60
    assert estimator.soc(60,5000)==pytest.approx(68.5)
    restored=SocEstimator.restore(50,estimator.dump())
    assert restored.soc(60,5000)==pytest.approx(68.5)
    assert restored.soc(66,5000)==66
    assert restored.soc(66,6000)==pytest.approx(67.7)


@pytest.mark.parametrize('date_kind',['absent','past','future','reversed','same_new_date'])
def test_tracker_uses_evcc_percentages_not_peugeot_dates(tmp_path,date_kind):
    from test_charging_accounting import setup_tracker,frame
    from app.domain.measurements import utcnow
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow()
    cfg.vehicles[0].capacity_kwh=50
    def sample(seconds,energy,soc):
        data=frame(now+timedelta(seconds=seconds),energy,soc=soc,stamp=now)
        stamp={'absent':None,'past':now-timedelta(days=7),'future':now+timedelta(days=7),
               'reversed':now-timedelta(seconds=seconds),'same_new_date':now+timedelta(seconds=seconds)}[date_kind]
        return replace(data,vehicle_telemetry={'car':replace(data.vehicle_telemetry['car'],measured_at=stamp)})
    tracker.update(sample(0,10000,60),cfg)
    tracker.update(sample(30,15000,60),cfg)
    assert tracker.summary('ev')['soc']==pytest.approx(68.5)
    tracker.update(sample(60,15000,66),cfg)
    assert tracker.summary('ev')['soc']==66
    tracker.update(sample(90,16000,66),cfg)
    assert tracker.summary('ev')['soc']==pytest.approx(67.7)
    from app.runtime.charging import ChargingTracker
    restored=ChargingTracker(store)
    restored.update(sample(90,16000,66),cfg)
    assert restored.summary('ev')['soc']==pytest.approx(67.7)


def test_missing_peugeot_timestamp_keeps_valid_soc():
    from app.connectors.peugeot.telemetry import parse_telemetry
    assert parse_telemetry({'energy':[{'type':'Electric','level':60}]}).soc==60


@pytest.mark.parametrize('capacity',[None,50])
def test_api_failure_requires_capacity_to_advance_cached_percentage(tmp_path,capacity):
    from test_charging_accounting import setup_tracker,frame
    from app.domain.measurements import utcnow,Quality
    tracker,_,cfg=setup_tracker(tmp_path);cfg.vehicles[0].capacity_kwh=capacity;now=utcnow()
    tracker.update(frame(now,10000,soc=60,stamp=now),cfg)
    failed=frame(now+timedelta(seconds=30),10500,soc=60,stamp=now)
    failed=replace(failed,vehicle_telemetry={'car':replace(failed.vehicle_telemetry['car'],quality=Quality.UNAVAILABLE)})
    tracker.update(failed,cfg)
    assert tracker.summary('ev')['soc']==pytest.approx(60 if capacity is None else 60.85)
    assert tracker.summary('ev')['soc_usable'] is (capacity is not None)
    if capacity is None:assert 'capacité' in tracker.summary('ev')['soc_reason']
    else:assert tracker.summary('ev')['soc_reason'] is None


def test_evcc_goal_releases_on_changed_percentage_without_date_hysteresis(tmp_path):
    from test_charging_accounting import setup_tracker,frame
    from app.domain.measurements import utcnow
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow()
    tracker.update(frame(now,10000,soc=80,stamp=now),cfg)
    assert tracker.target_reached('ev',80)
    tracker.update(frame(now+timedelta(seconds=30),10000,soc=79.5,stamp=now-timedelta(days=1)),cfg)
    assert not tracker.target_reached('ev',80)


def test_upgrade_preserves_known_legacy_energy_basis_without_reading_peugeot_date(tmp_path):
    from test_charging_accounting import setup_tracker,frame
    from app.domain.measurements import utcnow
    from app.runtime.charging import ChargingTracker
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow()
    tracker.update(frame(now,10000),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000),cfg)
    legacy=tracker.sessions['ev'];legacy.pop('evcc_soc')
    legacy['anchor']={'source':'vehicle','soc':75,'energy':0,'at':None}
    store.set('charging_sessions',tracker.sessions)
    tracker=ChargingTracker(store)
    tracker.update(frame(now+timedelta(seconds=60),12000),cfg)
    assert tracker.summary('ev')['soc']==pytest.approx(80)
