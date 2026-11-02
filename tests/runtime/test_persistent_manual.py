from dataclasses import replace
from datetime import timedelta
import pytest
from app.domain.devices import DeviceSpec, DeviceState
from app.domain.measurements import Sample, utcnow
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.runtime.coordinator import Coordinator
from app.settings import SettingsDocument
from app.simulation.clock import SimulatedClock
from test_resume_modes import service


def test_manual_charger_has_no_expiry_even_for_an_old_ui_sending_30_minutes(tmp_path):
    app, client = service(tmp_path, 'charger', 'planned')
    result = client.post('/api/v1/devices/device/manual', json={'duration_minutes':30})
    assert result.status_code == 200
    assert result.json()['until'] is None
    assert app.state.store.get('manual_controls')['device']['until'] is None
    assert client.post('/api/v1/devices/device/manual', json={}).status_code == 200
    assert app.state.store.get('manual_controls')['device']['previous_mode'] == 'planned'


@pytest.mark.parametrize('legacy', [True, False])
def test_overnight_and_restart_do_not_return_a_manual_charger_to_automatic(tmp_path, legacy):
    app, client = service(tmp_path, 'charger', 'manual')
    now = utcnow()
    if legacy:
        app.state.store.set('manual_controls', {'device':{
            'until':(now-timedelta(hours=10)).isoformat(), 'previous_mode':'planned'}})
    config = SettingsDocument.model_validate(app.state.store.load_settings())
    assert app.state.coordinator.policies(config, now)['device'].mode == 'manual'
    assert config.devices[0].mode == 'manual'
    reopened = Coordinator(app.state.store)
    next_day = SettingsDocument.model_validate(app.state.store.load_settings())
    assert reopened.policies(next_day, now+timedelta(days=2))['device'].mode == 'manual'
    assert app.state.store.load_settings()['devices'][0]['mode'] == 'manual'
    if legacy:
        assert app.state.store.get('manual_controls')['device']['until'] is None


@pytest.mark.parametrize('expiry', [None, 'past'])
def test_manual_car_can_keep_charging_without_solar_or_a_planned_window(expiry):
    clock = SimulatedClock()
    now = clock.now()
    sample = lambda value: Sample(value, 'W', 'test', now, now, checked_at=now)
    spec = DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700)
    policy = DevicePolicy('ev','manual',armed=True,
        manual_until=now-timedelta(hours=12) if expiry else None)
    snapshot = SiteSnapshot(now,grid=sample(500),solar=sample(0),site_limit_w=11000,
        device_states={'ev':DeviceState('ev',sample(0),'Preparing',True,vehicle_connected=True)})
    result = EnergyEngine(clock).evaluate(snapshot,[spec],{'ev':policy},{})
    assert result.commands[0].action == 'set_power' and result.commands[0].limit_w > 0
    assert result.reasons['ev'] == 'Commande manuelle'
    # Persistence of the mode does not bypass target or electrical limits.
    running = replace(snapshot,grid=sample(2500),device_states={'ev':replace(snapshot.device_states['ev'],observed_power=sample(2000),observed_state='Charging')})
    reached = replace(running,device_states={'ev':replace(running.device_states['ev'],target_reached=True)})
    target_engine=EnergyEngine(clock);target_engine.requested['ev']=3680
    assert target_engine.evaluate(reached,[spec],{'ev':policy},{}).commands[0].action == 'suspend'
    limited = replace(running,site_limit_w=600)
    limited_engine=EnergyEngine(clock);limited_engine.requested['ev']=3680
    assert limited_engine.evaluate(limited,[spec],{'ev':policy},{}).commands[0].action == 'suspend'


def test_only_explicit_automatic_or_pause_exits_manual_mode(tmp_path):
    app, client = service(tmp_path, 'charger', 'planned')
    assert client.post('/api/v1/devices/device/manual',json={}).status_code == 200
    assert client.post('/api/v1/devices/device/resume').status_code == 200
    assert app.state.store.load_settings()['devices'][0]['mode'] == 'planned'
    assert client.post('/api/v1/devices/device/manual',json={}).status_code == 200
    assert client.post('/api/v1/devices/device/pause').status_code == 200
    config = SettingsDocument.model_validate(app.state.store.load_settings())
    assert app.state.coordinator.policies(config,utcnow()+timedelta(days=2))['device'].mode == 'off'


def test_water_heater_retains_its_existing_temporary_manual_cycle(tmp_path):
    app, client = service(tmp_path, 'water_heater', 'off_peak_solar')
    response = client.post('/api/v1/devices/device/manual',json={'duration_minutes':1})
    assert response.status_code == 200 and response.json()['until'] is not None
    config = SettingsDocument.model_validate(app.state.store.load_settings())
    assert app.state.coordinator.policies(config,utcnow()+timedelta(minutes=2))['device'].mode == 'off_peak_solar'



@pytest.mark.parametrize('stale_pause', [None, 'solar'])
def test_pause_then_automatic_restores_the_policy_used_before_manual(tmp_path, stale_pause):
    app, client = service(tmp_path, 'charger', 'planned')
    if stale_pause:
        app.state.store.set('paused_modes', {'device':stale_pause})
    assert client.post('/api/v1/devices/device/manual',json={}).status_code == 200
    assert client.post('/api/v1/devices/device/pause').status_code == 200
    assert 'device' not in app.state.store.get('manual_controls',{})
    assert client.post('/api/v1/devices/device/resume').status_code == 200
    assert app.state.store.load_settings()['devices'][0]['mode'] == 'planned'
