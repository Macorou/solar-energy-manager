import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.api.water_heaters import adapter
from app.connectors.ariston.client import AristonAdapter
from app.domain.commands import CommandIntent
from app.domain.devices import DeviceState
from app.domain.measurements import Sample, utcnow
from app.domain.site import SiteSnapshot
from app.main import create_app
from app.settings import DeviceConfig, RuntimeSettings, SettingsDocument


class NativeHeater:
    water_heater_current_temperature = 28
    water_heater_target_temperature = 55
    water_heater_minimum_temperature = 40
    water_heater_maximum_temperature = 65
    water_heater_power_value = False

    def __init__(self):
        self.calls = []

    async def async_update_state(self): pass
    async def async_update_settings(self): pass

    async def async_set_water_heater_temperature(self, target):
        self.calls.append(('target', target))

    async def async_set_power(self, power):
        self.calls.append(('power', power))


def configured_app(tmp_path):
    app = create_app(RuntimeSettings(data_dir=tmp_path))
    device = DeviceConfig(id='tank', name='Test NUOS', kind='water_heater',
        mode='off_peak_solar', armed=True, gateway_id='TEST-GATEWAY',
        target=50, min_power_w=700, max_power_w=2570)
    config = SettingsDocument(site_limit_w=11000, devices=[device])
    app.state.store.save_settings(config.model_dump(mode='json'))
    app.state.secrets.set('ariston_password', 'test-password-only')
    return app, device, config


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['manual', 'off', 'solar', 'off_peak_solar'])
async def test_mode_and_target_changes_keep_the_session_and_use_current_target(tmp_path, mode):
    app, device, config = configured_app(tmp_path)
    request = SimpleNamespace(app=app)
    source = adapter(request, device)
    native = source.device = NativeHeater()
    await source.probe_capabilities()
    changed = device.model_copy(update={'mode': mode, 'target': 55})
    app.state.store.save_settings(config.model_copy(update={'devices': [changed]}).model_dump(mode='json'))
    current = adapter(request, changed)
    assert current is source
    result = await current.execute(CommandIntent('start', 'tank', 'set_power', 2570))
    assert result.accepted
    assert native.calls == [('target', 55), ('power', True)]


@pytest.mark.parametrize('changed', ['gateway', 'username', 'password'])
def test_connection_identity_changes_replace_the_old_session(tmp_path, changed):
    app, device, config = configured_app(tmp_path)
    request = SimpleNamespace(app=app)
    source = adapter(request, device)
    source.device = NativeHeater()
    if changed == 'gateway':
        device = device.model_copy(update={'gateway_id': 'OTHER-GATEWAY'})
    elif changed == 'username':
        config.ariston.username = 'other-test-account'
    else:
        app.state.secrets.set('ariston_password', 'other-test-password')
    config.devices = [device]
    app.state.store.save_settings(config.model_dump(mode='json'))
    current = adapter(request, device)
    assert current is not source
    assert current.device is None


@pytest.mark.asyncio
async def test_probe_before_discovery_cannot_disable_commands_after_connection():
    device = DeviceConfig(id='tank', name='Test', kind='water_heater', target=55)
    source = AristonAdapter(device)
    early = await source.probe_capabilities()
    assert not early.supported
    native = source.device = NativeHeater()
    result = await source.execute(CommandIntent('start', 'tank', 'set_power', 2570))
    assert result.accepted
    assert native.calls == [('target', 55), ('power', True)]


@pytest.mark.asyncio
async def test_command_waits_for_in_progress_connection(monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    native = NativeHeater()

    class Library:
        async def async_connect(self, username, password):
            entered.set()
            await release.wait()
            return True

        async def async_hello(self, gateway): return native

    monkeypatch.setattr('app.connectors.ariston.client.Ariston', Library)
    device = DeviceConfig(id='tank', name='Test', kind='water_heater', target=55)
    source = AristonAdapter(device, 'test-account', 'test-password')
    connection = asyncio.create_task(source.connect())
    await entered.wait()
    command = asyncio.create_task(source.execute(CommandIntent('start', 'tank', 'set_power', 2570)))
    await asyncio.sleep(0)
    release.set()
    try:
        _, result = await asyncio.wait_for(asyncio.gather(connection, command), 2)
        assert result.accepted
        assert native.calls == [('target', 55), ('power', True)]
    finally:
        for task in (connection, command):
            if not task.done(): task.cancel()
        await asyncio.gather(connection, command, return_exceptions=True)


def prepare_runtime(app, config):
    runtime = app.state.coordinator
    now = utcnow()
    sample = lambda value: Sample(value, 'W', 'test', now, now)
    runtime.ha = SimpleNamespace(device_power=lambda key: sample(0),
        snapshot=lambda: SiteSnapshot(now, grid=sample(700)))
    runtime.ha_signature = (config.home_assistant.model_dump_json(), '')
    runtime.running = True
    return runtime


async def stop_workers(runtime):
    runtime.running = False
    jobs = [*runtime.workers.values(), *runtime.command_tasks.values(), *runtime.refresh_tasks]
    for job in jobs: job.cancel()
    await asyncio.gather(*jobs, return_exceptions=True)


@pytest.mark.asyncio
async def test_manual_transition_uses_ready_adapter_without_reconnecting(tmp_path, monkeypatch):
    app, device, config = configured_app(tmp_path)
    source = adapter(SimpleNamespace(app=app), device)
    native = source.device = NativeHeater()
    await source.probe_capabilities()
    runtime = prepare_runtime(app, config)
    reconnects = []

    class NoReconnect:
        async def async_connect(self, username, password):
            reconnects.append(True)
            await asyncio.Event().wait()

    monkeypatch.setattr('app.connectors.ariston.client.Ariston', NoReconnect)
    try:
        await runtime.acquire(config)
        for _ in range(8): await asyncio.sleep(0)
        assert runtime.cache['tank'].connected
        app.state.store.set('manual_controls', {'tank': {
            'until': (utcnow() + timedelta(minutes=30)).isoformat(),
            'previous_mode': 'off_peak_solar'}})
        manual_config = config.model_copy(update={'devices': [device.model_copy(update={'mode': 'manual'})]})
        app.state.store.save_settings(manual_config.model_dump(mode='json'))
        await runtime.tick()
        await asyncio.gather(*runtime.command_tasks.values())
        assert runtime.dispatcher.records['tank']['status'] == 'accepted'
        assert runtime.dispatcher.records['tank']['action'] == 'set_power'
        assert native.calls == [('target', 50), ('power', True)]
        assert not reconnects
    finally:
        await stop_workers(runtime)


@pytest.mark.asyncio
async def test_replaced_connection_cannot_inherit_old_connected_state(tmp_path, monkeypatch):
    app, device, config = configured_app(tmp_path)
    source = adapter(SimpleNamespace(app=app), device)
    source.device = NativeHeater()
    runtime = prepare_runtime(app, config)

    class WaitingLibrary:
        async def async_connect(self, username, password):
            await asyncio.Event().wait()

    monkeypatch.setattr('app.connectors.ariston.client.Ariston', WaitingLibrary)
    try:
        await runtime.acquire(config)
        for _ in range(8): await asyncio.sleep(0)
        assert runtime.cache['tank'].connected
        changed = config.model_copy(update={'devices': [device.model_copy(update={'gateway_id': 'OTHER-GATEWAY'})]})
        app.state.store.save_settings(changed.model_dump(mode='json'))
        snapshot = await runtime.acquire(changed)
        assert not snapshot.device_states['tank'].connected
    finally:
        await stop_workers(runtime)


class LoadingLimitsHeater(NativeHeater):
    water_heater_maximum_temperature = None

    def __init__(self):
        super().__init__()
        self.loading = asyncio.Event()
        self.release = asyncio.Event()

    async def async_update_settings(self):
        self.loading.set()
        await self.release.wait()
        self.water_heater_maximum_temperature = 65


def fake_discovery(monkeypatch, native):
    class Library:
        async def async_connect(self, username, password): return True
        async def async_hello(self, gateway): return native
    monkeypatch.setattr('app.connectors.ariston.client.Ariston', Library)


@pytest.mark.asyncio
async def test_target_change_during_settings_load_uses_loaded_limits_and_current_target(tmp_path, monkeypatch):
    app, device, config = configured_app(tmp_path)
    config.ariston.username = 'test-account'
    app.state.store.save_settings(config.model_dump(mode='json'))
    native = LoadingLimitsHeater()
    fake_discovery(monkeypatch, native)
    runtime = prepare_runtime(app, config)
    try:
        await runtime.acquire(config)
        await asyncio.wait_for(native.loading.wait(), 2)
        changed = config.model_copy(update={'devices': [device.model_copy(update={'target': 55})]})
        app.state.store.save_settings(changed.model_dump(mode='json'))
        await runtime.acquire(changed)
        for _ in range(4): await asyncio.sleep(0)
        native.release.set()
        for _ in range(8): await asyncio.sleep(0)
        result = await runtime.adapters['tank'].execute(CommandIntent('start', 'tank', 'set_power', 2570))
        assert result.accepted
        assert native.calls == [('target', 55), ('power', True)]
    finally:
        await stop_workers(runtime)


@pytest.mark.asyncio
async def test_cancelled_initialization_reloads_limits_before_a_command(monkeypatch):
    native = LoadingLimitsHeater()
    fake_discovery(monkeypatch, native)
    device = DeviceConfig(id='tank', name='Test', kind='water_heater', target=55)
    source = AristonAdapter(device, 'test-account', 'test-password')
    initialization = asyncio.create_task(source.connect())
    try:
        await asyncio.wait_for(native.loading.wait(), 2)
        initialization.cancel()
        await asyncio.gather(initialization, return_exceptions=True)
        native.release.set()
        result = await source.execute(CommandIntent('start', 'tank', 'set_power', 2570))
        assert result.accepted
        assert native.calls == [('target', 55), ('power', True)]
    finally:
        if not initialization.done(): initialization.cancel()
        await asyncio.gather(initialization, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [False, True])
async def test_old_command_refresh_cannot_publish_after_session_replacement(tmp_path, failure):
    app, device, config = configured_app(tmp_path)
    source = adapter(SimpleNamespace(app=app), device)
    source.device = NativeHeater()
    runtime = prepare_runtime(app, config)
    entered, release = asyncio.Event(), asyncio.Event()
    old_refresh = None
    try:
        await runtime.acquire(config)
        for _ in range(8): await asyncio.sleep(0)
        assert runtime.cache['tank'].connected

        async def old_read():
            entered.set()
            await release.wait()
            if failure: raise RuntimeError('old session unavailable')
            return DeviceState('tank', connected=True, temperature=99)

        source.read_state = old_read
        old_refresh = asyncio.create_task(runtime.refresh_after_command('tank', source))
        await entered.wait()
        changed = config.model_copy(update={'devices': [device.model_copy(update={'gateway_id': 'OTHER-GATEWAY'})]})
        app.state.store.save_settings(changed.model_dump(mode='json'))
        await runtime.acquire(changed)
        release.set()
        await old_refresh
        state = runtime.cache.get('tank')
        assert not state or not state.connected
        assert 'tank' not in runtime.errors
    finally:
        if old_refresh and not old_refresh.done(): old_refresh.cancel()
        if old_refresh: await asyncio.gather(old_refresh, return_exceptions=True)
        await stop_workers(runtime)


@pytest.mark.asyncio
async def test_changed_target_is_evaluated_on_cached_temperature_without_reconnecting(tmp_path):
    app, device, config = configured_app(tmp_path)
    source = adapter(SimpleNamespace(app=app), device)
    source.device = NativeHeater()
    source.device.water_heater_current_temperature = 52
    runtime = prepare_runtime(app, config)
    try:
        await runtime.acquire(config)
        for _ in range(8): await asyncio.sleep(0)
        assert runtime.cache['tank'].target_reached
        changed = config.model_copy(update={'devices': [device.model_copy(update={'target': 55})]})
        app.state.store.save_settings(changed.model_dump(mode='json'))
        snapshot = await runtime.acquire(changed)
        assert snapshot.device_states['tank'].temperature == 52
        assert not snapshot.device_states['tank'].target_reached
    finally:
        await stop_workers(runtime)
