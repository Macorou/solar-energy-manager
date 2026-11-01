"""A grid window keeps charging without SOC, uses the opt-in fallback without HA, warns if too short."""
from datetime import timedelta
from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Sample
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock

CAR = DeviceSpec('ev', 'charger', min_power_w=1380, max_power_w=3680, grid_phases=('L1',), max_current_a=16)
MANUAL = {'ev': DevicePolicy('ev', 'manual', armed=True, vehicle_id='car')}


def plugged(now, grid=True, fallback=0):
    s = lambda value: Sample(value, 'W', 'test', now, now, checked_at=now)
    return SiteSnapshot(now, grid=s(500) if grid else None, solar=s(0), site_limit_w=9000,
        grid_fallback_current_a=fallback,
        device_states={'ev': DeviceState('ev', s(0), 'Preparing', True, vehicle_connected=True)})


def test_a_grid_window_keeps_charging_without_a_known_soc():
    clock = SimulatedClock()
    batch = EnergyEngine(clock).evaluate(plugged(clock.now()), [CAR], MANUAL, {})
    assert [c.action for c in batch.commands] == ['set_power']
    assert batch.reasons['ev'] == 'Batterie inconnue : charge poursuivie jusqu’à l’arrêt par la voiture'
    solar = {'ev': DevicePolicy('ev', 'solar', armed=True, vehicle_id='car')}
    assert EnergyEngine(clock).evaluate(plugged(clock.now()), [CAR], solar, {}).commands == ()


def test_an_unverifiable_estimate_still_ends_the_charge_at_the_target():
    from app.domain.vehicles import VehicleTelemetry
    from app.domain.measurements import Quality
    clock = SimulatedClock()
    def last_estimate(soc):
        # The session estimate is known but no longer usable (e.g. stale energy index).
        car = VehicleTelemetry(soc, measured_at=clock.now(), received_at=clock.now(), quality=Quality.UNAVAILABLE,
                               unavailable_reason='Index d’énergie de la borne trop ancien')
        snapshot = plugged(clock.now())
        return SiteSnapshot(**{**snapshot.__dict__, 'vehicle_telemetry': {'car': car}})
    below = EnergyEngine(clock).evaluate(last_estimate(64), [CAR], MANUAL, {})
    assert [c.action for c in below.commands] == ['set_power']
    assert below.reasons['ev'].endswith('(dernière estimation 64 %)')
    reached = EnergyEngine(clock).evaluate(last_estimate(81), [CAR], MANUAL, {})
    assert reached.commands == () and reached.reasons['ev'] == 'Objectif atteint (dernière estimation)'


def test_fallback_current_is_opt_in_when_the_grid_meter_is_missing():
    clock = SimulatedClock()
    assert EnergyEngine(clock).evaluate(plugged(clock.now(), grid=False), [CAR], MANUAL, {}).commands == ()
    batch = EnergyEngine(clock).evaluate(plugged(clock.now(), grid=False, fallback=16), [CAR], MANUAL, {})
    assert batch.commands[0].limit_w == 16*230


def test_a_too_short_window_is_reported_without_changing_the_plan():
    from app.runtime.coordinator import plan_warnings
    from app.scheduling.recurrence import occurrences_for
    from app.domain.vehicles import VehicleTelemetry
    from app.domain.measurements import Quality, utcnow
    from app.settings import SettingsDocument
    cfg = SettingsDocument(vehicles=[{'id': 'car', 'capacity_kwh': 46}],
        devices=[{'id': 'ev', 'name': 'EV', 'kind': 'charger', 'vehicle_id': 'car', 'mode': 'planned',
                  'max_power_w': 3680, 'max_current_a': 16}],
        schedules=[{'id': 'p', 'vehicle_id': 'car', 'weekdays': list(range(7)), 'earliest_start': '22:00',
                    'deadline': '05:45', 'target_soc': 80}])
    now = utcnow()
    occurrences = occurrences_for(cfg.schedules[0], now, now+timedelta(days=2), cfg.timezone)
    def at(soc):
        car = VehicleTelemetry(soc, measured_at=now, received_at=now, quality=Quality.FRESH)
        return plan_warnings(SiteSnapshot(now, vehicle_telemetry={'car': car}), cfg, occurrences)
    assert 'probablement non atteint à 05:45' in at(20)['ev']
    assert at(70) == {}
