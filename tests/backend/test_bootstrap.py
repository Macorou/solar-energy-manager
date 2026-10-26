from fastapi.testclient import TestClient


def service(tmp_path):
    from app.main import create_app
    from app.settings import RuntimeSettings
    app = create_app(RuntimeSettings(data_dir=tmp_path))
    return app, TestClient(app)


def setup(client, path):
    return client.post('/api/v1/setup', json={
        'token': (path / 'bootstrap-token').read_text(),
        'username': 'admin', 'password': 'a-secure-test-password'})


def test_bootstrap_is_one_time_and_settings_require_auth(tmp_path):
    app, client = service(tmp_path)
    assert client.get('/api/v1/settings').status_code == 401
    assert setup(client, tmp_path).status_code == 200
    assert setup(client, tmp_path).status_code == 409
    assert client.get('/api/v1/settings').status_code == 200
    assert client.post('/api/v1/auth/logout').status_code == 200
    assert client.get('/api/v1/settings').status_code == 401


def test_setup_rejects_wrong_token_and_login_wrong_password(tmp_path):
    app, client = service(tmp_path)
    assert client.post('/api/v1/setup', json={'token': 'wrong', 'username': 'admin',
        'password': 'a-secure-test-password'}).status_code == 403
    assert setup(client, tmp_path).status_code == 200
    client.post('/api/v1/auth/logout')
    assert client.post('/api/v1/auth/login', json={'username': 'admin',
        'password': 'incorrect'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'username': 'admin',
        'password': 'a-secure-test-password'}).status_code == 200


def test_cookie_session_cannot_mutate_from_another_origin(tmp_path):
    app, client = service(tmp_path)
    setup(client, tmp_path)
    response = client.put('/api/v1/settings', json={},
        headers={'Origin': 'https://attacker.example'})
    assert response.status_code == 403

