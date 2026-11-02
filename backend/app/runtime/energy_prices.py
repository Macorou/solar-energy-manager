"""Per-device energy price: grid import is attributed to the least prioritary device first."""
IDLE_POWER_W = 20
KIND_ORDER = ('charger', 'water_heater')


def usable_value(sample, snapshot, config):
    return sample.value if sample and sample.usable(snapshot.at, config.sample_max_age_s) else None


def active_by_state(device, state):
    if device.kind == 'charger':
        return state.connected and state.observed_state == 'Charging'
    return state.observed_state == 'on'


def device_power(device, state, snapshot, config):
    if state is None:
        return None
    power = usable_value(state.observed_power, snapshot, config)
    if power is not None:
        return max(0, power)
    return None if active_by_state(device, state) else 0


def grid_shares(snapshot, config):
    """Device id -> grid fraction in [0, 1], or None when it cannot be known."""
    ordered = [d for kind in KIND_ORDER
               for d in sorted((d for d in config.devices if d.kind == kind), key=lambda d: d.priority, reverse=True)]
    grid = usable_value(snapshot.grid, snapshot, config)
    if grid is None:
        return {d.id: None for d in ordered}
    remaining = max(0, grid)
    shares = {}
    unknown = False
    for device in ordered:
        power = None if unknown else device_power(device, snapshot.device_states.get(device.id), snapshot, config)
        if power is None:
            unknown = True
            shares[device.id] = None
        elif power <= IDLE_POWER_W:
            shares[device.id] = 1.0 if remaining > 0 else 0.0
        else:
            imported = min(power, remaining)
            shares[device.id] = imported / power
            remaining -= imported
    return shares


def price_from_share(share, tariff, solar_price):
    if share is None:
        return None
    if share == 0:
        return solar_price
    if tariff is None:
        return None
    return share * tariff + (1 - share) * solar_price


def device_prices(snapshot, config):
    """Device id -> EUR/kWh rounded to 3 decimals, or None."""
    tariff = usable_value(snapshot.price, snapshot, config)
    prices = {}
    for device_id, share in grid_shares(snapshot, config).items():
        price = price_from_share(share, tariff, config.solar_price_per_kwh)
        prices[device_id] = None if price is None else round(price, 3)
    return prices
