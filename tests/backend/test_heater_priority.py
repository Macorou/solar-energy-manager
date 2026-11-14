"""A water heater with a higher priority than the car gets its surplus back from the car.

2026-11-14 morning: the car (priority 2) started first on 1.4 kW, which the 2.7 kW heater
(priority 1) could not use. At 10:19 the surplus reached ~4.9 kW; the heater began its
5-minute wait, but the car raised to 4.4 kW within a minute and the heater never started.
"""
from datetime import timedelta

from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Sample
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock

CAR = DeviceSpec('ev', 'charger', min_power_w=1380, max_power_w=4600, max_current_a=20, priority=2)
TANK = DeviceSpec('tank', 'water_heater', min_power_w=2700, max_power_w=2700, priority=1)
HOUSE_W = 300


class Morning:
    """Every device draws what SEM last asked of it; grid = house + devices - solar."""

    def __init__(self, car_a, car_mode='solar', tank_priority=1):
        self.clock = SimulatedClock(); self.engine = EnergyEngine(self.clock)
        self.specs = [CAR, DeviceSpec('tank', 'water_heater', min_power_w=2700, max_power_w=2700,
                                      priority=tank_priority)]
        if car_a:
            self.engine.requested['ev'] = self.engine.charger_offered['ev'] = car_a*230
            self.engine.running_since['ev'] = self.clock.monotonic()
        until = self.clock.now()+timedelta(hours=4) if car_mode=='manual' else None
        self.policies = {
            'ev': DevicePolicy('ev', car_mode, armed=True, start_delay_s=300, manual_until=until),
            'tank': DevicePolicy('tank', 'solar', armed=True, start_delay_s=300, target=75)}
        self.clock.advance(600)
        self.sent = []

    def draw(self, key):
        return self.engine.requested.get(key) or 0

    def tick(self, solar_w, seconds=10):
        self.clock.advance(seconds)
        now = self.clock.now()
        s = lambda value: Sample(value, 'W', 'test', now, now, checked_at=now)
        car, tank = self.draw('ev'), self.draw('tank')
        snapshot = SiteSnapshot(now, grid=s(HOUSE_W+car+tank-solar_w), site_limit_w=12000, export_margin_w=0,
            device_states={
                'ev': DeviceState('ev', s(car), 'Charging' if car else 'SuspendedEVSE', True,
                                  vehicle_connected=True, transaction_active=True),
                'tank': DeviceState('tank', s(tank), 'heating' if tank else 'idle', True, temperature=55)})
        batch = self.engine.evaluate(snapshot, self.specs, self.policies, {})
        for command in batch.commands:
            self.engine.command_result(command, True)  # the station and the heater accept at once
        self.sent += [(c.device_id, c.limit_w) for c in batch.commands]
        return batch

    def run(self, solar_w, seconds):
        for _ in range(int(seconds//10)):
            batch = self.tick(solar_w)
        return batch


def test_the_car_gives_way_to_a_higher_priority_heater():
    # 10:20: ~5.2 kW of sun, the car takes 19 A, only ~600 W is left over.
    morning = Morning(car_a=19)
    morning.run(5200+HOUSE_W, 20)
    assert morning.draw('tank') == 0
    morning.run(5200+HOUSE_W, 300)
    assert morning.draw('tank') == 2700
    # The car keeps what the heater leaves, never less than its minimum.
    assert 1380 <= morning.draw('ev') <= 5200-2700
    morning.run(5200+HOUSE_W, 120)
    assert morning.draw('tank') == 2700
    assert 1380 <= morning.draw('ev') <= 5200-2700


def test_the_car_does_not_grow_into_the_surplus_the_heater_waits_for():
    morning = Morning(car_a=8)
    morning.run(5000+HOUSE_W, 200)
    # Only what the heater will not need: 5000 - 2700 W.
    assert 8*230 <= morning.draw('ev') <= 5000-2700
    assert morning.draw('tank') == 0
    morning.run(5000+HOUSE_W, 120)
    assert morning.draw('tank') == 2700
    assert morning.draw('ev') <= 5000-2700


def test_the_car_does_not_start_on_the_surplus_the_heater_waits_for():
    morning = Morning(car_a=0)
    morning.run(3000+HOUSE_W, 320)
    assert morning.draw('tank') == 2700
    assert not any(device=='ev' and limit for device, limit in morning.sent)


def test_a_car_charging_from_the_grid_is_not_counted_as_surplus():
    morning = Morning(car_a=19, car_mode='manual')
    morning.run(5200+HOUSE_W, 400)
    assert morning.draw('tank') == 0
    assert morning.draw('ev') >= 19*230


def test_a_heater_with_a_lower_priority_does_not_take_from_the_car():
    morning = Morning(car_a=19, tank_priority=3)
    morning.run(5200+HOUSE_W, 400)
    assert morning.draw('tank') == 0
    assert morning.draw('ev') >= 19*230


def test_the_car_still_uses_what_the_heater_cannot():
    # 9:55: 2 kW of sun, too little for the 2.7 kW heater: the car may charge on it.
    morning = Morning(car_a=0)
    morning.run(2000+HOUSE_W, 400)
    assert morning.draw('tank') == 0
    assert morning.draw('ev') >= 1380
