import hashlib
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

DAY = 86400
CHROME_WINDOWS = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
SAFARI_IPHONE = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 '
                 '(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')


@pytest.fixture
def clock(monkeypatch):
    import app.api.auth as auth
    now = SimpleNamespace(value=1_800_000_000.0)
    monkeypatch.setattr(auth, 'time', SimpleNamespace(time=lambda: now.value))
    return now


@pytest.fixture
def app(tmp_path):
    from app.main import create_app
    from app.settings import RuntimeSettings
    return create_app(RuntimeSettings(data_dir=tmp_path))


def client(app, agent=CHROME_WINDOWS):
    return TestClient(app, headers={'User-Agent': agent})


def setup(app, tmp_path, agent=CHROME_WINDOWS):
    c = client(app, agent)
    assert c.post('/api/v1/setup', json={'token': (tmp_path / 'bootstrap-token').read_text(),
        'username': 'admin', 'password': 'a-secure-test-password'}).status_code == 200
    return c


def login(app, agent):
    c = client(app, agent)
    assert c.post('/api/v1/auth/login', json={'username': 'admin',
        'password': 'a-secure-test-password'}).status_code == 200
    return c


def expiry(app, c):
    hashed = hashlib.sha256(c.cookies['sem_session'].encode()).hexdigest()
    with app.state.store.connection() as db:
        return db.execute('SELECT expires FROM sessions WHERE token_hash=?', (hashed,)).fetchone()['expires']


def test_login_cookie_lasts_thirty_days(app, tmp_path, clock):
    response = client(app).post('/api/v1/setup', json={'token': (tmp_path / 'bootstrap-token').read_text(),
        'username': 'admin', 'password': 'a-secure-test-password'})
    cookie = response.headers['set-cookie']
    assert 'Max-Age=2592000' in cookie and 'HttpOnly' in cookie and 'SameSite=strict' in cookie


def test_session_slides_while_used_and_expires_after_thirty_idle_days(app, tmp_path, clock):
    c = setup(app, tmp_path)
    start = clock.value
    clock.value = start + 20 * DAY
    response = c.get('/api/v1/settings')
    assert response.status_code == 200
    assert 'Max-Age=2592000' in response.headers['set-cookie']
    assert expiry(app, c) == clock.value + 30 * DAY
    clock.value = start + 45 * DAY
    assert c.get('/api/v1/settings').status_code == 200
    clock.value = start + 76 * DAY
    assert c.get('/api/v1/settings').status_code == 401


def test_session_is_renewed_at_most_once_an_hour(app, tmp_path, clock):
    c = setup(app, tmp_path)
    before = expiry(app, c)
    clock.value += 600
    response = c.get('/api/v1/settings')
    assert response.status_code == 200 and 'set-cookie' not in response.headers
    assert expiry(app, c) == before


def test_lists_connected_devices_with_current_marker(app, tmp_path, clock):
    computer = setup(app, tmp_path)
    clock.value += 2 * 3600
    phone = login(app, SAFARI_IPHONE)
    devices = computer.get('/api/v1/auth/sessions').json()
    assert [d['device'] for d in devices] == ['Safari · iPhone', 'Chrome · Windows']
    assert [d['current'] for d in devices] == [False, True]
    assert all(d['created_at'] and d['last_seen_at'] and d['id'] for d in devices)
    assert 'token' not in str(devices) and computer.cookies['sem_session'] not in str(devices)
    assert phone.get('/api/v1/auth/sessions').json()[0]['current'] is True


def test_revoking_a_device_disconnects_it_and_is_journaled(app, tmp_path, clock):
    computer = setup(app, tmp_path)
    phone = login(app, SAFARI_IPHONE)
    target = next(d for d in computer.get('/api/v1/auth/sessions').json() if not d['current'])
    assert computer.delete('/api/v1/auth/sessions/' + target['id']).status_code == 200
    assert phone.get('/api/v1/settings').status_code == 401
    assert computer.get('/api/v1/settings').status_code == 200
    assert len(computer.get('/api/v1/auth/sessions').json()) == 1
    assert computer.delete('/api/v1/auth/sessions/' + target['id']).status_code == 404
    messages = [row['message'] for row in app.state.store.journal.query(areas=['auth'])['entries']]
    assert any('Appareil déconnecté : Safari · iPhone' in m for m in messages)


def test_revoke_others_keeps_only_current_device(app, tmp_path, clock):
    computer = setup(app, tmp_path)
    phone, tablet = login(app, SAFARI_IPHONE), login(app, 'curl/8.0')
    assert computer.post('/api/v1/auth/sessions/revoke-others').json() == {'revoked': 2}
    assert phone.get('/api/v1/settings').status_code == 401
    assert tablet.get('/api/v1/settings').status_code == 401
    assert [d['current'] for d in computer.get('/api/v1/auth/sessions').json()] == [True]


def test_session_from_previous_release_is_extended_and_listed(app, tmp_path, clock):
    c = client(app)
    setup(app, tmp_path)
    token = 'previous-release-token'
    with app.state.store.connection() as db:
        db.execute('INSERT INTO sessions VALUES(?,?)',
            (hashlib.sha256(token.encode()).hexdigest(), clock.value + 3600))
    c.cookies.set('sem_session', token, domain='testserver.local')
    devices = c.get('/api/v1/auth/sessions').json()
    assert expiry(app, c) == clock.value + 30 * DAY
    assert next(d for d in devices if d['current'])['device'] == 'Chrome · Windows'


def test_logout_forgets_the_device(app, tmp_path, clock):
    computer = setup(app, tmp_path)
    phone = login(app, SAFARI_IPHONE)
    assert phone.post('/api/v1/auth/logout').status_code == 200
    assert [d['device'] for d in computer.get('/api/v1/auth/sessions').json()] == ['Chrome · Windows']
    with app.state.store.connection() as db:
        assert db.execute('SELECT count(*) FROM session_info').fetchone()[0] == 1


def test_sessions_table_keeps_previous_release_layout(app, tmp_path, clock):
    # An older release inserts two values into sessions; rolling back must keep login working.
    setup(app, tmp_path)
    with app.state.store.connection() as db:
        db.execute('INSERT INTO sessions VALUES(?,?)', ('older-release', clock.value))


def test_device_labels():
    from app.api.auth import describe_agent
    assert describe_agent(CHROME_WINDOWS) == 'Chrome · Windows'
    assert describe_agent(SAFARI_IPHONE) == 'Safari · iPhone'
    assert describe_agent('Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) Gecko/20100101 Firefox/131.0') == 'Firefox · macOS'
    assert describe_agent('Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile Safari/537.36 EdgA/130.0') == 'Edge · Android'
    assert describe_agent('Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36 Edg/130.0') == 'Edge · Windows'
    assert describe_agent('Home Assistant/2026.10 (io.robbie.HomeAssistant; build:1; iOS 18.0)') == 'Home Assistant · iOS'
    assert describe_agent('curl/8.0') == 'Appareil inconnu'
    assert describe_agent('') == 'Appareil inconnu'
