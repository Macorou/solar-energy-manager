"""A device's own measure is ahead of the site meter for a few seconds after it changes.

2026-11-10 23:12: the station announced SuspendedEVSE (0 W) while the Home Assistant
meters still contained the car. The car was counted twice (its old draw inside the site
meter, plus its offer) and the running heater was stopped for lack of room.
"""
from dataclasses import replace
from datetime import timedelta

from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Quality, Sample
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.engine.settling import SETTLING_MAX_S
from app.simulation.clock import SimulatedClock

CAR = DeviceSpec('ev', 'charger', min_power_w=1380, max_power_w=4002, max_current_a=20, priority=2)
TANK = DeviceSpec('tank', 'water_heater', min_power_w=2570, max_power_w=2570, priority=1)
OFFER_W = 17.4*230  # 4002 W


class Night:
    """Off-peak hours: house 500 W, heater 2570 W, car 17.4 A on L1 (phase limit 20 A)."""

    def __init__(self, phases=False):
        self.clock = SimulatedClock(); self.engine = EnergyEngine(self.clock); self.phases = phases
        self.specs = [TANK, replace(CAR, grid_phases=('L1',)) if phases else CAR]
        now = self.clock.now()
        self.policies = {'tank': DevicePolicy('tank', 'off_peak_solar', armed=True, off_peak=True, target=55),
                         'ev': DevicePolicy('ev', 'manual', armed=True, manual_until=now+timedelta(hours=4))}
        self.engine.requested = {'tank': 2570, 'ev': OFFER_W}
        self.engine.requested_targets['tank'] = 55
        self.engine.charger_offered['ev'] = OFFER_W
        self.engine.running_since = {'ev': self.clock.monotonic(), 'tank': self.clock.monotonic()}
        self.engine.phase_current_seen.add('ev')
        self.clock.advance(120)
        self.engine.charger_last_control['ev'] = self.clock.monotonic()
        self.meters_at = self.car_at = self.clock.now()
        self.grid_w, self.phase_a, self.tank_w, self.car = 7070, 19, 2570, ('Charging', 4000)
        self.limit_w = 11000

    def read_meters(self, grid_w, phase_a):
        """Home Assistant delivers a new site reading."""
        self.grid_w, self.phase_a, self.meters_at = grid_w, phase_a, self.clock.now()

    def station_says(self, status, power_w):
        self.car, self.car_at = (status, power_w), self.clock.now()

    def tick(self, seconds=2):
        self.clock.advance(seconds)
        now = self.clock.now()
        ha = lambda value, unit='W': Sample(value, unit, 'HA', self.meters_at, now, checked_at=now)
        status, power = self.car
        charging = status == 'Charging'
        car = DeviceState('ev', Sample(power, 'W', 'OCPP', now if charging else self.car_at, now,
                                       Quality.FRESH if charging else Quality.ESTIMATED, checked_at=now),
            status, True, vehicle_connected=True, transaction_active=True, status_measured_at=self.car_at,
            # The last current sent by the station dates from before its pause.
            currents={'L1': Sample(17.4, 'A', 'OCPP', now if charging else self.car_at-timedelta(seconds=1),
                                   now, checked_at=now)})
        tank = DeviceState('tank', Sample(self.tank_w, 'W', 'HA', now, now, checked_at=now), 'on', True,
                           temperature=50, target_temperature=55)
        snapshot = SiteSnapshot(now, grid=ha(self.grid_w), solar=ha(0), site_limit_w=self.limit_w,
            device_states={'tank': tank, 'ev': car}, phase_control_enabled=self.phases, phase_margin_a=1,
            phase_limits_a={'L1': 20}, phase_currents={'L1': ha(self.phase_a, 'A')} if self.phases else {})
        return self.engine.evaluate(snapshot, self.specs, self.policies, {})

    def pause_seen_before_the_meters(self):
        """The meters are read, then the station announces its pause, between two evaluations."""
        self.clock.advance(1)
        self.read_meters(self.grid_w, self.phase_a)
        self.station_says('SuspendedEVSE', 0)
        return self.tick(1)


def actions(batch):
    return sorted((c.device_id, c.action) for c in batch.commands)


def test_running_heater_survives_a_car_pause_seen_before_the_site_meter_is_read_again():
    night = Night()
    assert night.tick().commands == ()
    batch = night.pause_seen_before_the_meters()  # the site meter still shows 7070 W, car included
    assert batch.commands == ()
    assert batch.reasons['tank'] == 'Chauffe heures creuses'
    night.read_meters(3070, 1.6)
    assert night.tick().commands == ()


def test_paused_car_keeps_its_offer_while_the_phase_meter_still_contains_its_current():
    night = Night(phases=True)
    assert night.tick().commands == ()
    batch = night.pause_seen_before_the_meters()  # L1 still shows 19 A, the car's 17.4 A included
    assert batch.commands == ()
    assert batch.reasons['ev'] == 'Commande manuelle'
    night.read_meters(3070, 1.6)
    assert night.tick().commands == ()


def test_a_real_phase_overload_still_reduces_the_offer_during_mixed_frames():
    night = Night(phases=True)
    assert night.tick().commands == ()
    night.grid_w, night.phase_a = 7990, 23  # 4 A more in the house: L1 is over its limit
    batch = night.pause_seen_before_the_meters()
    assert actions(batch) == [('ev', 'set_power')]
    assert batch.commands[0].limit_w < OFFER_W


def test_heater_stopped_by_its_thermostat_is_not_counted_twice_either():
    night = Night()
    night.limit_w = 7200  # 128 W of room left
    assert night.tick().commands == ()
    night.tank_w = 0  # its Home Assistant meter is read after the site meter
    assert night.tick().commands == ()
    night.read_meters(4500, 19)
    assert night.tick().commands == ()


def test_mixed_frames_are_bounded_when_the_site_meter_is_never_read_again():
    night = Night()
    night.tick()
    assert night.pause_seen_before_the_meters().commands == ()
    batch = night.tick(SETTLING_MAX_S)  # same old reading: back to the plain calculation
    assert ('tank', 'suspend') in actions(batch)


def test_nothing_starts_until_the_site_meter_shows_the_change():
    night = Night()
    night.engine.requested.pop('tank'); night.engine.running_since.pop('tank')
    night.policies['tank'] = replace(night.policies['tank'], mode='off')
    night.grid_w, night.tank_w = 4500, 0
    assert night.tick().commands == ()
    night.policies['tank'] = replace(night.policies['tank'], mode='off_peak_solar')
    batch = night.pause_seen_before_the_meters()
    assert batch.commands == ()
    assert batch.reasons['tank'] == 'Mesures en cours de mise à jour : démarrage différé'
