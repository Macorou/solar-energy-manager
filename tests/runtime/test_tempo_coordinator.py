"""Tempo red day, peak hours, in the coordinator; Manual with a chosen duration."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.domain.devices import DeviceState
from app.domain.measurements import Sample, utcnow
from app.domain.site import SiteSnapshot
from app.runtime.coordinator import Coordinator
from app.scheduling.tempo import next_tempo_day_start
from app.settings import SettingsDocument
from test_resume_modes import service

PARIS = ZoneInfo('Europe/Paris')
TEMPO = 'sensor.rte_tempo_couleur_actuelle'


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=PARIS).astimezone(timezone.utc)


def setup(tmp_path, kind='charger', mode='planned', entity=TEMPO, program=False):
    app, client = service(tmp_path, kind, mode)
    settings = app.state.store.load_settings()
    settings['home_assistant']['tempo_entity'] = entity
    settings['off_peak'] = [{'start': '22:00', 'end': '06:00'}]
    settings['devices'][0]['cloud'] |= {'import_tolerance_w': 500, 'stop_delay_s': 180, 'min_run_s': 300}
    if program:
        settings['schedules'] = [{'id': 'nuit', 'vehicle_id': 'car', 'weekdays': list(range(7)),
                                  'earliest_start': '22:00', 'deadline': '07:00', 'target_soc': 80}]
    app.state.store.save_settings(settings)
    return app, client


def site(now, color='Rouge', ev=3680, state='Charging', grid=3800, changed=None):
    s = lambda value: Sample(value, 'W', 'test', now, now, checked_at=now)
    return SiteSnapshot(now, grid=s(grid), solar=s(0), site_limit_w=9000, export_margin_w=0, tempo_state=color,
        tempo_changed_at=changed,
        device_states={'device': DeviceState('device', s(ev), state, True, vehicle_connected=True)})


def spy(coordinator):
    seen = []
    evaluate = coordinator.engine.evaluate
    def wrapped(snapshot, specs, policies, authorizations):
        seen.append(policies['device'])
        return evaluate(snapshot, specs, policies, authorizations)
    coordinator.engine.evaluate = wrapped
    return seen


def mode(app): return app.state.store.load_settings()['devices'][0]['mode']
def kinds(app, kind): return [e for e in app.state.store.events() if e['kind'] == kind]
def journal(app, area='tempo'):
    return [(e['level'], e['message']) for e in app.state.store.journal.query(areas=(area,))['entries']]
def said(app, device='device'):
    # The readable journal lines, without the raw copy of each event.
    return [e for e in journal(app, 'device:'+device) if not re.match(r'^\w+ \{', e[1])]
START, END = {'state': 'start', 'reason': 'Début'}, {'state': 'end', 'reason': 'Fin'}
CUT = 'Heures pleines rouges : fin du mode Manuel, retour en automatique'


async def test_red_peak_stops_planned_grid_charge(tmp_path):
    app, _ = setup(tmp_path, program=True)
    coordinator = app.state.coordinator
    seen = spy(coordinator)
    coordinator.engine.requested['device'] = 3680
    before = await coordinator.tick(site(at(6, 5, 59)))
    assert not seen[-1].grid_blocked and seen[-1].import_tolerance_w == 500 and seen[-1].stop_delay_s == 180
    assert seen[-1].min_run_s == 300
    assert coordinator.engine.network_allowed['device'] is True
    assert not any(c.action == 'suspend' for c in before.commands)
    batch = await coordinator.tick(site(at(6, 6)))
    policy = seen[-1]
    assert (policy.mode, policy.grid_blocked, policy.import_tolerance_w, policy.stop_delay_s) == ('planned', True, 0, 0)
    assert policy.min_run_s == 0   # no minimum run on the grid either
    assert [c.action for c in batch.commands if c.device_id == 'device'] == ['suspend']
    assert coordinator.red_peak_active is True
    assert [e['details'] for e in kinds(app, 'tempo_red_peak')] == [START]
    assert journal(app) == [('INFO', 'Heures pleines rouges : réseau coupé en automatique')]


async def test_red_peak_start_ends_running_manual(tmp_path):
    app, _ = setup(tmp_path, mode='manual')
    app.state.store.set('manual_controls', {'device': {'until': (at(6, 5) + timedelta(hours=4)).isoformat(),
                                                       'previous_mode': 'planned'}})
    coordinator = app.state.coordinator
    seen = spy(coordinator)
    await coordinator.tick(site(at(6, 5, 59)))
    assert mode(app) == 'manual' and seen[-1].mode == 'manual'
    batch = await coordinator.tick(site(at(6, 6)))
    assert mode(app) == 'planned' and seen[-1].mode == 'planned' and seen[-1].grid_blocked
    assert 'device' not in app.state.store.get('manual_controls', {})
    assert [c.action for c in batch.commands if c.device_id == 'device'] == ['suspend']
    ended = kinds(app, 'manual_ended')
    assert [(e['device_id'], e['details']) for e in ended] == [('device', {'reason': 'Heures pleines rouges', 'cause': 'tempo_red_peak'})]
    assert said(app) == [('INFO', CUT)]
    assert [e['details'] for e in kinds(app, 'tempo_red_peak')] == [START]
    # Nothing more is recorded until the next transition.
    await coordinator.tick(site(at(6, 6, 1)))
    await coordinator.tick(site(at(6, 12)))
    assert len(kinds(app, 'manual_ended')) == 1 and len(kinds(app, 'tempo_red_peak')) == 1
    assert journal(app) == [('INFO', 'Heures pleines rouges : réseau coupé en automatique')]
    await coordinator.tick(site(at(6, 22)))
    assert [e['details'] for e in kinds(app, 'tempo_red_peak')] == [END, START]
    assert journal(app) == [('INFO', 'Heures pleines rouges : réseau coupé en automatique'),
                            ('INFO', 'Fin des heures pleines rouges')]


async def test_manual_started_during_red_peak_survives(tmp_path):
    app, _ = setup(tmp_path)
    coordinator = app.state.coordinator
    seen = spy(coordinator)
    await coordinator.tick(site(at(6, 9)))
    assert coordinator.red_peak_active
    settings = app.state.store.load_settings(); settings['devices'][0]['mode'] = 'manual'
    app.state.store.save_settings(settings)
    app.state.store.set('manual_controls', {'device': {'until': (at(6, 10) + timedelta(hours=4)).isoformat(),
                                                       'previous_mode': 'planned'}})
    batch = await coordinator.tick(site(at(6, 10, 5)))
    assert mode(app) == 'manual' and seen[-1].mode == 'manual'
    assert seen[-1].grid_blocked and coordinator.engine.network_allowed['device'] is True
    assert not any(c.action == 'suspend' for c in batch.commands)
    assert batch.reasons['device'] != 'Jour rouge, heures pleines : solaire seul'
    assert not kinds(app, 'manual_ended')
    # A restart, before Home Assistant answers again, neither ends it nor records a new start.
    restarted = Coordinator(app.state.store)
    seen = spy(restarted)
    await restarted.tick(site(at(6, 10, 10), color=None))
    assert restarted.red_peak_active and mode(app) == 'manual' and seen[-1].grid_blocked
    assert restarted.public_state()['tempo'] == {'configured': True, 'color': 'rouge', 'red_peak': True, 'unknown': False}
    assert len(kinds(app, 'tempo_red_peak')) == 1 and not kinds(app, 'manual_ended')


async def test_car_manual_expires_after_duration(tmp_path):
    app, client = setup(tmp_path)
    for minutes in (0, 30, 90, 780, -60):
        response = client.post('/api/v1/devices/device/manual', json={'duration_minutes': minutes})
        assert response.status_code == 409 and response.json()['detail'] == 'Durée de 1 h à 12 h'
    assert mode(app) == 'planned'
    start = utcnow()
    response = client.post('/api/v1/devices/device/manual', json={'duration_minutes': 60})
    assert response.status_code == 200
    until = datetime.fromisoformat(response.json()['until'])
    assert timedelta(minutes=59) < until - start < timedelta(minutes=61)
    event = kinds(app, 'manual')[0]['details']
    assert event == {'duration_minutes': 60, 'origin': 'web'}
    coordinator = app.state.coordinator
    assert coordinator.public_state()['devices'][0]['manual_until'] == response.json()['until']
    await coordinator.tick(site(until - timedelta(minutes=1), color='Bleu'))
    assert mode(app) == 'manual'
    await coordinator.tick(site(until + timedelta(seconds=1), color='Bleu'))
    assert mode(app) == 'planned' and 'device' not in app.state.store.get('manual_controls', {})
    assert coordinator.public_state()['devices'][0]['manual_until'] is None
    await coordinator.tick(site(until + timedelta(seconds=3), color='Bleu'))
    assert [(e['device_id'], e['details']) for e in kinds(app, 'manual_ended')] == [('device', {'reason': 'Durée écoulée'})]
    assert said(app) == [('INFO', 'Fin de la durée du mode Manuel, retour en automatique')]


def test_car_manual_defaults_to_four_hours_and_heater_to_thirty_minutes(tmp_path):
    app, client = setup(tmp_path)
    start = utcnow()
    until = datetime.fromisoformat(client.post('/api/v1/devices/device/manual', json={}).json()['until'])
    assert timedelta(minutes=239) < until - start < timedelta(minutes=241)
    assert kinds(app, 'manual')[0]['details']['duration_minutes'] == 240
    app, client = setup(tmp_path / 'tank', kind='water_heater', mode='off_peak_solar')
    start = utcnow()
    until = datetime.fromisoformat(client.post('/api/v1/devices/device/manual', json={}).json()['until'])
    assert timedelta(minutes=29) < until - start < timedelta(minutes=31)
    assert client.post('/api/v1/devices/device/manual', json={'duration_minutes': 721}).status_code == 409
    assert client.post('/api/v1/devices/device/manual', json={'duration_minutes': 0}).status_code == 409


async def test_legacy_persistent_car_manual_gets_12h_end(tmp_path):
    app, _ = setup(tmp_path, mode='manual')
    app.state.store.set('manual_controls', {'device': {'until': None, 'previous_mode': 'planned'}})
    coordinator = app.state.coordinator
    now = at(6, 14)
    await coordinator.tick(site(now, color='Bleu'))
    entry = app.state.store.get('manual_controls')['device']
    assert datetime.fromisoformat(entry['until']) == now + timedelta(hours=12)
    assert entry['previous_mode'] == 'planned' and mode(app) == 'manual'
    await coordinator.tick(site(now + timedelta(hours=1), color='Bleu'))
    assert app.state.store.get('manual_controls')['device'] == entry   # saved once
    await coordinator.tick(site(now + timedelta(hours=12, seconds=1), color='Bleu'))
    assert mode(app) == 'planned'


async def test_tempo_disabled_keeps_previous_behaviour(tmp_path):
    app, _ = setup(tmp_path, entity='')
    coordinator = app.state.coordinator
    seen = spy(coordinator)
    await coordinator.tick(site(at(6, 10)))
    assert coordinator.public_state()['tempo'] == {'configured': False, 'color': None, 'red_peak': False, 'unknown': False}
    policy = seen[-1]
    assert (policy.grid_blocked, policy.import_tolerance_w, policy.stop_delay_s) == (False, 500, 180)
    assert not kinds(app, 'tempo_red_peak') and journal(app) == []


async def test_unknown_colour_after_6am_lifts_restriction(tmp_path):
    app, _ = setup(tmp_path)
    coordinator = app.state.coordinator
    seen = spy(coordinator)
    await coordinator.tick(site(at(6, 10)))
    for color in ('unavailable', None, 'Violet'):
        await coordinator.tick(site(at(6, 15), color=color))
        assert coordinator.red_peak_active and seen[-1].grid_blocked
    assert coordinator.public_state()['tempo'] == {'configured': True, 'color': 'rouge', 'red_peak': True, 'unknown': False}
    await coordinator.tick(site(at(7, 5, 59), color='unavailable'))
    assert not coordinator.red_peak_active
    await coordinator.tick(site(at(7, 6), color='unavailable'))
    await coordinator.tick(site(at(7, 6, 1), color='unavailable'))
    assert coordinator.public_state()['tempo'] == {'configured': True, 'color': None, 'red_peak': False, 'unknown': True}
    assert not seen[-1].grid_blocked and seen[-1].import_tolerance_w == 500
    assert journal(app).count(('WARN', 'Couleur Tempo inconnue')) == 1
    await coordinator.tick(site(at(7, 6, 2), color='Bleu'))
    assert coordinator.public_state()['tempo']['unknown'] is False
    await coordinator.tick(site(at(7, 6, 3), color='unknown'))
    assert journal(app).count(('WARN', 'Couleur Tempo inconnue')) == 1   # Bleu is kept for the day


def test_public_state_before_any_tick(tmp_path):
    app, _ = setup(tmp_path)
    assert Coordinator(app.state.store).public_state()['tempo'] == {'configured': True, 'color': None, 'red_peak': False, 'unknown': False}
    app, _ = setup(tmp_path / 'off', entity='')
    assert Coordinator(app.state.store).public_state()['tempo']['configured'] is False


def saved_tempo(app, day, read_at):
    value = {'color': 'rouge', 'read_at': read_at.isoformat(), 'until': next_tempo_day_start(read_at, 'Europe/Paris').isoformat(),
             'red_peak': True} | ({'day': day.isoformat()} if day else {})
    app.state.store.set('tempo', value)


async def test_red_peak_start_missed_during_downtime_still_ends_manual(tmp_path):
    # Stopped during a red peak, restarted the next red morning: the flag alone looks unchanged.
    app, _ = setup(tmp_path, mode='manual')
    app.state.store.set('manual_controls', {'device': {'until': (at(7, 5) + timedelta(hours=4)).isoformat(),
                                                       'previous_mode': 'planned'}})
    saved_tempo(app, day=at(7, 6), read_at=at(6, 21))
    restarted = Coordinator(app.state.store)
    assert restarted.red_peak_active
    await restarted.tick(site(at(7, 7), changed=at(7, 6) + timedelta(seconds=19)))
    assert mode(app) == 'planned' and 'device' not in app.state.store.get('manual_controls', {})
    assert [e['details'] for e in kinds(app, 'tempo_red_peak')] == [START]
    assert said(app) == [('INFO', CUT)]
    assert app.state.store.get('tempo')['day'] == at(8, 6).isoformat()


async def test_saved_state_without_day_counts_as_the_current_day(tmp_path):
    # First tick after the upgrade: a Manual confirmed just before it is kept.
    app, _ = setup(tmp_path, mode='manual')
    app.state.store.set('manual_controls', {'device': {'until': (at(6, 9) + timedelta(hours=4)).isoformat(),
                                                       'previous_mode': 'planned'}})
    saved_tempo(app, day=None, read_at=at(6, 9))
    restarted = Coordinator(app.state.store)
    await restarted.tick(site(at(6, 10)))
    assert restarted.red_peak_active and mode(app) == 'manual'
    assert not kinds(app, 'tempo_red_peak') and not kinds(app, 'manual_ended')
    assert app.state.store.get('tempo')['day'] == at(7, 6).isoformat()


async def test_manual_after_pause_ends_in_automatic(tmp_path):
    app, client = setup(tmp_path, mode='solar')
    assert client.post('/api/v1/devices/device/pause').status_code == 200
    until = datetime.fromisoformat(client.post('/api/v1/devices/device/manual', json={'duration_minutes': 60}).json()['until'])
    assert app.state.store.get('manual_controls')['device']['previous_mode'] == 'off'
    await app.state.coordinator.tick(site(until + timedelta(seconds=1), color='Bleu'))
    assert mode(app) == 'solar'


async def test_manual_after_pause_cut_by_red_peak_ends_in_automatic(tmp_path):
    app, client = setup(tmp_path)
    assert client.post('/api/v1/devices/device/pause').status_code == 200
    assert client.post('/api/v1/devices/device/manual', json={'duration_minutes': 60}).status_code == 200
    app.state.store.set('manual_controls', {'device': {'until': (at(6, 5) + timedelta(hours=4)).isoformat(),
                                                       'previous_mode': 'off'}})
    coordinator = app.state.coordinator
    await coordinator.tick(site(at(6, 5, 59)))
    assert mode(app) == 'manual'
    await coordinator.tick(site(at(6, 6)))
    assert mode(app) == 'planned'


async def test_manual_confirmed_during_red_peak_is_recorded(tmp_path):
    app, client = setup(tmp_path)
    assert client.post('/api/v1/devices/device/manual', json={'duration_minutes': 60}).status_code == 200
    assert 'reason' not in kinds(app, 'manual')[0]['details'] and said(app) == []
    await app.state.coordinator.tick(site(at(6, 9)))
    assert client.post('/api/v1/devices/device/manual', json={'duration_minutes': 120}).status_code == 200
    assert kinds(app, 'manual')[0]['details'] == {'duration_minutes': 120, 'origin': 'web',
                                                  'reason': 'Confirmé : jour rouge, heures pleines'}
    assert said(app) == [('INFO', CUT), ('INFO', 'Manuel confirmé pendant les heures pleines rouges')]   # the first one was cut


async def test_stale_red_reading_at_6am_is_ignored(tmp_path):
    # Red day then blue day: at 06:00:05 Home Assistant still shows yesterday's « Rouge ».
    app, _ = setup(tmp_path)
    coordinator = app.state.coordinator
    seen = spy(coordinator)
    yesterday = at(6, 6) + timedelta(seconds=19)
    await coordinator.tick(site(at(6, 10), changed=yesterday))
    await coordinator.tick(site(at(6, 22), changed=yesterday))
    assert not coordinator.red_peak_active
    settings = app.state.store.load_settings(); settings['devices'][0]['mode'] = 'manual'
    app.state.store.save_settings(settings)
    app.state.store.set('manual_controls', {'device': {'until': (at(7, 5) + timedelta(hours=4)).isoformat(),
                                                       'previous_mode': 'planned'}})
    await coordinator.tick(site(at(7, 6) + timedelta(seconds=5), changed=yesterday))
    assert not coordinator.red_peak_active and not seen[-1].grid_blocked and mode(app) == 'manual'
    assert coordinator.public_state()['tempo'] == {'configured': True, 'color': None, 'red_peak': False, 'unknown': False}
    await coordinator.tick(site(at(7, 6) + timedelta(seconds=19), color='Bleu', changed=at(7, 6) + timedelta(seconds=19)))
    assert coordinator.tempo_color == 'bleu' and not coordinator.red_peak_active and mode(app) == 'manual'
    assert [e['details'] for e in kinds(app, 'tempo_red_peak')] == [END, START]   # newest first
    assert not kinds(app, 'manual_ended') and ('WARN', 'Couleur Tempo inconnue') not in journal(app)


async def test_second_red_day_starts_after_two_minutes(tmp_path):
    # Red day after red day: Home Assistant keeps yesterday's last_changed.
    app, _ = setup(tmp_path)
    coordinator = app.state.coordinator
    yesterday = at(6, 6) + timedelta(seconds=19)
    await coordinator.tick(site(at(6, 21), changed=yesterday))
    await coordinator.tick(site(at(6, 23), changed=yesterday))
    await coordinator.tick(site(at(7, 6, 1), changed=yesterday))
    await coordinator.tick(site(at(7, 6, 1) + timedelta(seconds=59), changed=yesterday))
    assert not coordinator.red_peak_active
    await coordinator.tick(site(at(7, 6, 2), changed=yesterday))
    assert coordinator.red_peak_active
    assert [e['details'] for e in kinds(app, 'tempo_red_peak')] == [START, END, START]


async def test_fresh_red_reading_applies_at_once(tmp_path):
    app, _ = setup(tmp_path)
    coordinator = app.state.coordinator
    await coordinator.tick(site(at(6, 21), color='Bleu', changed=at(6, 6) + timedelta(seconds=19)))
    await coordinator.tick(site(at(7, 6) + timedelta(seconds=19), changed=at(7, 6) + timedelta(seconds=19)))
    assert coordinator.red_peak_active
