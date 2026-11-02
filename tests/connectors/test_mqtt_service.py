import asyncio
import json
import ssl
import time
from contextlib import asynccontextmanager
import aiomqtt
import pytest
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode
from app.connectors.mqtt import service as service_module
from app.connectors.mqtt.service import MqttService
from app.domain.measurements import utcnow
from app.domain.site import SiteSnapshot
from app.runtime.coordinator import Coordinator
from app.settings import MqttConfig, SettingsDocument
from app.storage.database import SQLiteStore
from app.storage.secrets import SecretStore
from test_mqtt_entities import make_state

FAST = dict(interval=0.05, backoff=(0.05, 0.2), client_timeout=0.3)


class Broker:
    """Fake factory: records connections and messages, can fail, hang or inject incoming messages."""

    def __init__(self):
        self.sent, self.subscribed, self.connections = [], [], []
        self.error, self.hang, self.hang_exit = None, False, False
        self.incoming = asyncio.Queue()
        self.open, self.attempts = 0, []

    def factory(self, config, password, client_id, will_topic):
        broker = self

        class Client:
            async def publish(self, topic, payload, retain):
                if broker.hang: await asyncio.Event().wait()
                broker.sent.append((topic, payload, retain))

            async def subscribe(self, topic): broker.subscribed.append(topic)

            async def messages(self):
                while True:
                    item = await broker.incoming.get()
                    if item is None: return  # the stream ends
                    yield item

        @asynccontextmanager
        async def connect():
            broker.attempts.append(time.monotonic())
            if broker.error: raise broker.error
            broker.connections.append(dict(config=config, password=password, client_id=client_id, will_topic=will_topic))
            broker.open += 1
            try: yield Client()
            finally:
                if broker.hang_exit:  # a disconnect that never completes, once
                    broker.hang_exit = False
                    await asyncio.Event().wait()
                broker.open -= 1
        return connect()

    def on(self, topic): return [p for t, p, r in self.sent if t == topic]
    def config_topics(self): return [t for t, p, r in self.sent if t.endswith('/config') and p]


def setup(tmp_path, provider=None, **mqtt):
    store = SQLiteStore(tmp_path / 'db')
    secrets = SecretStore(store, tmp_path / 'secrets' / 'master.key')
    save(store, **mqtt)
    broker = Broker()
    service = MqttService(store, secrets, provider or (lambda: make_state()), broker.factory, **FAST)
    return store, secrets, broker, service


def save(store, **mqtt):
    store.save_settings(SettingsDocument(mqtt=MqttConfig(**mqtt)).model_dump(mode='json'))


async def until(check, timeout=3):
    end = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < end, 'condition not reached'
        await asyncio.sleep(0.01)


def test_mqtt_config_validation():
    assert MqttConfig(broker='192.168.1.30:1883').broker == '192.168.1.30:1883'
    for broker in ('host', 'host:0', 'host:70000', 'a b:1883', 'ho/st:1883', ':1883', 'host:abc'):
        with pytest.raises(ValueError, match='Courtier'): MqttConfig(broker=broker)
    for topic in ('sem/#', 'se+m', 'a b', '/sem', 'sem/'):
        with pytest.raises(ValueError, match='Sujet'): MqttConfig(topic=topic)
    for prefix in ('', 'home/#', '/homeassistant'):
        with pytest.raises(ValueError, match='découverte'): MqttConfig(discovery_prefix=prefix)
    for topic in ('evcc', 'evcc/x', 'EVCC', 'Evcc/x'):
        with pytest.raises(ValueError, match='EVCC'): MqttConfig(topic=topic)
    assert MqttConfig(topic='sem').topic == 'sem' and MqttConfig(topic='evccx').topic == 'evccx'
    assert MqttConfig(topic='sem/evcc').topic == 'sem/evcc'
    assert MqttConfig(topic='').topic == ''
    assert MqttConfig().enabled is False
    assert MqttConfig(broker='b:1883').enabled is True
    assert MqttConfig(broker='b:1883', topic='').enabled is False
    assert SettingsDocument().mqtt == MqttConfig()


async def test_disabled_when_broker_empty(tmp_path):
    _, _, broker, service = setup(tmp_path)
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'disabled')
        await asyncio.sleep(0.2)
        assert broker.connections == [] and service.status() == {
            'state': 'disabled', 'last_publish_at': None, 'error': None}
    finally: await service.stop()


async def test_connect_announces_and_publishes_online(tmp_path):
    _, secrets, broker, service = setup(tmp_path, broker='b:1883', username='u')
    secrets.set('mqtt_password', 'pw-secret')
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        await until(lambda: service.status()['last_publish_at'])
        assert broker.on('sem/status')[0] == 'online'
        assert broker.config_topics() and all(t.startswith('homeassistant/') for t in broker.config_topics())
        assert broker.subscribed == ['homeassistant/status']
        assert broker.on('sem/site/price/state') == ['0.123']
        connection = broker.connections[0]
        assert connection['client_id'].startswith('sem-') and connection['will_topic'] == 'sem/status'
        assert connection['password'] == 'pw-secret' and connection['config'].username == 'u'
        assert service.status()['error'] is None
    finally: await service.stop()
    assert broker.on('sem/status')[-1] == 'offline' and broker.open == 0
    assert service.status()['state'] == 'disabled'


async def test_client_id_is_stable_across_reconnections(tmp_path):
    store, _, broker, service = setup(tmp_path, broker='b:1883')
    await service.start()
    try:
        await until(lambda: len(broker.connections) == 1 and service.status()['state'] == 'connected')
        save(store, broker='b:1884')
        await until(lambda: len(broker.connections) == 2)
        assert broker.connections[0]['client_id'] == broker.connections[1]['client_id']
        save(store, broker='b:1884', client_id='fixed')
        await until(lambda: len(broker.connections) == 3)
        assert broker.connections[2]['client_id'] == 'fixed'
    finally: await service.stop()


async def test_reannounces_when_home_assistant_comes_back_online(tmp_path):
    _, _, broker, service = setup(tmp_path, broker='b:1883')
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        first = len(broker.config_topics())
        await broker.incoming.put(('homeassistant/status', 'offline'))
        await asyncio.sleep(0.2)
        assert len(broker.config_topics()) == first
        await broker.incoming.put(('homeassistant/status', 'online'))
        await until(lambda: len(broker.config_topics()) == 2 * first)
    finally: await service.stop()


async def test_reannounces_when_the_entity_set_changes(tmp_path):
    state = make_state()
    _, _, broker, service = setup(tmp_path, provider=lambda: state, broker='b:1883')
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        first = len(broker.config_topics())
        state['devices'] = state['devices'][:1]
        await until(lambda: len(broker.config_topics()) > first)
        again = len(broker.config_topics())
        await asyncio.sleep(0.3)
        assert len(broker.config_topics()) == again
    finally: await service.stop()


async def test_broker_down_sets_disconnected_and_control_loop_still_ticks(tmp_path):
    store, _, broker, service = setup(tmp_path, broker='b:1883')
    broker.error = OSError('down')
    coordinator = Coordinator(SQLiteStore(tmp_path / 'control'))
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'disconnected')
        assert service.status()['error'] == 'Courtier injoignable'
        for _ in range(5):
            await asyncio.wait_for(coordinator.tick(SiteSnapshot(utcnow())), 5)
            await asyncio.sleep(0.05)
        logs = store.journal.query(areas=('mqtt',))
        assert len([r for r in logs['entries'] if r['level'] == 'WARN']) == 1  # logged once, not per retry
        assert 'down' not in str(logs)
        broker.error = None
        await until(lambda: service.status()['state'] == 'connected')
        assert service.status()['error'] is None
    finally: await service.stop()


async def test_defaults_and_backoff_progression(tmp_path):
    store, secrets, broker, _ = setup(tmp_path, broker='b:1883')
    default = MqttService(store, secrets, dict)
    assert (default.client_timeout, default.interval, default.backoff) == (5, 2, (5, 60))
    broker.error = OSError('down')
    service = MqttService(store, secrets, dict, broker.factory, interval=0.02, backoff=(0.1, 0.2), client_timeout=0.3)
    await service.start()
    try:
        await until(lambda: len(broker.attempts) >= 5)
    finally: await service.stop()
    gaps = [b - a for a, b in zip(broker.attempts, broker.attempts[1:])]
    assert gaps[0] >= 0.09 and gaps[1] >= 0.19 and all(0.19 <= g < 0.4 for g in gaps[1:4])  # 0.1, 0.2, then capped


async def test_refused_credentials_are_reported_as_such(tmp_path):
    _, _, broker, service = setup(tmp_path, broker='b:1883')
    broker.error = aiomqtt.MqttCodeError(ReasonCode(PacketTypes.CONNACK, identifier=134))
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'disconnected')
        assert service.status()['error'] == 'Authentification refusée'
    finally: await service.stop()


async def test_state_provider_failure_is_contained(tmp_path):
    store, secrets, broker, _ = setup(tmp_path, broker='b:1883')
    calls = []
    def provider():
        calls.append(1)
        raise RuntimeError('boom')
    service = MqttService(store, secrets, provider, broker.factory, **FAST)
    await service.start()
    try:
        await until(lambda: len(calls) >= 2)
        assert service.status()['state'] == 'disconnected' and service.status()['error'] == 'Échange MQTT interrompu'
    finally: await service.stop()


async def test_hanging_publish_does_not_block_ticks(tmp_path):
    _, _, broker, service = setup(tmp_path, broker='b:1883')
    coordinator = Coordinator(SQLiteStore(tmp_path / 'control'))
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        broker.hang = True
        broker.incoming.put_nowait(('homeassistant/status', 'online'))  # forces a publish... and a hang
        started = time.monotonic()
        while service.status()['state'] == 'connected':
            await asyncio.wait_for(coordinator.tick(SiteSnapshot(utcnow())), 5)
            await asyncio.sleep(0.02)
            assert time.monotonic() - started < 3
        assert service.status()['error'] == 'Échange MQTT interrompu'
        assert time.monotonic() - started >= FAST['client_timeout'] * 0.9
    finally: await service.stop()


async def test_hanging_connection_is_bounded(tmp_path):
    _, _, broker, service = setup(tmp_path, broker='b:1883')
    @asynccontextmanager
    async def never(*args):
        await asyncio.Event().wait()
        yield
    service.client_factory = never
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'disconnected')
        assert service.status()['error'] == 'Courtier injoignable'
    finally: await service.stop()


async def test_reconnects_on_config_change(tmp_path):
    store, secrets, broker, service = setup(tmp_path, broker='b:1883')
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        save(store, broker='other:1883')
        await until(lambda: len(broker.connections) == 2)
        assert broker.connections[1]['config'].broker == 'other:1883'
        secrets.set('mqtt_password', 'new')
        await until(lambda: len(broker.connections) == 3)
        assert broker.connections[2]['password'] == 'new'
        assert broker.open == 1
        save(store)  # broker emptied: disabled and disconnected
        await until(lambda: service.status()['state'] == 'disabled' and broker.open == 0)
        assert broker.on('sem/status')[-1] == 'offline'
    finally: await service.stop()


async def test_stop_is_bounded_when_the_broker_hangs(tmp_path):
    _, _, broker, service = setup(tmp_path, broker='b:1883')
    await service.start()
    await until(lambda: service.status()['state'] == 'connected')
    broker.hang = True
    started = time.monotonic()
    await service.stop()
    assert time.monotonic() - started < 2
    assert service._task is None or service._task.done()


async def test_stop_is_bounded_when_the_client_disconnect_hangs(tmp_path):
    _, _, broker, service = setup(tmp_path, broker='b:1883')
    await service.start()
    await until(lambda: service.status()['state'] == 'connected')
    broker.hang_exit = True
    started = time.monotonic()
    await service.stop()
    assert time.monotonic() - started < 2.5
    assert service._task is None and service.status()['state'] == 'disabled'


async def test_reconnects_even_when_the_previous_disconnect_hangs(tmp_path):
    _, _, broker, service = setup(tmp_path, broker='b:1883')
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        broker.hang_exit = True
        broker.incoming.put_nowait(None)  # ends the session with an error whose cleanup hangs
        await until(lambda: len(broker.connections) == 2, timeout=5)
        await until(lambda: service.status()['state'] == 'connected')
    finally: await service.stop()


async def test_reconnects_when_the_message_stream_ends(tmp_path):
    _, _, broker, service = setup(tmp_path, broker='b:1883')
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        broker.incoming.put_nowait(None)
        await until(lambda: len(broker.connections) == 2)
        await until(lambda: service.status()['state'] == 'connected')
        first = len(broker.config_topics())
        await broker.incoming.put(('homeassistant/status', 'online'))  # the new session listens again
        await until(lambda: len(broker.config_topics()) > first)
    finally: await service.stop()


async def test_password_never_reaches_the_journal_or_the_status(tmp_path):
    store, secrets, broker, service = setup(tmp_path, broker='b:1883')
    password = 'p@ss:w/rd#\u00e9'
    secrets.set('mqtt_password', password)
    seen = []
    await service.start()
    try:
        for error, text in ((OSError(f'cannot reach with {password}'), 'Courtier injoignable'),
                            (aiomqtt.MqttCodeError(ReasonCode(PacketTypes.CONNACK, identifier=134)),
                             'Authentification refusée')):
            broker.error = error
            await until(lambda: service.status()['error'] == text)
            seen.append(str(service.status()))
        logs = store.journal.query(areas=('mqtt',))
        assert len(logs['entries']) == 2
        assert password not in str(logs) + ''.join(seen)
    finally: await service.stop()


async def test_test_connection_reports_french_errors(tmp_path):
    _, _, broker, service = setup(tmp_path)
    await service.test(MqttConfig(broker='b:1883'), 'pw')
    assert broker.connections[0]['client_id'] != service.default_client_id  # never steals the live session
    assert broker.sent == [] and broker.open == 0
    broker.error = OSError('x')
    with pytest.raises(ValueError, match='Courtier injoignable'): await service.test(MqttConfig(broker='b:1883'), None)
    broker.error = aiomqtt.MqttCodeError(ReasonCode(PacketTypes.CONNACK, identifier=135))
    with pytest.raises(ValueError, match='Authentification refusée'): await service.test(MqttConfig(broker='b:1883'), None)
    with pytest.raises(ValueError, match='Courtier'): await service.test(MqttConfig(), None)


async def test_remove_clears_discovery_and_marks_offline(tmp_path):
    store, _, broker, service = setup(tmp_path, broker='b:1883')
    await service.start()
    try: await until(lambda: service.status()['state'] == 'connected')
    finally: await service.stop()
    broker.sent.clear()
    assert await service.remove(MqttConfig(broker='b:1883'), None) is True
    cleared = [t for t, p, r in broker.sent if t.endswith('/config')]
    assert cleared and all(p == '' and r for t, p, r in broker.sent if t.endswith('/config'))
    assert broker.sent[-1] == ('sem/status', 'offline', True)
    broker.error = OSError('x')
    assert await service.remove(MqttConfig(broker='b:1883'), None) is False


async def test_remove_without_broker_or_topic_never_connects(tmp_path):
    _, _, broker, service = setup(tmp_path)
    assert await service.remove(MqttConfig(), None) is None
    assert await service.remove(MqttConfig(broker='b:1883', topic=''), 'pw') is None
    assert await service.remove(MqttConfig(topic='sem'), None) is None
    assert broker.attempts == [] and broker.connections == [] and broker.sent == []


class CapturedClient:
    kwargs = None
    def __init__(self, **kwargs): type(self).kwargs = kwargs
    async def __aenter__(self): return self
    async def __aexit__(self, *exc): return None
    async def publish(self, topic, payload, qos=0, retain=False): type(self).published = (topic, payload, retain)
    async def subscribe(self, topic): pass


async def open_default(monkeypatch, config, password=None):
    monkeypatch.setattr(aiomqtt, 'Client', CapturedClient)
    async with service_module.default_client_factory(config, password, 'cid', f'{config.topic}/status') as client:
        await client.publish('t', 'p', True)
    return CapturedClient.kwargs


async def test_default_factory_options(monkeypatch):
    kwargs = await open_default(monkeypatch, MqttConfig(broker='192.168.1.30:1884', username='u'), 'secret')
    assert (kwargs['hostname'], kwargs['port']) == ('192.168.1.30', 1884)
    assert (kwargs['username'], kwargs['password'], kwargs['identifier'], kwargs['keepalive']) == ('u', 'secret', 'cid', 30)
    will = kwargs['will']
    assert (will.topic, will.payload, will.retain) == ('sem/status', 'offline', True)
    assert kwargs.get('tls_params') is None and not kwargs.get('tls_insecure') and kwargs.get('tls_context') is None
    assert CapturedClient.published == ('t', 'p', True)
    anonymous = await open_default(monkeypatch, MqttConfig(broker='h:1883'))
    assert anonymous['username'] is None and anonymous['password'] is None
    # Self-signed is meaningless without TLS and must not switch anything on.
    plain = await open_default(monkeypatch, MqttConfig(broker='h:1883', allow_self_signed=True))
    assert plain.get('tls_params') is None and not plain.get('tls_insecure')
    verified = await open_default(monkeypatch, MqttConfig(broker='h:8883', tls=True))
    assert verified['tls_params'] is not None and not verified.get('tls_insecure')
    assert verified['tls_params'].cert_reqs in (None, ssl.CERT_REQUIRED)
    insecure = await open_default(monkeypatch, MqttConfig(broker='h:8883', tls=True, allow_self_signed=True))
    assert insecure['tls_insecure'] is True and insecure['tls_params'].cert_reqs == ssl.CERT_NONE


class FakeHandler:
    """Records what the service routes to it; `errors` are raised one per call, first call first."""

    def __init__(self, result=('site', 'price'), errors=()):
        self.calls, self.result, self.errors = [], result, list(errors)

    async def handle(self, prefix, topic, payload):
        self.calls.append((prefix, topic, payload))
        if self.errors and (error := self.errors.pop(0)): raise error
        return self.result


def with_commands(tmp_path, handler, interval=FAST['interval'], **mqtt):
    store, secrets, broker, _ = setup(tmp_path, broker='b:1883', **mqtt)
    service = MqttService(store, secrets, lambda: make_state(), broker.factory, commands=handler,
                          **{**FAST, 'interval': interval})
    return store, broker, service


async def test_command_message_is_handled_and_state_republished_at_once(tmp_path):
    handler = FakeHandler()
    _, broker, service = with_commands(tmp_path, handler, interval=5, commands_enabled=True)
    await service.start()
    try:
        await until(lambda: broker.on('sem/site/price/state') == ['0.123'])
        assert broker.subscribed == ['homeassistant/status', 'sem/+/+/set']
        await asyncio.sleep(0.1)  # the loop is now asleep for 5 s
        await broker.incoming.put(('sem/ev/car_mode/set', 'Pause', False))
        await until(lambda: broker.on('sem/site/price/state') == ['0.123', '0.123'], timeout=2)  # forgotten, sent again
        assert handler.calls == [('sem', 'sem/ev/car_mode/set', 'Pause')]
        await broker.incoming.put(('sem/ev/car_mode/set', 'Auto'))  # an old two-item message is not retained
        await until(lambda: len(handler.calls) == 2)
    finally: await service.stop()


async def test_retained_command_is_ignored(tmp_path):
    handler = FakeHandler()
    store, broker, service = with_commands(tmp_path, handler, commands_enabled=True)
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        await broker.incoming.put(('sem/ev/car_mode/set', 'Pause', True))
        await until(lambda: 'Commande Home Assistant retenue ignorée' in str(store.journal.query(areas=('mqtt',))))
        assert handler.calls == []
        entries = store.journal.query(areas=('mqtt',))['entries']
        assert [(e['level'], e['message']) for e in entries] == [('WARN', 'Commande Home Assistant retenue ignorée')]
    finally: await service.stop()


async def test_commands_disabled_neither_subscribe_nor_apply(tmp_path):
    handler = FakeHandler()
    _, broker, service = with_commands(tmp_path, handler)
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        first = len(broker.config_topics())
        await broker.incoming.put(('sem/ev/car_mode/set', 'Pause', False))
        await broker.incoming.put(('homeassistant/status', 'online'))  # read after the command: it was consumed
        await until(lambda: len(broker.config_topics()) == 2 * first)
        assert broker.subscribed == ['homeassistant/status'] and handler.calls == []
    finally: await service.stop()


async def test_handler_error_does_not_stop_the_reader(tmp_path):
    handler = FakeHandler(errors=[RuntimeError('boom-secret')])
    store, broker, service = with_commands(tmp_path, handler, commands_enabled=True)
    await service.start()
    try:
        await until(lambda: service.status()['state'] == 'connected')
        await broker.incoming.put(('sem/ev/car_mode/set', 'Pause', False))
        await broker.incoming.put(('sem/ev/car_mode/set', 'Auto', False))
        await until(lambda: len(handler.calls) == 2)
        seen = service.status()['last_publish_at']
        await until(lambda: service.status()['last_publish_at'] != seen)  # the publish loop keeps going
        entries = store.journal.query(areas=('mqtt',))['entries']
        assert [e['level'] for e in entries] == ['ERROR'] and 'RuntimeError' in entries[0]['message']
        assert 'boom-secret' not in str(entries) and len(broker.connections) == 1
        assert service.status()['state'] == 'connected'
    finally: await service.stop()


SELECT = 'homeassistant/select/sem_ev/car_mode/config'
NUMBER = 'homeassistant/number/sem_ev/program_semaine_target/config'


def save_car(store, commands_enabled=True, program='Semaine'):
    store.save_settings(SettingsDocument.model_validate({
        'mqtt': {'broker': 'b:1883', 'commands_enabled': commands_enabled},
        'devices': [{'id': 'ev', 'name': 'Wallbox', 'kind': 'charger', 'armed': True, 'vehicle_id': 'car'}],
        'vehicles': [{'id': 'car'}],
        'schedules': [{'id': 'semaine', 'name': program, 'vehicle_id': 'car', 'target_soc': 80}]}).model_dump(mode='json'))


async def test_turning_commands_off_removes_the_entities_and_the_subscription(tmp_path):
    store, broker, service = with_commands(tmp_path, FakeHandler())
    save_car(store)
    await service.start()
    try:
        await until(lambda: broker.on(SELECT) and broker.on(NUMBER))
        assert broker.on(SELECT)[-1] and broker.on(NUMBER)[-1]
        assert broker.subscribed == ['homeassistant/status', 'sem/+/+/set']
        known = len(broker.subscribed)
        save_car(store, commands_enabled=False)  # the session restarts without commands
        await until(lambda: len(broker.connections) == 2 and service.status()['state'] == 'connected')
        await until(lambda: broker.on(SELECT)[-1] == '' and broker.on(NUMBER)[-1] == '')
        assert (SELECT, '', True) in broker.sent and (NUMBER, '', True) in broker.sent  # retained, so Home Assistant forgets them
        assert broker.subscribed[known:] == ['homeassistant/status']  # no '/set' subscription on the new connection
    finally: await service.stop()


async def test_renaming_a_program_reannounces_the_number_under_the_same_unique_id(tmp_path):
    store, broker, service = with_commands(tmp_path, FakeHandler(), interval=0.05)
    save_car(store)
    await service.start()
    try:
        await until(lambda: broker.on(NUMBER))
        first = json.loads(broker.on(NUMBER)[-1])
        assert first['name'] == 'Objectif – Semaine'
        save_car(store, program='Semaine 2')
        await until(lambda: len(broker.on(NUMBER)) > 1)
        again = json.loads(broker.on(NUMBER)[-1])
        assert again['name'] == 'Objectif – Semaine 2'
        assert again['unique_id'] == first['unique_id'] == 'sem_ev_program_semaine_target'
        assert len(broker.connections) == 1
    finally: await service.stop()
