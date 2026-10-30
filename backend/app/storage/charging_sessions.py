"""Local charge history. Runtime checkpoints and history have one SQLite commit.

No VIN, cloud payload, SOC buffers or access credentials enter public history.
Deleted rows are tombstoned so a delayed terminal meter value cannot revive them.
"""
import json
from datetime import datetime, timezone
from app.settings import SettingsDocument


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat() if stamp is not None else None


def history_record(device_id, session, config):
    device = next((d for d in config.devices if d.id == device_id), None)
    vehicle_id = session['vehicle'][0]
    vehicle = next((v for v in config.vehicles if v.id == vehicle_id), None)
    base = session.get('history_base', {})
    count = lambda key: session.get(key, 0) + base.get(key, 0)
    energy = count('energy_wh')
    measured = session.get('last_at') is not None or base.get('measured', False)
    partial = bool(session.get('meter_partial') or base.get('meter_partial') or session.get('terminal_pending')
        or session.get('history_meter_partial') or session.get('history_terminal_confirmed') is False)
    allocated = min(energy, max(0, count('allocated_wh')))
    solar = min(allocated, max(0, count('solar_wh')))
    priced = min(energy, max(0, count('priced_wh')))
    cost = count('cost_eur') if priced > 0 or measured and energy == 0 else None
    complete_mix = measured and not partial and energy > 0 and allocated + 1e-6 >= energy
    complete_cost = measured and not partial and priced + 1e-6 >= energy
    duration = session.get('charge_duration_s')
    if duration is not None:
        duration = duration + base.get('charge_duration_s', 0) if base.get('charge_duration_s', 0) is not None else None
    return {
        'id': session.get('history_id', session['id']), 'source': 'local',
        'device_id': device_id, 'device_name': device.name if device else device_id,
        'vehicle_id': vehicle_id, 'vehicle_name': vehicle.name if vehicle else vehicle_id or 'Véhicule inconnu',
        'started_at': iso(session.get('history_started_at', session['started_at'])),
        'ended_at': iso(session.get('ended_at')), 'active': session['active'],
        'energy_kwh': energy / 1000 if measured else None,
        'energy_partial': partial or not measured,
        'solar_kwh': solar / 1000 if measured and allocated > 0 else None,
        'grid_kwh': (allocated - solar) / 1000 if measured and allocated > 0 else None,
        'unknown_kwh': max(0, energy - allocated) / 1000 if measured else None,
        'solar_percent': 100 * solar / energy if complete_mix else None,
        'cost_eur': cost, 'cost_partial': not complete_cost,
        'average_price_per_kwh': cost / (energy / 1000) if complete_cost and energy > 0 else None,
        'charge_duration_s': duration, 'duration_partial': bool(session.get('duration_partial') or base.get('duration_partial') or duration is None),
        'soc_start': session.get('history_soc_start'), 'soc_end': session.get('soc'),
        'soc_start_source': session.get('history_soc_start_source','unavailable'),
        'soc_end_estimated': bool(session.get('soc_estimated')),
        'updated_at': iso(session.get('checked_at', session['started_at'])),
    }


class SessionHistory:
    def __init__(self, store):
        self.store = store

    def migrate(self, sessions, config=None):
        """Copy the last legacy runtime records, exactly once, without replacing edits."""
        config = config or SettingsDocument.model_validate(self.store.load_settings() or {})
        with self.store.connection() as db:
            # 0.1.20 could capture the current SOC as a migrated session start.
            # Repair historical rows lacking provenance, including older rows
            # no longer present in the latest-per-device runtime KV. Keep their
            # manual vehicle overrides and tombstones completely intact.
            repaired={s.get('history_id',s['id']):s for s in sessions.values()}
            for stored in db.execute("SELECT id,data FROM charging_history WHERE json_type(data,'$.soc_start_source') IS NULL").fetchall():
                row=json.loads(stored['data']);runtime=repaired.get(stored['id'])
                row['soc_start']=runtime.get('history_soc_start') if runtime else None
                row['soc_start_source']=runtime.get('history_soc_start_source','unavailable') if runtime else 'unavailable'
                db.execute('UPDATE charging_history SET data=? WHERE id=?',(json.dumps(row,allow_nan=False),stored['id']))
            for device_id, session in sessions.items():
                row = history_record(device_id, session, config)
                self._write(db, row, insert_only=True)
            db.execute('INSERT OR REPLACE INTO kv VALUES(?,?)',('charging_sessions',json.dumps(sessions,allow_nan=False)))

    @staticmethod
    def _write(db, row, insert_only=False):
        statement = '''INSERT INTO charging_history(id,started,device_id,vehicle_id,active,data)
            VALUES(?,?,?,?,?,?)'''
        statement += ' ON CONFLICT(id) DO NOTHING' if insert_only else ''' ON CONFLICT(id) DO UPDATE SET
            active=excluded.active, vehicle_id=excluded.vehicle_id,
            data=excluded.data WHERE charging_history.deleted=0'''
        db.execute(statement, (row['id'], datetime.fromisoformat(row['started_at']).timestamp(),
            row['device_id'], row['vehicle_id'], int(row['active']), json.dumps(row, allow_nan=False)))

    def checkpoint(self, sessions, config):
        with self.store.connection() as db:
            for device_id, session in sessions.items():
                self._write(db, history_record(device_id, session, config))
            db.execute('INSERT OR REPLACE INTO kv VALUES(?,?)', ('charging_sessions', json.dumps(sessions, allow_nan=False)))

    @staticmethod
    def decode(row, vehicles=None):
        data = json.loads(row['data'])
        override = row['vehicle_override']
        if override is not None:
            data['vehicle_id'] = override
            data['vehicle_name'] = (vehicles or {}).get(override, override or 'Véhicule inconnu')
        data['editable'] = not data['active'] and data['source'] == 'local'
        return data

    def all(self):
        config = self.store.load_settings()
        names = {v['id']: v['name'] for v in config.get('vehicles', [])}
        with self.store.connection() as db:
            return [self.decode(row, names) for row in db.execute('SELECT * FROM charging_history WHERE deleted=0 ORDER BY started DESC,id')]
