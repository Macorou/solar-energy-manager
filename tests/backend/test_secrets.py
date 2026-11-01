import pytest


def test_provider_access_is_encrypted_and_not_returned_as_setting(tmp_path):
    from app.main import create_app
    from app.settings import RuntimeSettings
    app = create_app(RuntimeSettings(data_dir=tmp_path))
    app.state.secrets.set('ha_token', 'private-token-that-must-not-be-plaintext')
    assert app.state.secrets.get('ha_token') == 'private-token-that-must-not-be-plaintext'
    assert b'private-token-that-must-not-be-plaintext' not in (tmp_path / 'app.db').read_bytes()
    assert 'ha_token' not in app.state.store.load_settings()


def test_missing_key_for_existing_database_fails_instead_of_replacing_it(tmp_path):
    from app.main import create_app
    from app.settings import RuntimeSettings
    create_app(RuntimeSettings(data_dir=tmp_path))
    (tmp_path / 'secrets' / 'master.key').unlink()
    with pytest.raises(RuntimeError, match='key|clé'):
        create_app(RuntimeSettings(data_dir=tmp_path))


def test_delete_removes_secret_and_is_idempotent(tmp_path):
    from app.main import create_app
    from app.settings import RuntimeSettings
    app = create_app(RuntimeSettings(data_dir=tmp_path))
    secrets = app.state.secrets
    secrets.set('mqtt_password', 'to-be-deleted')
    assert secrets.present('mqtt_password')
    secrets.delete('mqtt_password')
    assert not secrets.present('mqtt_password') and secrets.get('mqtt_password') is None
    secrets.delete('mqtt_password')
    secrets.delete('never-existed')
