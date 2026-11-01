import pytest
import json
from datetime import datetime, timedelta, timezone
from app.connectors.mqtt.entities import build_entities
from app.connectors.mqtt.publisher import Publisher
from app.settings import SettingsDocument
from app.storage.database import SQLiteStore

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def make_state(**overrides):
    state = {
        'running': True, 'at': NOW - timedelta(seconds=5), 'errors': {},
        'solar_budget_w': 1234.4, 'off_peak': False,
        'energy_prices': {'site': 0.1234, 'devices': {'ev': 0.11, 'tank': 0.2}},
        'devices': [
            {'config': {'id': 'ev', 'name': 'Wallbox', 'kind': 'charger', 'mode': 'planned', 'armed': True,
                        'vehicle_id': 'car', 'default_soc_target': 80, 'solar_target': 90,
                        'charge_point_id': 'CP-SECRET'},
             'state': {'id': 'ev', 'observed_power': {'value': 3200.0, 'usable': True},
                       'observed_state': 'Charging', 'connected': True, 'fault': None, 'vehicle_connected': True},
             'reason': 'Charge sur surplus', 'effective_target': None, 'target_source': 'grid',
             'plan_warning': None,
             'charging': {'active': True, 'soc': 55.26, 'soc_estimated': True, 'energy_kwh': 4.256,
                          'cost_eur': 1.234, 'solar_percent': 62.34},
             'command': {'status': 'observed'}, 'authorization': {'target_soc': 70}},
            {'config': {'id': 'tank', 'name': 'Ballon', 'kind': 'water_heater', 'mode': 'solar', 'armed': True},
             'state': {'id': 'tank', 'observed_power': {'value': 1500.0, 'usable': True},
                       'observed_state': 'on', 'connected': True, 'fault': None, 'temperature': 48.54},
             'reason': 'Surplus', 'effective_target': 55.0, 'target_source': 'solar',
             'plan_warning': None, 'charging': None, 'command': None, 'authorization': None}],
        'vehicles': {'car': {'soc': 41.0, 'range_km': 123.46}},
    }
    state.update(overrides)
    return state


def build(state=None, config=None):
    return build_entities(state or make_state(), config or SettingsDocument(), NOW)


def find(entities, group, key):
    return next(e for e in entities if e.group == group and e.key == key)


def test_catalogue_keys_units_and_device_names():
    entities = build()
    assert {(e.group, e.key) for e in entities} == {
        *{('site', k) for k in ('price', 'surplus', 'off_peak', 'control_active', 'problem')},
        *{('ev', k) for k in ('price', 'battery', 'range', 'power', 'state', 'reason', 'mode', 'plugged', 'target',
                              'solar_target', 'session_energy', 'session_cost', 'session_solar', 'plan_warning')},
        *{('tank', k) for k in ('price', 'temperature', 'target', 'power', 'state', 'reason', 'mode')}}
    units = {(e.group, e.key): e.unit for e in entities if e.unit}
    assert units == {('site', 'price'): 'EUR/kWh', ('site', 'surplus'): 'W', ('ev', 'price'): 'EUR/kWh',
        ('ev', 'battery'): '%', ('ev', 'range'): 'km', ('ev', 'power'): 'W', ('ev', 'target'): '%',
        ('ev', 'solar_target'): '%', ('ev', 'session_energy'): 'kWh', ('ev', 'session_cost'): 'EUR',
        ('ev', 'session_solar'): '%', ('tank', 'price'): 'EUR/kWh', ('tank', 'temperature'): '°C',
        ('tank', 'target'): '°C', ('tank', 'power'): 'W'}
    assert {e.device_name for e in entities if e.group == 'site'} == {'SEM – Installation'}
    assert {e.device_name for e in entities if e.group == 'ev'} == {'SEM – Wallbox'}
    assert {e.device_name for e in entities if e.group == 'tank'} == {'SEM – Ballon'}
    assert find(entities, 'site', 'price').throttled and find(entities, 'ev', 'power').throttled
    assert not find(entities, 'ev', 'battery').throttled
    assert find(entities, 'ev', 'plugged').component == 'binary_sensor'
    assert find(entities, 'site', 'surplus').value == '1234'
    assert find(entities, 'ev', 'power').value == '3200'
    assert find(entities, 'ev', 'range').value == '123.5'
    assert find(entities, 'ev', 'session_energy').value == '4.26'
    assert find(entities, 'ev', 'session_cost').value == '1.23'
    assert find(entities, 'tank', 'temperature').value == '48.5'


def test_prices_are_three_decimals_and_none_is_unavailable():
    entities = build()
    assert find(entities, 'ev', 'price').value == '0.110'
    assert find(entities, 'site', 'price').value == '0.123'
    entities = build(make_state(energy_prices={'site': None, 'devices': {'ev': None}}))
    assert find(entities, 'ev', 'price').value is None
    assert find(entities, 'site', 'price').value is None
    assert find(entities, 'tank', 'price').value is None


def test_mode_and_state_labels():
    assert find(build(), 'ev', 'mode').value == 'Automatique'
    assert find(build(), 'ev', 'state').value == 'En charge'
    assert find(build(), 'tank', 'state').value == 'En chauffe'
    state = make_state()
    state['devices'][0]['config']['armed'] = False
    entities = build(state)
    assert find(entities, 'ev', 'mode').value == 'Observation'
    assert find(entities, 'ev', 'state').value == 'En charge'
    state = make_state()
    state['devices'][0]['command'] = {'status': 'unknown'}
    assert find(build(state), 'ev', 'state').value == 'À vérifier'
    state = make_state()
    state['devices'][0]['state']['observed_state'] = 'Available'
    state['devices'][0]['command'] = {'status': 'sending'}
    assert find(build(state), 'ev', 'state').value == 'En attente de confirmation'
    state['devices'][0]['command'] = None
    assert find(build(state), 'ev', 'state').value == 'En attente'
    state['devices'][0]['state']['connected'] = False
    assert find(build(state), 'ev', 'state').value == 'Hors connexion'
    state['devices'][0]['config']['armed'] = False
    assert find(build(state), 'ev', 'state').value == 'Observation'
    for mode, label in (('manual', 'Manuel'), ('off', 'Pause'), ('solar', 'Automatique')):
        state['devices'][0]['config'].update(armed=True, mode=mode)
        assert find(build(state), 'ev', 'mode').value == label


def test_battery_source():
    battery = find(build(), 'ev', 'battery')
    assert battery.value == '55.3' and battery.attributes == {'source': 'estimée'}
    state = make_state()
    state['devices'][0]['charging'] = None
    battery = find(build(state), 'ev', 'battery')
    assert battery.value == '41' and battery.attributes == {'source': 'relevée'}


def test_targets():
    entities = build()
    assert find(entities, 'ev', 'target').value == '70'
    assert find(entities, 'ev', 'solar_target').value == '90'
    state = make_state()
    state['devices'][0]['config']['mode'] = 'manual'
    entities = build(state)
    assert find(entities, 'ev', 'target').value == '80'
    assert find(entities, 'ev', 'solar_target').value is None
    assert find(build(), 'tank', 'target').attributes == {'source': 'solaire'}
    assert find(build(), 'tank', 'target').value == '55'


def test_site_control_and_problem():
    assert find(build(), 'site', 'control_active').value == 'ON'
    assert find(build(), 'site', 'off_peak').value == 'OFF'
    assert find(build(), 'site', 'problem').value == ''
    assert find(build(make_state(at=NOW - timedelta(seconds=30))), 'site', 'control_active').value == 'OFF'
    recent = make_state(at=(NOW - timedelta(seconds=2)).isoformat())
    assert find(build(recent), 'site', 'control_active').value == 'ON'
    assert find(build(make_state(at=None)), 'site', 'control_active').value == 'OFF'
    assert find(build(make_state(running=False)), 'site', 'control_active').value == 'OFF'


def test_problem_translates_provider_codes():
    state = make_state(errors={'vehicle_car': 'reconnect_required'})
    assert find(build(state), 'site', 'problem').value == 'Reconnexion Peugeot nécessaire'
    state = make_state(errors={'runtime': 'Évaluation indisponible'})
    assert find(build(state), 'site', 'problem').value == 'Évaluation indisponible'


class Recorder:
    def __init__(self): self.sent = []
    async def publish(self, topic, payload, retain): self.sent.append((topic, payload, retain))


async def test_no_vin_or_identity_leaks(tmp_path):
    secrets = ('VR3UPHNKSKT101600', 'someone@example.com', 'CP-SECRET')
    config = SettingsDocument.model_validate({
        'vehicles': [{'id': 'car', 'name': 'Peugeot e-208', 'vin': secrets[0]}],
        'peugeot': {'username': secrets[1]},
        'devices': [{'id': 'ev', 'name': 'Wallbox', 'kind': 'charger', 'charge_point_id': secrets[2]}]})
    entities = build(config=config)
    client = Recorder()
    publisher = Publisher(client, 'sem', 'homeassistant', SQLiteStore(tmp_path / 'db'))
    await publisher.announce(entities)
    await publisher.publish(entities, 0.0)
    dump = json.dumps([[e.__dict__ for e in entities], client.sent], default=str, ensure_ascii=False)
    assert 'sem_ev_power' in dump
    for secret in secrets:
        assert secret not in dump


def with_charger(**changes):
    state = make_state()
    charger = state['devices'][0]
    for part, values in changes.items(): charger[part] = {**(charger[part] or {}), **values}
    return state


def test_session_entities_flag_partial_values():
    entities = build()
    assert find(entities, 'ev', 'session_energy').attributes == {'partial': False}
    assert find(entities, 'ev', 'session_cost').attributes == {'partial': False}
    assert find(entities, 'ev', 'session_solar').attributes == {'partial': False}
    entities = build(with_charger(charging={'solar_partial': True}))
    assert find(entities, 'ev', 'session_solar').attributes == {'partial': True}
    entities = build(with_charger(charging={'energy_partial': True, 'cost_partial': False}))
    assert find(entities, 'ev', 'session_energy').attributes == {'partial': True}
    assert find(entities, 'ev', 'session_cost').attributes == {'partial': False}
    entities = build(with_charger(charging={'energy_partial': False, 'cost_partial': True}))
    assert find(entities, 'ev', 'session_energy').attributes == {'partial': False}
    assert find(entities, 'ev', 'session_cost').attributes == {'partial': True}
    entities = build(make_state(devices=[{**make_state()['devices'][0], 'charging': None}]))
    assert find(entities, 'ev', 'session_energy').attributes == {'partial': False}
    assert find(entities, 'ev', 'session_energy').value is None


def test_plugged_is_unavailable_when_the_charger_is_not_connected():
    assert find(build(), 'ev', 'plugged').value == 'ON'
    assert find(build(with_charger(state={'vehicle_connected': False})), 'ev', 'plugged').value == 'OFF'
    assert find(build(with_charger(state={'vehicle_connected': None})), 'ev', 'plugged').value == 'OFF'
    for connected in (False, None):
        entities = build(with_charger(state={'connected': connected, 'vehicle_connected': True}))
        assert find(entities, 'ev', 'plugged').value is None


def commands_config(**mqtt):
    return SettingsDocument.model_validate({
        'mqtt': {'commands_enabled': True, **mqtt},
        'devices': [{'id': 'ev', 'name': 'Wallbox', 'kind': 'charger', 'mode': 'planned', 'vehicle_id': 'car'},
                    {'id': 'ev2', 'name': 'Garage', 'kind': 'charger', 'mode': 'off'},
                    {'id': 'tank', 'name': 'Ballon', 'kind': 'water_heater'}],
        'vehicles': [{'id': 'car'}, {'id': 'van'}],
        'schedules': [{'id': 'week', 'name': 'Semaine', 'vehicle_id': 'car', 'target_soc': 80},
                      {'id': 'we', 'name': 'Week-end', 'vehicle_id': 'car', 'target_soc': 100, 'enabled': False},
                      {'id': 'other', 'name': 'Autre', 'vehicle_id': 'van'}]})


def test_commands_disabled_add_no_entities():
    assert not [e for e in build() if e.command]
    config = commands_config()
    config.mqtt.commands_enabled = False
    assert not [e for e in build(config=config) if e.command]


@pytest.mark.parametrize('mode,label', [('planned', 'Auto'), ('manual', 'Manuel'), ('off', 'Pause'),
                                        ('solar', 'None'), ('off_peak_solar', 'None')])
def test_car_mode_select_maps_sem_modes(mode, label):
    config = commands_config()
    config.devices[0].mode = mode
    select = find(build(config=config), 'ev', 'car_mode')
    assert select.component == 'select' and select.command is True and select.value == label
    assert select.options == ('Auto', 'Manuel', 'Pause') and select.name == 'Mode de la voiture'
    assert select.device_name == 'SEM – Wallbox'


def test_one_target_number_per_program_of_the_car():
    entities = build(config=commands_config())
    numbers = [e for e in entities if e.component == 'number']
    assert [(e.group, e.key, e.name) for e in numbers] == [
        ('ev', 'program_week_target', 'Objectif – Semaine'), ('ev', 'program_we_target', 'Objectif – Week-end')]
    assert [e.value for e in numbers] == ['80', '100']
    assert all(e.command and e.unit == '%' and (e.minimum, e.maximum, e.step) == (1, 100, 1) for e in numbers)
    assert {e.device_name for e in numbers} == {'SEM – Wallbox'}
    assert [e.key for e in entities if e.group == 'ev2' and e.command] == ['car_mode']
    assert not [e for e in entities if e.group == 'tank' and e.command]
