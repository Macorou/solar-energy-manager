"""A measure missing for a moment keeps what runs, never more; a longer loss stops as before."""
from datetime import timedelta

import pytest

from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Quality, Sample
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine, MEASURE_HOLD_S
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock

CAR = DeviceSpec('ev', 'charger', min_power_w=1380, max_power_w=4002, max_current_a=20, priority=2,
                 grid_phases=('L1',))
TANK = DeviceSpec('tank', 'water_heater', min_power_w=2570, max_power_w=2570, priority=1)
OFFER_W = 17*230
HELD = 'Mesure réseau momentanément indisponible : puissance maintenue'


class Site:
    def __init__(self, car=('Charging', 4000)):
        self.clock = SimulatedClock(); self.engine = EnergyEngine(self.clock); self.car = car
        now = self.clock.now()
        self.policies = {'tank': DevicePolicy('tank', 'off_peak_solar', armed=True, off_peak=True, target=55),
                         'ev': DevicePolicy('ev', 'manual', armed=True, manual_until=now+timedelta(hours=4))}
        if car[0] == 'Charging':
            self.engine.requested['ev'] = self.engine.charger_offered['ev'] = OFFER_W
            self.engine.running_since['ev'] = self.clock.monotonic()
            self.engine.phase_current_seen.add('ev')
        self.engine.requested['tank'] = 2570; self.engine.requested_targets['tank'] = 55
        self.engine.running_since['tank'] = self.clock.monotonic()
        self.clock.advance(120)

    def tick(self, seconds=2, grid=True, home_assistant=True):
        """`grid=False`: the site sensors alone are unavailable; `home_assistant=False`: the whole link is down."""
        self.clock.advance(seconds)
        now = self.clock.now()
        def ha(value, unit='W', ok=True):
            return Sample(value if ok else None, unit, 'HA', now, now,
                          Quality.FRESH if home_assistant else Quality.UNAVAILABLE, checked_at=now)
        status, power = self.car
        car = DeviceState('ev', Sample(power, 'W', 'OCPP', now, now, checked_at=now), status, True,
            vehicle_connected=status != 'Available', transaction_active=status == 'Charging',
            currents={'L1': Sample(17 if power else 0, 'A', 'OCPP', now, now, checked_at=now)})
        tank = DeviceState('tank', ha(2570), 'on', True, temperature=50, target_temperature=55)
        snapshot = SiteSnapshot(now, grid=ha(7070, ok=grid), solar=ha(0), site_limit_w=11000,
            device_states={'tank': tank, 'ev': car}, phase_control_enabled=True, phase_margin_a=1,
            phase_limits_a={'L1': 20}, phase_currents={'L1': ha(19, 'A', ok=grid)})
        return self.engine.evaluate(snapshot, [TANK, CAR], self.policies, {})


def actions(batch):
    return sorted((c.device_id, c.action) for c in batch.commands)


@pytest.mark.parametrize('missing', [{'grid': False}, {'home_assistant': False}])
def test_a_measure_missing_for_a_moment_keeps_the_running_devices(missing):
    site = Site()
    assert site.tick().commands == ()
    batch = site.tick(**missing)
    assert batch.commands == ()
    assert batch.reasons == {'tank': HELD, 'ev': 'Courant réseau momentanément indisponible : puissance maintenue'}
    assert site.tick(MEASURE_HOLD_S-4, **missing).commands == ()
    assert site.tick().commands == ()  # back: nothing was changed meanwhile


@pytest.mark.parametrize('missing', [{'grid': False}, {'home_assistant': False}])
def test_a_longer_loss_stops_the_devices_as_before(missing):
    site = Site()
    site.tick()
    assert site.tick(**missing).commands == ()
    assert actions(site.tick(MEASURE_HOLD_S, **missing)) == [('ev', 'suspend'), ('tank', 'suspend')]


def test_a_measure_never_read_gives_no_hold():
    site = Site()
    assert actions(site.tick(grid=False)) == [('ev', 'suspend'), ('tank', 'suspend')]


def test_nothing_starts_while_a_measure_is_held():
    site = Site(car=('Available', 0))
    assert site.tick().commands == ()
    site.car = ('Preparing', 0)
    batch = site.tick(grid=False)
    assert batch.commands == ()
    assert batch.reasons['ev'] == 'Mesure réseau momentanément indisponible : démarrage différé'
