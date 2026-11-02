import pytest
from app.runtime.device_modes import DeviceNotFound, ModeRefused, apply_manual, apply_pause, apply_resume
from test_resume_modes import service


def test_resume_to_planned_leaves_manual_and_clears_controls(tmp_path):
    app, client = service(tmp_path, 'charger', 'solar')
    apply_manual(app.state, 'device', origin='home_assistant')
    apply_resume(app.state, 'device', mode='planned')
    assert app.state.store.load_settings()['devices'][0]['mode'] == 'planned'
    assert 'device' not in app.state.store.get('manual_controls', {})


def test_manual_records_its_origin(tmp_path):
    app, _ = service(tmp_path, 'charger', 'planned')
    apply_manual(app.state, 'device', origin='home_assistant')
    event = app.state.store.events()[0]
    assert event['kind'] == 'manual' and event['details']['origin'] == 'home_assistant'


def test_refusals_keep_the_web_messages(tmp_path):
    app, _ = service(tmp_path, 'charger', 'planned')
    config = app.state.store.load_settings(); config['devices'][0]['armed'] = False
    app.state.store.save_settings(config)
    with pytest.raises(ModeRefused, match='Activer et vérifier cet appareil avant une commande'):
        apply_manual(app.state, 'device')
    with pytest.raises(ModeRefused, match='Appareil non activé'):
        apply_resume(app.state, 'device', mode='planned')
    apply_pause(app.state, 'device')  # always allowed
    with pytest.raises(DeviceNotFound):
        apply_pause(app.state, 'missing')
