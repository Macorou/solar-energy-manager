from dataclasses import dataclass
from datetime import datetime, timezone
import math
from app.settings import SettingsDocument

CONTROL_MAX_AGE_S = 30
PROVIDER_ERRORS = {
    'not_configured': 'Peugeot non configuré',
    'reconnect_required': 'Reconnexion Peugeot nécessaire',
    'rate_limited': 'Limite de requêtes Peugeot atteinte',
    'vehicle_not_found': 'Véhicule introuvable chez Peugeot',
    'vin_required': 'VIN du véhicule à renseigner',
    'provider_unavailable': 'Service indisponible'}


@dataclass(frozen=True)
class Entity:
    group: str  # 'site' or a SEM device id
    key: str
    component: str  # 'sensor' or 'binary_sensor'
    name: str
    device_name: str
    value: str | None  # None means unavailable; binary values are 'ON'/'OFF'
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    precision: int | None = None
    attributes: dict | None = None
    throttled: bool = False


def _number(value, decimals):
    if value is None or isinstance(value, bool) or not math.isfinite(value): return None
    return f'{value:.{decimals}f}'


def _short(value):
    text = _number(value, 1)
    return None if text is None else text.rstrip('0').rstrip('.')


def _power(value):
    text = _number(value, 0)
    return '0' if text == '-0' else text


def _time(value):
    if isinstance(value, str):
        try: value = datetime.fromisoformat(value)
        except ValueError: return None
    if not isinstance(value, datetime): return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _binary(flag):
    return 'ON' if flag else 'OFF'


def _mode(config):
    if not config['armed']: return 'Observation'
    if config['mode'] == 'manual': return 'Manuel'
    if config['mode'] == 'off': return 'Pause'
    return 'Automatique'


def _status(device):
    # Mirrors the badge of frontend DeviceCard.
    config, state, command = device['config'], device['state'], device.get('command')
    power = state.get('observed_power') or {}
    value = power.get('value') if power.get('usable') else None
    status = (command or {}).get('status')
    if state.get('fault') or status == 'unknown': return 'À vérifier'
    if (state.get('connected') and value is not None and value > 20
            and state.get('observed_state') in ('Charging', 'on')):
        return 'En charge' if config['kind'] == 'charger' else 'En chauffe'
    if status in ('sending', 'accepted'): return 'En attente de confirmation'
    if not config['armed']: return 'Observation'
    if not state.get('connected'): return 'Hors connexion'
    return 'En attente'


def _observed_power(device):
    power = device['state'].get('observed_power') or {}
    return _power(power.get('value')) if power.get('usable') else None


def _common(device_name, device, price):
    group = device['config']['id']
    def entity(key, name, value, **kw):
        return Entity(group, key, kw.pop('component', 'sensor'), name, device_name, value, **kw)
    return [
        entity('state', 'État', _status(device)),
        entity('reason', 'Raison', device.get('reason') or ''),
        entity('mode', 'Mode', _mode(device['config'])),
        entity('power', 'Puissance de chauffe' if device['config']['kind'] == 'water_heater' else 'Puissance de charge',
               _observed_power(device), unit='W', device_class='power', state_class='measurement', throttled=True),
        entity('price', {'charger': "Prix de l'énergie de la voiture", 'water_heater': "Prix de l'énergie du ballon"}[
            device['config']['kind']], price, unit='EUR/kWh', state_class='measurement', precision=3, throttled=True)]


def _charger(device, vehicles, price):
    config, state = device['config'], device['state']
    group = config['id']
    name = 'SEM – ' + config['name']
    charging = device.get('charging') or {}
    telemetry = vehicles.get(config.get('vehicle_id')) or {}
    if charging.get('active') and charging.get('soc') is not None:
        soc, source = charging['soc'], 'estimée' if charging.get('soc_estimated') else 'relevée'
    else:
        soc, source = telemetry.get('soc'), 'relevée'
    manual = config['mode'] == 'manual'
    authorized = (device.get('authorization') or {}).get('target_soc')
    target = config['default_soc_target'] if manual or authorized is None else authorized
    solar_target = config.get('solar_target')
    show_solar = not manual and solar_target is not None and solar_target > target
    def entity(key, label, value, **kw):
        return Entity(group, key, kw.pop('component', 'sensor'), label, name, value, **kw)
    return _common(name, device, price) + [
        entity('battery', 'Batterie', _short(soc), unit='%', device_class='battery', state_class='measurement',
               precision=1, attributes={'source': source}),
        entity('range', 'Autonomie', _short(telemetry.get('range_km')), unit='km', device_class='distance',
               state_class='measurement', precision=1),
        entity('plugged', 'Voiture branchée',
               _binary(state.get('vehicle_connected') is True) if state.get('connected') else None,
               component='binary_sensor', device_class='plug'),
        entity('target', 'Objectif', _short(target), unit='%', precision=1),
        entity('solar_target', 'Objectif sur surplus solaire', _short(solar_target) if show_solar else None,
               unit='%', precision=1),
        entity('session_energy', 'Énergie de la session', _number(charging.get('energy_kwh'), 2), unit='kWh',
               device_class='energy', state_class='total', precision=2,
               attributes={'partial': bool(charging.get('energy_partial'))}),
        entity('session_cost', 'Coût de la session', _number(charging.get('cost_eur'), 2), unit='EUR',
               device_class='monetary', state_class='total', precision=2,
               attributes={'partial': bool(charging.get('cost_partial'))}),
        entity('session_solar', 'Part solaire de la session', _short(charging.get('solar_percent')), unit='%',
               precision=1, attributes={'partial': bool(charging.get('solar_partial'))}),
        entity('plan_warning', 'Avertissement du programme', device.get('plan_warning') or '')]


def _heater(device, price):
    config, state = device['config'], device['state']
    group = config['id']
    name = 'SEM – ' + config['name']
    # Like the dashboard, a disconnected heater has no trustworthy temperature.
    temperature = state.get('temperature') if state.get('connected') else None
    source = 'solaire' if device.get('target_source') == 'solar' else 'réseau'
    return _common(name, device, price) + [
        Entity(group, 'temperature', 'sensor', 'Température', name, _short(temperature), unit='°C',
               device_class='temperature', state_class='measurement', precision=1),
        Entity(group, 'target', 'sensor', 'Consigne en cours', name, _short(device.get('effective_target')),
               unit='°C', device_class='temperature', precision=1, attributes={'source': source})]


def _site(state, now):
    at = _time(state.get('at'))
    active = bool(state.get('running')) and at is not None and (now - at).total_seconds() < CONTROL_MAX_AGE_S
    errors = list((state.get('errors') or {}).values())
    problem = PROVIDER_ERRORS.get(errors[0], errors[0]) if errors else ''
    prices = state.get('energy_prices') or {}
    surplus = state.get('solar_budget_w')
    def entity(key, label, value, **kw):
        return Entity('site', key, kw.pop('component', 'sensor'), label, 'SEM – Installation', value, **kw)
    return [
        entity('price', "Prix de l'énergie du site", _number(prices.get('site'), 3), unit='EUR/kWh',
               state_class='measurement', precision=3, throttled=True),
        entity('surplus', 'Surplus solaire disponible', _power(surplus), unit='W', device_class='power',
               state_class='measurement', throttled=True),
        entity('off_peak', 'Heures creuses', _binary(state.get('off_peak')), component='binary_sensor'),
        entity('control_active', 'Pilotage actif', _binary(active), component='binary_sensor'),
        entity('problem', 'Problème en cours', problem)]


def build_entities(state: dict, config: SettingsDocument, now: datetime) -> list[Entity]:
    # `config` is accepted for symmetry with the runtime; names and targets come from the published state.
    device_prices = (state.get('energy_prices') or {}).get('devices') or {}
    entities = _site(state, now)
    for device in state.get('devices', []):
        price = _number(device_prices.get(device['config']['id']), 3)
        if device['config']['kind'] == 'charger':
            entities += _charger(device, state.get('vehicles') or {}, price)
        else:
            entities += _heater(device, price)
    return entities
