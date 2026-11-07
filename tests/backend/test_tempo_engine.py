"""Tempo red day, peak hours: automatic modes use surplus only, Manual stays exempt."""
import pytest
from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Sample
from app.domain.schedules import ChargeAuthorization
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock

RED = 'Jour rouge, heures pleines : solaire seul'
CAR = DeviceSpec('ev', 'charger', min_power_w=1380, max_power_w=3680, grid_phases=('L1',), max_current_a=16)
TANK = DeviceSpec('tank', 'water_heater', min_power_w=2000, max_power_w=2000)
GRID = {'ev': ChargeAuthorization('car', allow_grid=True, allow_solar=True, target_soc=80, reason='Créneau réseau')}


def blocked(mode, **kw):
    return DevicePolicy(kw.pop('device', 'ev'), mode, armed=True, start_delay_s=0, grid_blocked=True,
                        import_tolerance_w=0, stop_delay_s=0, **kw)


def site(now, grid=500, ev=0, state='Preparing', fallback=0, device='ev'):
    s = lambda value: Sample(value, 'W', 'test', now, now, checked_at=now)
    return SiteSnapshot(now, grid=s(grid) if grid is not None else None, solar=s(max(0, -(grid or 0)) + ev),
        site_limit_w=9000, export_margin_w=0, grid_fallback_current_a=fallback,
        device_states={device: DeviceState(device, s(ev), state, True, vehicle_connected=True)})


def test_grid_blocked_planned_charge_uses_surplus_only():
    clock = SimulatedClock()
    policies = {'ev': blocked('planned', vehicle_id='car')}
    # The same window without the block charges from the grid.
    free = {'ev': DevicePolicy('ev', 'planned', armed=True, vehicle_id='car')}
    assert EnergyEngine(clock).evaluate(site(clock.now()), [CAR], free, GRID).commands[0].action == 'set_power'
    batch = EnergyEngine(clock).evaluate(site(clock.now()), [CAR], policies, GRID)
    assert batch.commands == () and batch.reasons['ev'] == RED
    engine = EnergyEngine(clock)
    for _ in range(3):
        batch = engine.evaluate(site(clock.now(), grid=-2000), [CAR], policies, GRID)
        if batch.commands: break
        clock.advance(30)
    assert [c.action for c in batch.commands] == ['set_power'] and 1380 <= batch.commands[0].limit_w <= 2000


def test_grid_blocked_off_peak_heater_does_not_heat_from_grid():
    clock = SimulatedClock()
    free = {'tank': DevicePolicy('tank', 'off_peak_solar', armed=True, off_peak=True, start_delay_s=0)}
    assert EnergyEngine(clock).evaluate(site(clock.now(), device='tank'), [TANK], free, {}).commands[0].limit_w == 2000
    policies = {'tank': blocked('off_peak_solar', device='tank', off_peak=True)}
    batch = EnergyEngine(clock).evaluate(site(clock.now(), device='tank'), [TANK], policies, {})
    assert not any(c.limit_w for c in batch.commands) and batch.reasons['tank'] == RED


@pytest.mark.parametrize('min_run', [0, 300])
def test_red_peak_has_no_cloud_tolerance(min_run):
    # Neither the cloud tolerance nor the minimum run time may keep the car on the grid.
    clock = SimulatedClock()
    policies = {'ev': blocked('solar', vehicle_id='car', min_run_s=min_run)}
    engine = EnergyEngine(clock)
    for _ in range(3):
        batch = engine.evaluate(site(clock.now(), grid=-3000), [CAR], policies, {})
        if batch.commands: break
        clock.advance(30)
    started = batch.commands[0].limit_w
    engine.command_result(batch.commands[0], True, clock.now())
    clock.advance(20)
    batch = engine.evaluate(site(clock.now(), grid=300, ev=started, state='Charging'), [CAR], policies, {})
    # Reduced but still importing (e.g. held at the minimum) fails: the 300 W import must be gone.
    assert batch.commands and (batch.commands[0].action == 'suspend' or batch.commands[0].limit_w <= started-300)


@pytest.mark.parametrize('min_run', [0, 300])
def test_red_peak_heater_stops_at_once_on_deficit(min_run):
    clock = SimulatedClock()
    policies = {'tank': blocked('solar', device='tank', min_run_s=min_run)}
    engine = EnergyEngine(clock)
    batch = engine.evaluate(site(clock.now(), grid=-2500, device='tank', state='off'), [TANK], policies, {})
    assert [(c.action, c.limit_w) for c in batch.commands] == [('set_power', 2000)]
    clock.advance(10)
    batch = engine.evaluate(site(clock.now(), grid=300, ev=2000, state='on', device='tank'), [TANK], policies, {})
    assert [c.action for c in batch.commands] == ['suspend']


def test_manual_is_exempt_from_grid_block():
    clock = SimulatedClock()
    policies = {'ev': blocked('manual', vehicle_id='car')}
    batch = EnergyEngine(clock).evaluate(site(clock.now()), [CAR], policies, {})
    assert [c.action for c in batch.commands] == ['set_power'] and batch.commands[0].limit_w > 1380


def test_grid_block_disables_fallback_current():
    clock = SimulatedClock()
    free = {'ev': DevicePolicy('ev', 'planned', armed=True, vehicle_id='car')}
    assert EnergyEngine(clock).evaluate(site(clock.now(), grid=None, fallback=16), [CAR], free, GRID).commands
    policies = {'ev': blocked('planned', vehicle_id='car')}
    assert EnergyEngine(clock).evaluate(site(clock.now(), grid=None, fallback=16), [CAR], policies, GRID).commands == ()


def test_block_at_peak_start_stops_a_running_grid_charge():
    clock = SimulatedClock()
    engine = EnergyEngine(clock)
    free = {'ev': DevicePolicy('ev', 'planned', armed=True, vehicle_id='car')}
    batch = engine.evaluate(site(clock.now()), [CAR], free, GRID)
    engine.command_result(batch.commands[0], True, clock.now())
    clock.advance(30)
    batch = engine.evaluate(site(clock.now(), ev=3680, state='Charging'), [CAR], {'ev': blocked('planned', vehicle_id='car')}, GRID)
    assert [c.action for c in batch.commands] == ['suspend']
