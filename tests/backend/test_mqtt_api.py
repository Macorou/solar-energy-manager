import json
from test_bootstrap import service, setup

PASSWORD = 'p@ss:w/rd#é'
CONFIG = {'broker': 'mqtt.local:1883', 'topic': 'sem', 'username': 'sem'}


class StubMqtt:
    def __init__(self, remove_result=True, test_error=None):
        self.calls, self.remove_result, self.test_error = [], remove_result, test_error

    async def test(self, config, password):
        self.calls.append(('test', config, password))
        if self.test_error: raise ValueError(self.test_error)

    async def remove(self, config, password):
        self.calls.append(('remove', config, password))
        return self.remove_result

    def status(self):
        return {'state': 'connected', 'last_publish_at': '2026-11-01T10:00:00+00:00', 'error': None}


def ready(tmp_path, **kwargs):
    app, client = service(tmp_path)
    setup(client, tmp_path)
    app.state.mqtt = StubMqtt(**kwargs)
    return app, client


def test_put_saves_config_and_password_never_returned(tmp_path):
    app, client = ready(tmp_path)
    response = client.put('/api/v1/connections/mqtt', json={'config': CONFIG, 'password': PASSWORD})
    assert response.status_code == 200
    assert response.json() == {'ok': True, 'entities_removed': None}
    assert PASSWORD not in response.text
    settings = client.get('/api/v1/settings')
    assert settings.json()['mqtt']['broker'] == 'mqtt.local:1883'
    assert PASSWORD not in settings.text and 'password' not in json.dumps(settings.json()['mqtt'])
    assert app.state.secrets.get('mqtt_password') == PASSWORD
    export = client.get('/api/v1/logs/export')
    assert export.status_code == 200 and PASSWORD not in export.text
    assert PASSWORD not in json.dumps(app.state.store.journal.query(limit=500)['entries'])


def test_put_without_password_keeps_the_stored_one(tmp_path):
    app, client = ready(tmp_path)
    client.put('/api/v1/connections/mqtt', json={'config': CONFIG, 'password': PASSWORD})
    assert client.put('/api/v1/connections/mqtt', json={'config': {**CONFIG, 'topic': 'home'}}).status_code == 200
    assert app.state.secrets.get('mqtt_password') == PASSWORD


def test_put_rejects_invalid_topic(tmp_path):
    app, client = ready(tmp_path)
    response = client.put('/api/v1/connections/mqtt', json={'config': {**CONFIG, 'topic': 'a/#'}})
    assert response.status_code == 422
    assert client.get('/api/v1/settings').json()['mqtt']['broker'] == ''


def test_put_disabling_removes_entities(tmp_path):
    app, client = ready(tmp_path)
    client.put('/api/v1/connections/mqtt', json={'config': CONFIG, 'password': PASSWORD})
    response = client.put('/api/v1/connections/mqtt', json={'config': {**CONFIG, 'topic': ''}})
    assert response.status_code == 200 and response.json() == {'ok': True, 'entities_removed': True}
    removes = [call for call in app.state.mqtt.calls if call[0] == 'remove']
    assert len(removes) == 1
    assert removes[0][1].broker == 'mqtt.local:1883' and removes[0][1].topic == 'sem'
    assert removes[0][2] == PASSWORD
    assert client.get('/api/v1/settings').json()['mqtt']['topic'] == ''


def test_put_without_previous_enabled_config_does_not_remove(tmp_path):
    app, client = ready(tmp_path)
    response = client.put('/api/v1/connections/mqtt', json={'config': {**CONFIG, 'topic': ''}})
    assert response.json() == {'ok': True, 'entities_removed': None}
    assert app.state.mqtt.calls == []


def test_test_endpoint_uses_stored_password_and_reports_french_error(tmp_path):
    app, client = ready(tmp_path)
    app.state.secrets.set('mqtt_password', PASSWORD)
    response = client.post('/api/v1/connections/mqtt/test', json={'config': CONFIG})
    assert response.status_code == 200 and response.json() == {'ok': True}
    kind, config, password = app.state.mqtt.calls[-1]
    assert kind == 'test' and config.broker == 'mqtt.local:1883' and password == PASSWORD
    client.post('/api/v1/connections/mqtt/test', json={'config': CONFIG, 'password': 'typed'})
    assert app.state.mqtt.calls[-1][2] == 'typed'
    app.state.mqtt.test_error = 'Courtier injoignable'
    failed = client.post('/api/v1/connections/mqtt/test', json={'config': CONFIG})
    assert failed.status_code == 400 and failed.json()['detail'] == 'Courtier injoignable'
    assert client.post('/api/v1/connections/mqtt/test',
                       json={'config': {**CONFIG, 'topic': 'a+b'}}).status_code == 422


def test_delete_clears_config_secret_and_reports_cleanup(tmp_path):
    app, client = ready(tmp_path, remove_result=False)
    client.put('/api/v1/connections/mqtt', json={'config': CONFIG, 'password': PASSWORD})
    response = client.delete('/api/v1/connections/mqtt')
    assert response.status_code == 200 and response.json() == {'ok': True, 'entities_removed': False}
    kind, config, password = app.state.mqtt.calls[-1]
    assert kind == 'remove' and config.broker == 'mqtt.local:1883' and password == PASSWORD
    assert client.get('/api/v1/settings').json()['mqtt']['broker'] == ''
    assert not app.state.secrets.present('mqtt_password')


def test_status_endpoint(tmp_path):
    app, client = ready(tmp_path)
    response = client.get('/api/v1/connections/mqtt/status')
    assert response.status_code == 200 and response.json() == app.state.mqtt.status()


def test_connections_reports_mqtt(tmp_path):
    app, client = ready(tmp_path)
    assert client.get('/api/v1/connections').json()['mqtt'] is False
    client.put('/api/v1/connections/mqtt', json={'config': CONFIG})
    assert client.get('/api/v1/connections').json()['mqtt'] is True


def test_mqtt_endpoints_require_auth(tmp_path):
    app, client = service(tmp_path)
    assert client.get('/api/v1/connections/mqtt/status').status_code == 401
    assert client.put('/api/v1/connections/mqtt', json={'config': CONFIG}).status_code == 401
    assert client.delete('/api/v1/connections/mqtt').status_code == 401


def test_delete_reports_no_cleanup_attempt_as_null(tmp_path):
    app, client = ready(tmp_path, remove_result=None)
    response = client.delete('/api/v1/connections/mqtt')
    assert response.status_code == 200 and response.json() == {'ok': True, 'entities_removed': None}
