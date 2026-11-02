import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.settings import DeviceConfig,RuntimeSettings,SettingsDocument,VehicleConfig


def service(tmp_path,kind,mode):
    app=create_app(RuntimeSettings(data_dir=tmp_path,start_runtime=False))
    client=TestClient(app)
    assert client.post('/api/v1/setup',json={'token':(tmp_path/'bootstrap-token').read_text(),
        'username':'admin','password':'a-secure-test-password'}).status_code==200
    config=SettingsDocument(vehicles=[VehicleConfig(id='car')],devices=[DeviceConfig(
        id='device',name='Appareil',kind=kind,mode=mode,armed=True,
        vehicle_id='car' if kind=='charger' else '',min_power_w=1380,max_power_w=3700)])
    app.state.store.save_settings(config.model_dump(mode='json'))
    return app,client


@pytest.mark.parametrize('kind,mode',[('charger','planned'),('water_heater','off_peak_solar'),('charger','solar')])
def test_automatic_selection_keeps_the_current_automatic_policy(tmp_path,kind,mode):
    app,client=service(tmp_path,kind,mode)
    # A historical pause must not overwrite a later policy chosen in settings.
    app.state.store.set('paused_modes',{'device':'solar'})
    assert client.post('/api/v1/devices/device/resume').status_code==200
    assert client.get('/api/v1/settings').json()['devices'][0]['mode']==mode


@pytest.mark.parametrize('kind,mode',[('charger','planned'),('water_heater','off_peak_solar'),('charger','solar')])
def test_manual_to_automatic_restores_the_saved_policy_and_clears_the_timer(tmp_path,kind,mode):
    app,client=service(tmp_path,kind,mode)
    assert client.post('/api/v1/devices/device/manual',json={'duration_minutes':30}).status_code==200
    assert client.post('/api/v1/devices/device/resume').status_code==200
    assert client.get('/api/v1/settings').json()['devices'][0]['mode']==mode
    assert 'device' not in app.state.store.get('manual_controls',{})


def test_manual_after_pause_restores_the_pre_pause_policy(tmp_path):
    app,client=service(tmp_path,'charger','planned')
    assert client.post('/api/v1/devices/device/pause').status_code==200
    assert client.post('/api/v1/devices/device/manual',json={'duration_minutes':30}).status_code==200
    assert client.post('/api/v1/devices/device/resume').status_code==200
    assert client.get('/api/v1/settings').json()['devices'][0]['mode']=='planned'


@pytest.mark.parametrize('blocked',['unarmed','unknown_command'])
def test_automatic_selection_cannot_bypass_existing_activation_or_unknown_command_guards(tmp_path,blocked):
    app,client=service(tmp_path,'charger','planned')
    if blocked=='unarmed':
        settings=app.state.store.load_settings()
        settings['devices'][0]['armed']=False
        app.state.store.save_settings(settings)
    else:
        app.state.coordinator.dispatcher.records['device']={'status':'unknown'}
    assert client.post('/api/v1/devices/device/resume').status_code==409
    assert client.get('/api/v1/settings').json()['devices'][0]['mode']=='planned'
