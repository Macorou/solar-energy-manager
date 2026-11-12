"""The charger limit follows the room left on its phase in whole amps, and does not chase noise.

2026-11-12 evening: with 1 to 2 A of household noise on L1, the limit changed every 10 to 30 s
(17.5, 18.5, 17.9, 19.1 A...); twice the station paused itself right after such a change.
"""
from datetime import timedelta

from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Sample
from app.domain.site import SiteSnapshot
from app.engine.engine import CHARGER_RAISE_S, EnergyEngine
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock

CAR = DeviceSpec('ev', 'charger', min_power_w=1380, max_power_w=4600, max_current_a=20, grid_phases=('L1',))


class Evening:
    """The car draws what it is offered; L1 = house + car; room on L1 = 20 A - 1 A margin - house."""

    def __init__(self, offer_a):
        self.clock = SimulatedClock(); self.engine = EnergyEngine(self.clock)
        self.engine.requested['ev'] = self.engine.charger_offered['ev'] = offer_a*230
        self.engine.running_since['ev'] = self.clock.monotonic()
        self.engine.phase_current_seen.add('ev')
        self.policies = {'ev': DevicePolicy('ev', 'manual', armed=True,
                                            manual_until=self.clock.now()+timedelta(hours=4))}
        self.clock.advance(120)

    def tick(self, room_a, seconds=10):
        """`room_a`: what the phase leaves to the car, as the engine computes it."""
        self.clock.advance(seconds)
        now = self.clock.now()
        s = lambda value, unit='W': Sample(value, unit, 'test', now, now, checked_at=now)
        car_a = self.engine.requested['ev']/230
        house_a = 19-room_a
        snapshot = SiteSnapshot(now, grid=s((house_a+car_a)*230+300), solar=s(0), site_limit_w=12000,
            device_states={'ev': DeviceState('ev', s(car_a*230), 'Charging', True, vehicle_connected=True,
                                             transaction_active=True, currents={'L1': s(car_a, 'A')})},
            phase_currents={'L1': s(house_a+car_a, 'A')}, phase_limits_a={'L1': 20}, phase_margin_a=1,
            phase_control_enabled=True)
        return self.engine.evaluate(snapshot, [CAR], self.policies, {})


def limits(batch):
    return [c.limit_w/230 for c in batch.commands]


def test_household_noise_on_the_phase_sends_nothing():
    evening = Evening(offer_a=15)
    sent = []
    for room in [15.4, 16.3, 15.8, 16.9, 15.2, 16.4, 15.9, 16.6, 15.3, 16.1, 15.7, 16.8]:
        sent += limits(evening.tick(room))
    assert sent == []


def test_a_lasting_increase_is_sent_after_a_minute_in_whole_amps():
    evening = Evening(offer_a=15)
    assert limits(evening.tick(17.6)) == []
    assert limits(evening.tick(17.6, CHARGER_RAISE_S-1)) == []
    assert limits(evening.tick(17.6, 1)) == [17]


def test_an_increase_interrupted_by_a_dip_starts_its_minute_again():
    evening = Evening(offer_a=15)
    evening.tick(17.6)
    evening.tick(15.5, CHARGER_RAISE_S-20)  # still above 15 A: nothing to reduce, but no more gain
    assert limits(evening.tick(17.6, 15)) == []
    assert limits(evening.tick(17.6, CHARGER_RAISE_S-1)) == []
    assert limits(evening.tick(17.6, 1)) == [17]


def test_a_decrease_is_sent_at_once_in_whole_amps():
    evening = Evening(offer_a=15)
    assert limits(evening.tick(14.6, 2)) == [14]
