import asyncio
import os
import ssl
import time
from contextlib import AsyncExitStack, asynccontextmanager
import aiomqtt
from app.connectors.mqtt.entities import build_entities
from app.connectors.mqtt.publisher import Publisher
from app.domain.measurements import utcnow
from app.settings import MqttConfig, SettingsDocument

CLIENT_TIMEOUT_S = 5
LOOP_INTERVAL_S = 2
BACKOFF_S = (5, 60)
KEEPALIVE_S = 30
UNREACHABLE = 'Courtier injoignable'
REFUSED = 'Authentification refusée'
INTERRUPTED = 'Échange MQTT interrompu'
# CONNACK refusals for bad credentials / not authorised (MQTT 3.1.1: 4, 5; MQTT 5: 134, 135).
AUTH_CODES = {4, 5, 134, 135}


@asynccontextmanager
async def default_client_factory(config: MqttConfig, password: str | None, client_id: str, will_topic: str):
    host, _, port = config.broker.rpartition(':')
    options = {}
    if config.tls:
        options['tls_params'] = aiomqtt.TLSParameters(cert_reqs=ssl.CERT_NONE if config.allow_self_signed else None)
        if config.allow_self_signed: options['tls_insecure'] = True
    client = aiomqtt.Client(hostname=host, port=int(port), username=config.username or None,
        password=password or None, identifier=client_id, keepalive=KEEPALIVE_S,
        will=aiomqtt.Will(will_topic, 'offline', qos=1, retain=True), **options)
    async with client:
        yield _AiomqttSession(client)


class _AiomqttSession:
    """Adapts `aiomqtt.Client` to the small interface the service relies on."""

    def __init__(self, client): self.client = client

    async def publish(self, topic, payload, retain): await self.client.publish(topic, payload, qos=1, retain=retain)

    async def subscribe(self, topic): await self.client.subscribe(topic)

    async def messages(self):
        async for message in self.client.messages:
            payload = message.payload
            yield str(message.topic), payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else str(payload)


class _Bounded:
    """Every call to the broker gets a deadline, so a stuck connection can never hang the service."""

    def __init__(self, client, timeout): self.client, self.timeout = client, timeout

    async def publish(self, topic, payload, retain):
        await asyncio.wait_for(self.client.publish(topic, payload, retain), self.timeout)

    async def subscribe(self, topic): await asyncio.wait_for(self.client.subscribe(topic), self.timeout)


def refused(error) -> bool:
    return isinstance(error, aiomqtt.MqttCodeError) and getattr(error.rc, 'value', error.rc) in AUTH_CODES


class MqttService:
    """Publishes SEM state to MQTT. It lives in its own task and only ever reports through `status()` and the journal."""

    def __init__(self, store, secrets, state_provider, client_factory=None, *,
                 client_timeout=CLIENT_TIMEOUT_S, interval=LOOP_INTERVAL_S, backoff=BACKOFF_S):
        self.store, self.secrets, self.state_provider = store, secrets, state_provider
        self.client_factory = client_factory or default_client_factory
        self.client_timeout, self.interval, self.backoff = client_timeout, interval, backoff
        self.default_client_id = 'sem-' + os.urandom(4).hex()
        self._task = None
        self._stop = asyncio.Event()
        self._state, self._error, self._last_publish_at = 'disabled', None, None
        self._logged = None  # (state, error) of the last warning written to the journal
        self._reached = False  # the current attempt got connected at least once
        self._phase = 'connect'
        self._reannounce = asyncio.Event()

    def status(self) -> dict:
        return {'state': self._state, 'last_publish_at': self._last_publish_at, 'error': self._error}

    async def start(self):
        if self._task and not self._task.done(): return
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        task, self._task = self._task, None
        if not task: return
        self._stop.set()
        # The loop publishes `offline` itself on the way out; give it 5 s at most, then cut it.
        await asyncio.wait({task}, timeout=self.client_timeout)
        if not task.done():
            task.cancel()
            # A client stuck in its own disconnect may ignore the cancellation: wait briefly, then abandon the task.
            await asyncio.wait({task}, timeout=1)
        if task.done(): task.cancelled() or task.exception()
        else: task.add_done_callback(lambda done: done.cancelled() or done.exception())
        self._state, self._error = 'disabled', None

    def _load(self):
        document = SettingsDocument.model_validate(self.store.load_settings())
        return document, self.secrets.get('mqtt_password') or None

    def _client_id(self, config): return config.client_id or self.default_client_id

    async def _sleep(self, seconds):
        try: await asyncio.wait_for(self._stop.wait(), seconds)
        except TimeoutError: pass

    async def _run(self):
        delay = self.backoff[0]
        while not self._stop.is_set():
            current = None
            try:
                document, password = self._load()
                current = (document.mqtt, password)
                if not document.mqtt.enabled:
                    self._state, self._error = 'disabled', None
                    await self._sleep(self.interval)
                    continue
                self._reached, self._phase = False, 'connect'
                await self._session(document, password)
                delay = self.backoff[0]
                continue
            except asyncio.CancelledError: raise
            except Exception as error:
                self._fail(error)
            if self._reached: delay = self.backoff[0]
            await self._wait_before_retry(delay, current)
            delay = min(delay * 2, self.backoff[1])

    async def _wait_before_retry(self, delay, failed):
        """Backoff, cut short as soon as the settings or the password change."""
        end = time.monotonic() + delay
        while not self._stop.is_set() and time.monotonic() < end:
            await self._sleep(min(self.interval, max(end - time.monotonic(), 0)))
            try:
                document, password = self._load()
                if (document.mqtt, password) != failed: return
            except Exception: pass  # unreadable settings are reported by the next attempt

    def _fail(self, error):
        if refused(error): text = REFUSED
        elif self._phase == 'connect': text = UNREACHABLE
        else: text = INTERRUPTED
        self._state, self._error = 'disconnected', text
        if self._logged != (self._state, text):
            self._logged = (self._state, text)
            self.store.journal.write('WARN', 'mqtt', f'{text} ({type(error).__name__})')

    def _connected(self):
        self._state, self._error, self._reached = 'connected', None, True
        if self._logged:
            self._logged = None
            self.store.journal.write('INFO', 'mqtt', 'Connexion MQTT rétablie')

    @staticmethod
    def _signature(entities):
        return {(e.component, e.group, e.key, e.name, e.device_name) for e in entities}

    async def _session(self, document, password):
        config = document.mqtt
        if self._state != 'disconnected': self._state, self._error = 'connecting', None
        topic = f'{config.topic}/status'
        async with self._connect(config, password, self._client_id(config), topic) as raw:
            self._phase = 'exchange'
            client = _Bounded(raw, self.client_timeout)
            publisher = Publisher(client, config.topic, config.discovery_prefix, self.store)  # fresh per connection
            await client.publish(topic, 'online', True)
            entities = self.entities(document)
            await publisher.announce(entities)
            await client.subscribe(f'{config.discovery_prefix}/status')
            signature = self._signature(entities)
            self._reannounce.clear()
            reader = asyncio.create_task(self._read(raw, f'{config.discovery_prefix}/status'))
            try:
                self._connected()
                while not self._stop.is_set():
                    document, latest = self._load()
                    if (document.mqtt, latest) != (config, password): break
                    if reader.done():
                        reader.result()
                        raise ConnectionError('MQTT message stream ended')
                    entities = self.entities(document)
                    await publisher.publish(entities, time.monotonic())
                    if self._reannounce.is_set() or self._signature(entities) != signature:
                        self._reannounce.clear()
                        signature = self._signature(entities)
                        await publisher.announce(entities)
                    self._last_publish_at = utcnow().isoformat()
                    await self._sleep(self.interval)
                try: await client.publish(topic, 'offline', True)
                except Exception: pass  # best effort: the broker publishes the will when the link drops
            finally:
                reader.cancel()
                await asyncio.gather(reader, return_exceptions=True)

    def entities(self, document):
        return build_entities(self.state_provider(), document, utcnow())

    async def _read(self, client, topic):
        async for received, payload in client.messages():
            if received == topic and payload == 'online': self._reannounce.set()

    @asynccontextmanager
    async def _connect(self, config, password, client_id, will_topic):
        """The factory's context with a deadline on both entering and leaving it."""
        stack = AsyncExitStack()
        try:
            yield await asyncio.wait_for(stack.enter_async_context(
                self.client_factory(config, password, client_id, will_topic)), self.client_timeout)
        finally:
            try: await asyncio.wait_for(stack.aclose(), self.client_timeout)
            except Exception: pass  # the link is being dropped anyway; a stuck disconnect must not hold up the caller

    @asynccontextmanager
    async def _throwaway(self, config, password, suffix, will_topic):
        """Short-lived connection with its own client id, so the live session is never kicked off."""
        async with self._connect(config, password, f'{self._client_id(config)}-{suffix}', will_topic) as raw:
            yield _Bounded(raw, self.client_timeout)

    async def test(self, config: MqttConfig, password: str | None) -> None:
        if not config.broker: raise ValueError('Courtier non renseigné')
        try:
            async with self._throwaway(config, password, 'test', f'{config.topic or "sem"}/test'): pass
        except Exception as error:
            raise ValueError(REFUSED if refused(error) else UNREACHABLE) from None

    async def remove(self, config: MqttConfig, password: str | None) -> bool | None:
        """True: cleaned; False: broker unreachable; None: nothing was ever announced, so no attempt was made."""
        if not config.broker or not config.topic: return None
        status = f'{config.topic}/status'
        try:
            async with self._throwaway(config, password, 'rm', status) as client:
                await Publisher(client, config.topic, config.discovery_prefix, self.store).clear()
                await client.publish(status, 'offline', True)
            return True
        except Exception as error:
            self.store.journal.write('WARN', 'mqtt', f'Nettoyage MQTT impossible ({type(error).__name__})')
            return False
