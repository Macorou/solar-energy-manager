from contextlib import contextmanager
from pathlib import Path
from threading import RLock
import json
import sqlite3
from app.domain.measurements import utcnow


class SQLiteStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS secrets(key TEXT PRIMARY KEY, value BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at TEXT NOT NULL, kind TEXT NOT NULL, device_id TEXT, details TEXT NOT NULL);
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    def get(self, key, default=None):
        with self.connection() as db:
            row = db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default

    def set(self, key, value):
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO kv VALUES(?,?)', (key, json.dumps(value)))

    def load_settings(self):
        return self.get('settings', {})

    def save_settings(self, settings):
        self.set('settings', settings)

    def append_event(self, event):
        with self.connection() as db:
            db.execute('INSERT INTO events(at,kind,device_id,details) VALUES(?,?,?,?)',
                (event.get('at', utcnow().isoformat()), event['kind'], event.get('device_id'),
                 json.dumps(event.get('details', {}))))
            db.execute('DELETE FROM events WHERE id < (SELECT max(id)-10000 FROM events)')

    def events(self, limit=200):
        with self.connection() as db:
            rows = db.execute('SELECT * FROM events ORDER BY id DESC LIMIT ?', (min(limit, 1000),)).fetchall()
        return [dict(row) | {'details': json.loads(row['details'])} for row in rows]

    def backup(self, destination):
        with self.connection() as source:
            with sqlite3.connect(destination) as target:
                source.backup(target)
