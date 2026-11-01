"""Solar modulation must not chase noise, while limit reductions stay immediate."""
import pytest
from app.domain.commands import CommandIntent
from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Sample
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.phase_limits import phase_power_limit
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock

SPEC = DeviceSpec('ev', 'charger', min_power_w=1380, max_power_w=3680, grid_phases=('L1',), max_current_a=16)


def charging(now, grid, phase_current=None, limit=45):
    s = lambda value, unit='W': Sample(value, unit, 'test', now, now, checked_at=now)
    return SiteSnapshot(now, grid=s(grid), solar=s(3000), site_limit_w=11000, export_margin_w=100,
        phase_control_enabled=phase_current is not None, phase_margin_a=1,
        phase_currents={'L1': s(phase_current, 'A')} if phase_current is not None else {},
        phase_limits_a={'L1': limit},
        device_states={'ev': DeviceState('ev', s(2530), 'Charging', True, vehicle_connected=True,
                                         currents={'L1': s(11, 'A')})})


def engine_at_11a():
    clock = SimulatedClock()
    engine = EnergyEngine(clock)
    engine.requested['ev'] = engine.charger_offered['ev'] = 11*230
    engine.running_since['ev'] = clock.monotonic()
    return clock, engine


def test_rounding_to_a_tenth_of_an_ampere_is_not_reported_as_a_phase_limit():
    now = SimulatedClock().now()
    s = lambda value, unit='A': Sample(value, unit, 'test', now, now, checked_at=now)
    snapshot = SiteSnapshot(now, phase_control_enabled=True, phase_currents={'L1': s(2)}, phase_limits_a={'L1': 45},
        device_states={'ev': DeviceState('ev', s(2300, 'W'), 'Charging', True, currents={'L1': s(10)})})
    assert phase_power_limit(snapshot, SPEC, 2345.6, {}, 2300) == (2323.0, None)
    tight = SiteSnapshot(now, phase_control_enabled=True, phase_currents={'L1': s(19.5)}, phase_limits_a={'L1': 20},
        device_states=snapshot.device_states)
    assert phase_power_limit(tight, SPEC, 2345.6, {}, 2300)[1] == 'Limite de courant sur la phase réseau'


def test_solar_noise_below_the_deadband_sends_no_command_but_a_real_drop_does():
    clock, engine = engine_at_11a()
    policy = {'ev': DevicePolicy('ev', 'solar', armed=True)}
    # About +0.2 A of extra surplus: within the deadband.
    assert engine.evaluate(charging(clock.now(), -146), [SPEC], policy, {}).commands == ()
    clock.advance(2)
    # About -2 A: a real change, sent at once.
    commands = engine.evaluate(charging(clock.now(), 360), [SPEC], policy, {}).commands
    assert len(commands) == 1 and commands[0].limit_w == pytest.approx(9*230, abs=30)


def test_non_limit_adjustments_wait_for_the_pacing_interval():
    clock, engine = engine_at_11a()
    policy = {'ev': DevicePolicy('ev', 'solar', armed=True)}
    engine.charger_last_control['ev'] = clock.monotonic()
    clock.advance(2)
    assert engine.evaluate(charging(clock.now(), 360), [SPEC], policy, {}).commands == ()
    clock.advance(14)
    assert len(engine.evaluate(charging(clock.now(), 360), [SPEC], policy, {}).commands) == 1


def test_a_phase_limit_reduction_is_never_delayed_by_the_deadband_or_pacing():
    clock, engine = engine_at_11a()
    engine.charger_last_control['ev'] = clock.monotonic()
    clock.advance(2)
    manual = {'ev': DevicePolicy('ev', 'manual', armed=True)}
    # 11 A + (20 A - 1 A margin) - 19.3 A measured: 10.7 A allowed, only 0.3 A below the offer.
    commands = engine.evaluate(charging(clock.now(), 1000, phase_current=19.3, limit=20), [SPEC], manual, {}).commands
    assert len(commands) == 1 and commands[0].limit_w == pytest.approx(10.7*230)


TANK = DeviceSpec('tank', 'water_heater', min_power_w=1000, max_power_w=1000, priority=2)
SHARED = {'ev': DevicePolicy('ev', 'solar', armed=True),
          'tank': DevicePolicy('tank', 'solar', armed=True, target=55, start_delay_s=0)}


def car_and_tank(now, status='SuspendedEV', car_w=0, grid=-2550):
    s = lambda value, unit='W': Sample(value, unit, 'test', now, now, checked_at=now)
    return SiteSnapshot(now, grid=s(grid), solar=s(3000), site_limit_w=11000, export_margin_w=100,
        device_states={'ev': DeviceState('ev', s(car_w), status, True, vehicle_connected=True,
                                         currents={'L1': s(car_w/230, 'A')}),
                       'tank': DeviceState('tank', s(0), 'off', True, temperature=45, target_temperature=45,
                                           measured_at=now)})


def test_a_declining_car_keeps_its_offer_and_releases_the_solar_surplus():
    clock, engine = engine_at_11a()
    sent = {'ev': [], 'tank': []}
    for second in range(0, 132, 2):
        batch = engine.evaluate(car_and_tank(clock.now()), [SPEC, TANK], SHARED, {})
        for command in batch.commands:
            sent[command.device_id].append((second, command.action))
        clock.advance(2)
    # The car's offer holds the surplus until it has declined it for two minutes...
    assert sent['tank'] and all(second >= 120 for second, _ in sent['tank'])
    # ...then it is neither modulated nor suspended, and the heater may start.
    assert not any(second >= 120 for second, _ in sent['ev'])
    assert sent['tank'][0][1] == 'set_power'
    assert batch.reasons['ev'] == 'La voiture ne demande pas de charge : offre maintenue'
    assert engine.requested['ev'] == 11*230


def test_a_car_that_resumes_charging_is_regulated_again_at_once():
    clock, engine = engine_at_11a()
    for _ in range(62):
        engine.evaluate(car_and_tank(clock.now()), [SPEC, TANK], SHARED, {})
        clock.advance(2)
    assert 'ev' in engine.declined_chargers(car_and_tank(clock.now()), [SPEC, TANK], clock.monotonic())
    charging = car_and_tank(clock.now(), 'Charging', 2530, grid=-20)
    batch = engine.evaluate(charging, [SPEC, TANK], SHARED, {})
    assert batch.reasons['ev'] != 'La voiture ne demande pas de charge : offre maintenue'
    assert 'ev' not in engine.declined_chargers(charging, [SPEC, TANK], clock.monotonic())


def test_an_accepted_offer_becomes_the_pv_reference_at_once():
    _, engine = engine_at_11a()
    engine.charger_pv_frame['ev'] = (0, 9*230)
    engine.command_result(CommandIntent('id', 'ev', 'set_power', 11.4*230), True)
    assert 'ev' not in engine.charger_pv_frame and engine.charger_offered['ev'] == 11.4*230
