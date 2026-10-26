from pathlib import Path
import os
from cryptography.fernet import Fernet


class SecretStore:
    def __init__(self, store, key_path: Path, existing_database=False):
        self.store = store
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            if existing_database:
                raise RuntimeError('Missing encryption key for existing database')
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as output:
                output.write(Fernet.generate_key())
        self.cipher = Fernet(key_path.read_bytes())

    def set(self, name: str, value: str):
        with self.store.connection() as db:
            db.execute('INSERT OR REPLACE INTO secrets VALUES(?,?)',
                       (name, self.cipher.encrypt(value.encode())))

    def get(self, name: str) -> str | None:
        with self.store.connection() as db:
            row = db.execute('SELECT value FROM secrets WHERE key=?', (name,)).fetchone()
        return self.cipher.decrypt(row['value']).decode() if row else None

    def present(self, name: str) -> bool:
        with self.store.connection() as db:
            return db.execute('SELECT 1 FROM secrets WHERE key=?', (name,)).fetchone() is not None
