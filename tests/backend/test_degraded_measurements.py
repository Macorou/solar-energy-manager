"""A late reading keeps a running device at its power for a bounded time, never more."""
from datetime import timedelta
import pytest
from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Sample, Quality
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock

CAR = DeviceSpec('ev', 'charger', min_power_w=1380, max_power_w=3680, grid_phases=('L1',), max_current_a=16)
TANK = DeviceSpec('tank', 'water_heater', min_power_w=2000, max_power_w=2000, priority=2)
MANUAL = {'ev': DevicePolicy('ev', 'manual', armed=True), 'tank': DevicePolicy('tank', 'off', armed=True, target=55)}


def sample(value, unit, now, age=0, quality=Quality.FRESH):
    at = now-timedelta(seconds=age)
    return Sample(value, unit, 'test', at, at, quality, checked_at=at)


def site(now, car_age=0, tank_age=0, site_limit=11000, phase_current=None, tank_quality=Quality.FRESH,
         car_status='Charging', car_w=2530):
    return SiteSnapshot(now, grid=sample(3000, 'W', now), solar=sample(0, 'W', now), site_limit_w=site_limit,
        phase_control_enabled=phase_current is not None, phase_margin_a=1, phase_limits_a={'L1': 20},
        phase_currents={'L1': sample(phase_current, 'A', now)} if phase_current is not None else {},
        device_states={
            'ev': DeviceState('ev', sample(car_w, 'W', now, car_age), car_status, True, vehicle_connected=True,
                              currents={'L1': sample(car_w/230, 'A', now, car_age)}),
            'tank': DeviceState('tank', sample(0, 'W', now, tank_age, tank_quality), 'off', True,
                                temperature=50, target_temperature=55, measured_at=now)})


def charging_engine():
    clock = SimulatedClock()
    engine = EnergyEngine(clock)
    engine.requested['ev'] = engine.charger_offered['ev'] = 11*230
    engine.running_since['ev'] = clock.monotonic()
    engine.phase_current_seen.add('ev')  # an established charge, past its start-up wait
    clock.advance(60)
    return clock, engine


def test_a_late_heater_reading_no_longer_stops_a_manual_car_charge():
    clock, engine = charging_engine()
    batch = engine.evaluate(site(clock.now(), tank_age=40), [CAR, TANK], MANUAL, {})
    assert batch.commands == ()
    assert batch.reasons['ev'] == 'Mesure électrique en retard : puissance maintenue'


@pytest.mark.parametrize('age,quality', [(100, Quality.FRESH), (5, Quality.UNAVAILABLE)])
def test_a_long_delay_or_an_unavailable_reading_still_stops_the_charge(age, quality):
    clock, engine = charging_engine()
    batch = engine.evaluate(site(clock.now(), tank_age=age, tank_quality=quality), [CAR, TANK], MANUAL, {})
    assert [c.action for c in batch.commands] == ['suspend']


def test_a_late_reading_never_starts_or_raises_a_device():
    clock = SimulatedClock(); engine = EnergyEngine(clock)
    plugged = site(clock.now(), tank_age=40, car_status='Preparing', car_w=0)
    batch = engine.evaluate(plugged, [CAR, TANK], MANUAL, {})
    assert batch.commands == ()
    assert batch.reasons['ev'] == 'Mesure électrique en retard : démarrage différé'


def test_a_late_device_counts_at_its_maximum_against_the_site_limit():
    clock, engine = charging_engine()
    # 4500 W - (3000 W grid - 2530 W car) - 2000 W heater assumed at maximum = 2030 W for the car: 8 A.
    batch = engine.evaluate(site(clock.now(), tank_age=40, site_limit=4500), [CAR, TANK], MANUAL, {})
    assert batch.commands[0].action == 'set_power'
    assert batch.commands[0].limit_w == pytest.approx(8*230)


def test_a_late_own_current_keeps_the_offer_while_the_phase_has_room():
    clock, engine = charging_engine()
    batch = engine.evaluate(site(clock.now(), car_age=40, phase_current=13), [CAR, TANK], MANUAL, {})
    assert batch.commands == ()
    assert batch.reasons['ev'] == 'Courant de recharge en retard : puissance maintenue'


@pytest.mark.parametrize('age,phase_current', [(40, 19.5), (100, 13)])
def test_a_late_own_current_still_stops_on_overload_or_after_the_grace(age, phase_current):
    clock, engine = charging_engine()
    batch = engine.evaluate(site(clock.now(), car_age=age, phase_current=phase_current), [CAR, TANK], MANUAL, {})
    assert [c.action for c in batch.commands] == ['suspend']
