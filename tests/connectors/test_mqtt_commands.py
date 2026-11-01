import asyncio
from types import SimpleNamespace
import pytest
from app.connectors.mqtt.commands import CommandHandler
from app.runtime.coordinator import Coordinator
from app.settings import SettingsDocument
from app.storage.database import SQLiteStore


def make(tmp_path, commands_enabled=True):
    store = SQLiteStore(tmp_path / 'db')
    store.save_settings(SettingsDocument.model_validate({
        'mqtt': {'commands_enabled': commands_enabled},
        'devices': [{'id': 'ev', 'name': 'Wallbox', 'kind': 'charger', 'mode': 'solar', 'armed': True, 'vehicle_id': 'car'},
                    {'id': 'tank', 'name': 'Ballon', 'kind': 'water_heater', 'armed': True}],
        'vehicles': [{'id': 'car'}, {'id': 'van'}],
        'schedules': [{'id': 'semaine', 'name': 'Semaine', 'vehicle_id': 'car', 'target_soc': 80},
                      {'id': 'autre', 'name': 'Autre', 'vehicle_id': 'van', 'target_soc': 70}]}).model_dump(mode='json'))
    state = SimpleNamespace(store=store, coordinator=Coordinator(store))
    return state, CommandHandler(lambda: state)


def mode(state): return state.store.load_settings()['devices'][0]['mode']
def targets(state): return {p['id']: p['target_soc'] for p in state.store.load_settings()['schedules']}
def lines(state, level=None):
    entries = state.store.journal.query(areas=('mqtt',))['entries']
    return [e['message'] for e in entries if level is None or e['level'] == level]


async def test_auto_manual_pause_change_the_mode(tmp_path):
    state, handler = make(tmp_path)
    for option, expected in (('Auto', 'planned'), ('Manuel', 'manual'), ('Pause', 'off')):
        assert await handler.handle('sem', 'sem/ev/car_mode/set', option) == ('ev', 'car_mode')
        assert mode(state) == expected
    assert lines(state, 'INFO') == ['Mode Auto demandé depuis Home Assistant',
                                    'Mode Manuel demandé depuis Home Assistant',
                                    'Mode Pause demandé depuis Home Assistant']
    assert state.store.events()[0]['details']['origin'] == 'home_assistant'


@pytest.mark.parametrize('option,expected', [('Auto', 'planned'), ('Manuel', 'manual'), ('Pause', 'off')])
async def test_repeating_the_active_mode_does_not_command_the_charger_again(tmp_path, option, expected):
    state, handler = make(tmp_path)
    forgotten = []
    state.coordinator.engine.forget = forgotten.append
    assert await handler.handle('sem', 'sem/ev/car_mode/set', option) == ('ev', 'car_mode')
    assert mode(state) == expected
    done, events, controls = list(forgotten), list(state.store.events()), state.store.get('manual_controls', {})
    assert await handler.handle('sem', 'sem/ev/car_mode/set', option) == ('ev', 'car_mode')   # republished
    assert mode(state) == expected
    assert forgotten == done and list(state.store.events()) == events
    assert state.store.get('manual_controls', {}) == controls
    assert lines(state, 'INFO') == [f'Mode {option} demandé depuis Home Assistant',
                                    f'Mode {option} déjà actif (demande Home Assistant)']


async def test_refused_manual_is_journaled_and_republished(tmp_path):
    state, handler = make(tmp_path)
    config = state.store.load_settings(); config['devices'][0]['armed'] = False
    state.store.save_settings(config)
    assert await handler.handle('sem', 'sem/ev/car_mode/set', 'Manuel') == ('ev', 'car_mode')
    assert mode(state) == 'solar'
    assert lines(state, 'WARN') == ['Commande Home Assistant refusée : Manuel – Activer et vérifier cet appareil avant une commande']


async def test_program_target_is_saved(tmp_path):
    state, handler = make(tmp_path)
    assert await handler.handle('sem', 'sem/ev/program_semaine_target/set', ' 100\n') == ('ev', 'program_semaine_target')
    assert targets(state) == {'semaine': 100, 'autre': 70}
    assert lines(state, 'INFO') == ['Objectif du programme « Semaine » réglé à 100 % depuis Home Assistant']
    await handler.handle('sem', 'sem/ev/program_semaine_target/set', '82.5')
    assert targets(state)['semaine'] == 82.5
    assert lines(state, 'INFO')[-1] == 'Objectif du programme « Semaine » réglé à 82.5 % depuis Home Assistant'


@pytest.mark.parametrize('payload', ['abc', 'nan', 'inf', '0', '101', '', '1_0', '0.99'])
async def test_invalid_target_payloads_change_nothing(tmp_path, payload):
    state, handler = make(tmp_path)
    assert await handler.handle('sem', 'sem/ev/program_semaine_target/set', payload) == ('ev', 'program_semaine_target')
    assert targets(state) == {'semaine': 80, 'autre': 70}
    assert len(lines(state, 'WARN')) == 1 and lines(state, 'WARN')[0].startswith('Commande Home Assistant ignorée : ')


async def test_unknown_mode_option_is_refused(tmp_path):
    state, handler = make(tmp_path)
    for option in ('Turbo', 'auto'):
        assert await handler.handle('sem', 'sem/ev/car_mode/set', option) == ('ev', 'car_mode')
        assert mode(state) == 'solar'
    assert len(lines(state, 'WARN')) == 2 and all(l.startswith('Commande Home Assistant ignorée : ') for l in lines(state, 'WARN'))
    await handler.handle('sem', 'sem/ev/car_mode/set', ' Pause ')
    assert mode(state) == 'off'


async def test_long_payloads_are_cut_in_the_journal(tmp_path):
    state, handler = make(tmp_path)
    await handler.handle('sem', 'sem/ev/car_mode/set', 'X' * 500)
    await handler.handle('sem', 'sem/ev/program_semaine_target/set', '9' * 500)
    assert all('X' * 41 not in l and '9' * 41 not in l for l in lines(state))


async def test_commands_for_unknown_targets_are_ignored(tmp_path):
    state, handler = make(tmp_path)
    for topic in ('sem/tank/car_mode/set', 'sem/ghost/car_mode/set', 'sem/ev/program_autre_target/set',
                  'sem/ev/program_deleted_target/set', 'sem/ev/unknown_key/set'):
        assert await handler.handle('sem', topic, 'Pause') is None
    assert mode(state) == 'solar' and targets(state) == {'semaine': 80, 'autre': 70}
    assert len(lines(state, 'WARN')) == 5


async def test_topics_that_are_not_commands_return_none(tmp_path):
    state, handler = make(tmp_path)
    for topic in ('sem/ev/car_mode/state', 'other/ev/car_mode/set', 'sem/ev/set', 'sem/a/b/c/set', 'sem/status'):
        assert await handler.handle('sem', topic, 'Pause') is None
    assert mode(state) == 'solar' and lines(state) == []


async def test_disabled_commands_apply_nothing(tmp_path):
    state, handler = make(tmp_path, commands_enabled=False)
    assert await handler.handle('sem', 'sem/ev/car_mode/set', 'Pause') is None
    assert mode(state) == 'solar' and lines(state) == []


async def test_command_waits_for_the_coordinator_lock(tmp_path):
    state, handler = make(tmp_path)
    async with state.coordinator.lock:
        task = asyncio.create_task(handler.handle('sem', 'sem/ev/car_mode/set', 'Pause'))
        await asyncio.sleep(0.05)
        assert not task.done() and mode(state) == 'solar'
    assert await asyncio.wait_for(task, 2) == ('ev', 'car_mode')
    assert mode(state) == 'off'
