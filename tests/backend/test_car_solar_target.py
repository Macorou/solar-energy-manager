"""Above its target the car may still take solar surplus, never grid power, up to its solar target."""
import pytest
from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Quality, Sample
from app.domain.schedules import ChargeAuthorization
from app.domain.site import SiteSnapshot
from app.domain.vehicles import VehicleTelemetry
from app.engine.engine import EnergyEngine, charger_goals
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock

CAR = DeviceSpec('ev', 'charger', min_power_w=1380, max_power_w=3680, grid_phases=('L1',), max_current_a=16)
GRID_WINDOW = {'ev': ChargeAuthorization('car', True, True, 80, None, 'Complément autorisé par le planning')}


def site(now, soc, grid=500, solar=0):
    s = lambda value: Sample(value, 'W', 'test', now, now, checked_at=now)
    car = VehicleTelemetry(soc, measured_at=now, received_at=now, quality=Quality.FRESH)
    return SiteSnapshot(now, grid=s(grid), solar=s(solar), site_limit_w=9000,
        device_states={'ev': DeviceState('ev', s(0), 'Preparing', True, vehicle_connected=True)},
        vehicle_telemetry={'car': car})


def planned(solar_target, mode='planned'):
    return {'ev': DevicePolicy('ev', mode, armed=True, vehicle_id='car', target=80, solar_target=solar_target)}


def test_above_the_target_a_grid_window_only_takes_surplus():
    clock = SimulatedClock()
    night = EnergyEngine(clock).evaluate(site(clock.now(), 90), [CAR], planned(100), GRID_WINDOW)
    assert night.commands == ()
    engine = EnergyEngine(clock)
    for _ in range(3):  # a solar start waits for a stable surplus
        day = engine.evaluate(site(clock.now(), 90, grid=-3000, solar=3500), [CAR], planned(100), GRID_WINDOW)
        clock.advance(30)
    assert [c.action for c in day.commands] == ['set_power']
    assert day.commands[0].limit_w <= 3000
    assert day.reasons['ev'] == 'Surplus solaire au-delà de l’objectif, jusqu’à 100 %'


def test_below_the_target_the_grid_window_is_unchanged():
    clock = SimulatedClock()
    batch = EnergyEngine(clock).evaluate(site(clock.now(), 60), [CAR], planned(100), GRID_WINDOW)
    assert [c.action for c in batch.commands] == ['set_power']
    assert batch.commands[0].limit_w == 3680


def test_the_solar_target_ends_the_charge():
    clock = SimulatedClock()
    sunny = site(clock.now(), 92, grid=-3000, solar=3500)
    assert EnergyEngine(clock).evaluate(sunny, [CAR], planned(90), GRID_WINDOW).reasons['ev'] == 'Objectif atteint'
    # Without a solar target the charge still ends at the target.
    assert EnergyEngine(clock).evaluate(sunny, [CAR], planned(None), GRID_WINDOW).reasons['ev'] == 'Objectif atteint'


def test_manual_mode_ignores_the_solar_target():
    clock = SimulatedClock()
    manual = planned(100, mode='manual')
    batch = EnergyEngine(clock).evaluate(site(clock.now(), 85, grid=-3000, solar=3500), [CAR], manual, {})
    assert batch.commands == () and batch.reasons['ev'] == 'Objectif atteint'
    assert charger_goals(manual['ev'], GRID_WINDOW['ev']) == (80, 80)
    assert charger_goals(planned(100)['ev'], GRID_WINDOW['ev']) == (80, 100)
    assert charger_goals(planned(50)['ev'], GRID_WINDOW['ev']) == (80, 80)


def test_a_night_charge_crossing_the_target_stops_without_surplus():
    clock = SimulatedClock()
    engine = EnergyEngine(clock)
    engine.requested['ev'] = engine.charger_offered['ev'] = 3680
    engine.running_since['ev'] = clock.monotonic()
    engine.network_allowed['ev'] = True
    now = clock.now()
    s = lambda value: Sample(value, 'W', 'test', now, now, checked_at=now)
    charging = site(now, 81, grid=3800)
    charging = SiteSnapshot(**{**charging.__dict__, 'device_states': {'ev': DeviceState('ev', s(3680), 'Charging', True,
        vehicle_connected=True)}})
    batch = engine.evaluate(charging, [CAR], planned(100), GRID_WINDOW)
    assert [c.action for c in batch.commands] == ['suspend']


@pytest.mark.asyncio
@pytest.mark.parametrize('solar_target,reached', [(100, False), (None, True)])
async def test_the_coordinator_reports_the_target_reached_at_the_solar_target(tmp_path, solar_target, reached):
    from datetime import timedelta
    from app.runtime.coordinator import Coordinator
    from app.settings import SettingsDocument
    from app.storage.database import SQLiteStore
    store = SQLiteStore(tmp_path/'db')
    store.save_settings(SettingsDocument(vehicles=[{'id': 'car', 'capacity_kwh': 34}],
        devices=[{'id': 'ev', 'name': 'EV', 'kind': 'charger', 'vehicle_id': 'car', 'mode': 'solar',
                  'solar_target': solar_target}]).model_dump(mode='json'))
    runtime = Coordinator(store)
    clock = SimulatedClock()
    for seconds, energy in [(0, 10000), (30, 10000)]:
        now = clock.now()+timedelta(seconds=seconds)
        s = lambda value: Sample(value, 'W', 'test', now, now, checked_at=now)
        frame = SiteSnapshot(now, grid=s(500), solar=s(0), site_limit_w=9000,
            device_states={'ev': DeviceState('ev', s(0), 'SuspendedEV', True, vehicle_connected=True,
                                             energy_wh=energy, energy_measured_at=now)},
            vehicle_telemetry={'car': VehicleTelemetry(90, measured_at=now, received_at=now, quality=Quality.FRESH)})
        await runtime.tick(frame)
    assert runtime.snapshot.device_states['ev'].target_reached is reached
