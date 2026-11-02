"""Per-device energy prices: import is attributed to the least prioritary device first."""
from dataclasses import replace
from datetime import timedelta
import pytest
from app.domain.devices import DeviceState
from app.domain.measurements import Sample, utcnow
from app.domain.site import SiteSnapshot
from app.runtime.coordinator import Coordinator
from app.runtime.energy_prices import device_prices, grid_shares, price_from_share
from app.settings import SettingsDocument
from app.storage.database import SQLiteStore

NOW = utcnow()
TARIFF = 0.165


def sample(value, at=NOW):
    return Sample(value, 'W', 'test', at, at, checked_at=at)


def config(*extra):
    devices = [{'id': 'ev', 'name': 'EV', 'kind': 'charger', 'priority': 1},
               {'id': 'tank', 'name': 'Tank', 'kind': 'water_heater', 'priority': 2}, *extra]
    return SettingsDocument(devices=devices, solar_price_per_kwh=0)


def site(grid, car=('Charging', 3000), heater=('on', 2500), price=TARIFF, car_power_at=NOW, extra=None):
    states = {'ev': DeviceState('ev', sample(car[1], car_power_at), car[0], True, vehicle_connected=True),
              'tank': DeviceState('tank', sample(heater[1]), heater[0], True), **(extra or {})}
    return SiteSnapshot(NOW, grid=sample(grid) if grid is not None else None, solar=sample(0), site_limit_w=9000,
        price=Sample(price, 'EUR/kWh', 'test', NOW, NOW, checked_at=NOW) if price is not None else None,
        device_states=states)


def test_reference_example():
    snapshot = site(2000)
    assert grid_shares(snapshot, config()) == {'ev': pytest.approx(2 / 3), 'tank': 0.0}
    assert device_prices(snapshot, config()) == {'ev': 0.110, 'tank': 0.0}


def test_idle_car_pays_tariff_when_site_imports_and_solar_when_exporting():
    idle = dict(car=('Preparing', 0))
    assert device_prices(site(500, **idle), config())['ev'] == 0.165
    assert device_prices(site(-800, **idle), config())['ev'] == 0.0


def test_idle_heater_pays_tariff_only_when_import_exceeds_the_car():
    idle = dict(heater=('off', 0))
    assert device_prices(site(2000, **idle), config())['tank'] == 0.0
    assert device_prices(site(3500, **idle), config())['tank'] == 0.165


def test_missing_grid_makes_every_price_unavailable():
    assert device_prices(site(None), config()) == {'ev': None, 'tank': None}


def test_missing_tariff():
    assert device_prices(site(-500, price=None), config())['ev'] == 0.0
    assert device_prices(site(1000, price=None), config())['ev'] is None


def test_unknown_running_car_power_makes_later_prices_unknown():
    snapshot = site(1000, car_power_at=NOW - timedelta(seconds=120))
    assert device_prices(snapshot, config()) == {'ev': None, 'tank': None}


def test_unplugged_car_with_stale_power_counts_as_zero():
    snapshot = site(1000, car=('Available', 0), car_power_at=NOW - timedelta(seconds=120))
    assert device_prices(snapshot, config())['tank'] == pytest.approx(0.066)


def test_least_prioritary_charger_takes_import_first():
    cfg = SettingsDocument(solar_price_per_kwh=0, devices=[
        {'id': 'a', 'name': 'A', 'kind': 'charger', 'priority': 1},
        {'id': 'b', 'name': 'B', 'kind': 'charger', 'priority': 2}])
    states = {key: DeviceState(key, sample(2000), 'Charging', True, vehicle_connected=True) for key in 'ab'}
    snapshot = SiteSnapshot(NOW, grid=sample(2000), solar=sample(0), site_limit_w=9000, device_states=states)
    assert grid_shares(snapshot, cfg) == {'a': 0.0, 'b': 1.0}


def test_price_from_share():
    assert price_from_share(None, TARIFF, 0) is None
    assert price_from_share(0.0, None, 0.05) == 0.05
    assert price_from_share(0.5, None, 0.05) is None
    assert price_from_share(0.5, 0.2, 0.0) == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_public_state_exposes_energy_prices(tmp_path):
    store = SQLiteStore(tmp_path / 'db')
    cfg = config()
    store.save_settings(cfg.model_dump(mode='json'))
    runtime = Coordinator(store)
    now = utcnow()
    s = lambda value: Sample(value, 'W', 'test', now, now, checked_at=now)
    frame = SiteSnapshot(now, grid=s(2000), solar=s(0), site_limit_w=9000,
        price=Sample(TARIFF, 'EUR/kWh', 'test', now, now, checked_at=now),
        device_states={'ev': DeviceState('ev', s(3000), 'Charging', True, vehicle_connected=True),
                       'tank': DeviceState('tank', s(2500), 'on', True)})
    await runtime.tick(frame)
    prices = runtime.public_state()['energy_prices']
    assert set(prices) == {'site', 'devices'}
    assert prices['devices']['ev'] == device_prices(frame, cfg)['ev']
