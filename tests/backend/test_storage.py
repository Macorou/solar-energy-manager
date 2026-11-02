from pathlib import Path


def test_configuration_survives_reopening_and_backup(tmp_path):
    from app.storage.database import SQLiteStore
    path = tmp_path / 'app.db'
    store = SQLiteStore(path)
    store.save_settings({'timezone': 'Europe/Paris', 'off_peak': [{'start': '22:00', 'end': '06:00'}]})
    store.backup(tmp_path / 'backup.db')
    reopened = SQLiteStore(path)
    assert reopened.load_settings()['off_peak'][0]['end'] == '06:00'
    assert SQLiteStore(tmp_path / 'backup.db').load_settings()['timezone'] == 'Europe/Paris'

