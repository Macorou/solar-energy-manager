from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import sqlite3

from app.main import create_app
from app.settings import RuntimeSettings
from app.storage.database import SQLiteStore


def authenticated(tmp_path):
    app = create_app(RuntimeSettings(data_dir=tmp_path))
    client = TestClient(app)
    assert client.post('/api/v1/setup', json={'token': (tmp_path/'bootstrap-token').read_text(),
        'username': 'admin', 'password': 'a-secure-test-password'}).status_code == 200
    return app, client


def test_logs_and_export_require_authentication(tmp_path):
    client = TestClient(create_app(RuntimeSettings(data_dir=tmp_path)))
    assert client.get('/api/v1/logs').status_code == 401
    assert client.get('/api/v1/logs/export').status_code == 401


def test_filters_intersect_and_unknown_search_is_literal(tmp_path):
    app, client = authenticated(tmp_path)
    log = app.state.store.journal
    log.write('DEBUG', 'ha', 'Puissance réseau : 834 W')
    log.write('ERROR', 'ocpp:wallbox', 'MeterValues : timeout')
    log.write('WARN', 'ha', 'Connexion interrompue')
    log.write('TRACE', 'ha', 'Mesure détaillée')
    data = client.get('/api/v1/logs', params={'level': 'WARN', 'area': 'ha', 'search': 'CONNEXION'}).json()
    assert [r['message'] for r in data['entries']] == ['Connexion interrompue']
    assert {'ha', 'ocpp:wallbox'} <= set(data['areas'])
    assert client.get('/api/v1/logs', params={'level': 'TRACE', 'search': "%' OR 1=1 --"}).json()['entries'] == []
    assert client.get('/api/v1/logs', params={'level': 'NOPE'}).status_code == 422
    assert client.get('/api/v1/logs', params={'limit': 501}).status_code == 422


def test_incremental_cursor_and_older_pages_have_no_duplicates(tmp_path):
    app, client = authenticated(tmp_path)
    log = app.state.store.journal
    for i in range(7):
        log.write('INFO', 'ocpp', f'Status {i}')
    first = client.get('/api/v1/logs', params={'limit': 3}).json()
    assert [e['message'] for e in first['entries']] == ['Status 4', 'Status 5', 'Status 6']
    assert first['has_older']
    older = client.get('/api/v1/logs', params={'before': first['entries'][0]['id'], 'limit': 3}).json()
    assert [e['message'] for e in older['entries']] == ['Status 1', 'Status 2', 'Status 3']
    log.write('DEBUG', 'ha', 'Not selected')
    empty = client.get('/api/v1/logs', params={'after': first['cursor'], 'area': 'ocpp'}).json()
    assert not empty['entries'] and empty['cursor'] > first['cursor']
    for i in range(4):
        log.write('ERROR', 'ocpp', f'Failure {i}')
    next_page = client.get('/api/v1/logs', params={'after': empty['cursor'], 'limit': 2}).json()
    assert [e['message'] for e in next_page['entries']] == ['Failure 0', 'Failure 1']
    assert next_page['has_more']
    last = client.get('/api/v1/logs', params={'after': next_page['cursor'], 'limit': 2}).json()
    assert [e['message'] for e in last['entries']] == ['Failure 2', 'Failure 3']
    assert not last['has_more']


def test_redaction_happens_before_persistence_and_download(tmp_path):
    app, client = authenticated(tmp_path)
    app.state.secrets.set('ocpp_wallbox', 'Kelly-example-secret')
    app.state.store.journal.write('ERROR', 'ocpp:wallbox',
        'password=other-secret Authorization: Basic d2FsbGJveDpzZWNyZXQ=\n'
        'Bearer abc.def.token https://user:pass@host/path?access_token=hidden&x=1 '
        'Kelly-example-secret token="another value" idTag=rfid-secret VIN=VF3PRIVATE12345678')
    raw = sqlite3.connect(tmp_path/'app.db').execute('SELECT message FROM diagnostic_logs').fetchone()[0]
    exported = client.get('/api/v1/logs/export', params={'level': 'TRACE'}).text
    for secret in ('other-secret', 'd2FsbGJveDpzZWNyZXQ=', 'abc.def.token', 'user:pass', 'hidden',
                   'Kelly-example-secret', 'another value', 'rfid-secret', 'VF3PRIVATE12345678'):
        assert secret not in raw and secret not in exported
    assert '[masqué]' in exported
    assert client.get('/api/v1/logs/export', params={'area': 'missing'}).text.count('ERROR') == 0


def test_retention_survives_reopen_and_does_not_modify_events(tmp_path):
    store = SQLiteStore(tmp_path/'app.db')
    store.append_event({'kind': 'manual', 'device_id': 'car', 'details': {'action': 'start'}})
    old = (datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
    with store.connection() as db:
        db.execute('INSERT INTO diagnostic_logs(at,level,area,message) VALUES(?,?,?,?)',
                   (old, 'INFO', 'old', 'expired'))
        db.executemany('INSERT INTO diagnostic_logs(at,level,area,message) VALUES(?,?,?,?)',
            [(datetime.now(timezone.utc).isoformat(), 'INFO', 'test', str(i)) for i in range(10005)])
    # Purges run in batches; the first write of a reopened store always purges.
    store = SQLiteStore(tmp_path/'app.db')
    store.journal.write('INFO', 'system', 'reopened')
    store.backup(tmp_path/'backup.db')
    reopened = SQLiteStore(tmp_path/'backup.db')
    with reopened.connection() as db:
        assert db.execute('SELECT count(*) FROM diagnostic_logs').fetchone()[0] == 10000
        assert db.execute("SELECT count(*) FROM diagnostic_logs WHERE area='old'").fetchone()[0] == 0
    assert reopened.events()[0]['details']['action'] == 'start'


def test_diagnostics_failure_cannot_break_a_control_event(tmp_path, monkeypatch):
    store = SQLiteStore(tmp_path/'app.db')
    store.journal.write('INFO', 'system', 'before')
    # A locked/missing diagnostic table must not propagate into the controller.
    with store.connection() as db:
        db.execute('DROP TABLE diagnostic_logs')
    store.journal.write('ERROR', 'system', 'unavailable')
    store.append_event({'kind': 'command_accepted', 'device_id': 'car', 'details': {}})
    assert store.events()[0]['kind'] == 'command_accepted'


def test_registering_redaction_does_not_make_unrelated_corrupt_credentials_block_startup(tmp_path):
    from app.storage.secrets import SecretStore
    from cryptography.fernet import InvalidToken
    import pytest
    store=SQLiteStore(tmp_path/'app.db')
    secrets=SecretStore(store,tmp_path/'master.key')
    secrets.set('good','private-good')
    with store.connection() as db:
        db.execute('INSERT INTO secrets VALUES(?,?)',('corrupt',b'not-encrypted'))
    reopened=SecretStore(store,tmp_path/'master.key',True)
    assert reopened.get('good')=='private-good'
    with pytest.raises(InvalidToken):reopened.get('corrupt')


def test_retention_gaps_and_missing_table_are_explicit(tmp_path):
    app,client=authenticated(tmp_path)
    log=app.state.store.journal
    for i in range(6):log.write('INFO','ha',str(i))
    with app.state.store.connection() as db:db.execute('DELETE FROM diagnostic_logs WHERE id <= 3')
    page=client.get('/api/v1/logs',params={'after':1}).json()
    assert page['gap'] and len(page['entries'])==3
    with app.state.store.connection() as db:db.execute('DROP TABLE diagnostic_logs')
    assert client.get('/api/v1/logs').status_code==503


def test_short_normal_database_read_does_not_drop_a_communication_log(tmp_path):
    from threading import Thread, Event
    import time
    store=SQLiteStore(tmp_path/'app.db')
    held=Event()
    def read():
        with store.lock:
            held.set()
            time.sleep(.015)
    reader=Thread(target=read)
    reader.start();held.wait()
    store.journal.write('INFO','ocpp','Connexion établie')
    reader.join()
    assert store.journal.query()['entries'][0]['message']=='Connexion établie'
