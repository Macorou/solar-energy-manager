from datetime import datetime, timedelta, timezone
import sqlite3
from .redaction import Redactor

LEVELS = ('FATAL', 'ERROR', 'WARN', 'INFO', 'DEBUG', 'TRACE')
MAX_ENTRIES = 10000
RETENTION_DAYS = 7


class DiagnosticJournal:
    def __init__(self, store):
        self.store = store
        self.redactor = Redactor()
        self.dropped = 0

    def write(self, level, area, message):
        """Best effort: never hold up commands on a diagnostic DB lock/failure."""
        if not self.store.lock.acquire(timeout=.05):
            self.dropped += 1
            return
        try:
            level = {'WARNING': 'WARN', 'CRITICAL': 'FATAL'}.get(level, level)
            if level not in LEVELS:
                level = 'INFO'
            now = datetime.now(timezone.utc)
            with sqlite3.connect(self.store.path, timeout=.05) as db:
                db.execute('INSERT INTO diagnostic_logs(at,level,area,message) VALUES(?,?,?,?)',
                    (now.isoformat(), level, self.redactor.clean(area, 80), self.redactor.clean(message)))
                db.execute('DELETE FROM diagnostic_logs WHERE at < ? OR id <= '
                           '(SELECT COALESCE(max(id),0)-? FROM diagnostic_logs)',
                           ((now-timedelta(days=RETENTION_DAYS)).isoformat(), MAX_ENTRIES))
        except Exception:
            self.dropped += 1
        finally:
            self.store.lock.release()

    def query(self, level='DEBUG', areas=(), search='', after=None, before=None, limit=500):
        cutoff = (datetime.now(timezone.utc)-timedelta(days=RETENTION_DAYS)).isoformat()
        clauses, params = ['at >= ?'], [cutoff]
        allowed = LEVELS[:LEVELS.index(level)+1]
        clauses.append('level IN ('+','.join('?' for _ in allowed)+')')
        params.extend(allowed)
        if areas:
            clauses.append('area IN ('+','.join('?' for _ in areas)+')')
            params.extend(areas)
        if search:
            # instr is literal, unlike LIKE's wildcard matching. casefold supports French.
            clauses.append('instr(casefold(message),?) > 0')
            params.append(search.casefold())
        if after is not None:
            clauses.append('id > ?'); params.append(after)
        if before is not None:
            clauses.append('id < ?'); params.append(before)
        with self.store.connection() as db:
            db.create_function('casefold', 1, str.casefold)
            bounds = db.execute('SELECT min(id),max(id) FROM diagnostic_logs WHERE at >= ?', (cutoff,)).fetchone()
            available = [r[0] for r in db.execute('SELECT DISTINCT area FROM diagnostic_logs WHERE at >= ? ORDER BY area', (cutoff,))]
            rows = db.execute('SELECT * FROM diagnostic_logs WHERE '+' AND '.join(clauses)+
                (' ORDER BY id ASC LIMIT ?' if after is not None else ' ORDER BY id DESC LIMIT ?'),
                (*params, limit+1)).fetchall()
            extra = len(rows) > limit
            entries = [dict(r) for r in rows[:limit]]
            if after is None:
                entries.reverse()
            cursor = entries[-1]['id'] if after is not None and extra else (bounds[1] or after or 0)
            oldest = entries[0]['id'] if entries else before or 0
            # Existence query uses the same filters, without the supplied cursor.
            older_clauses = clauses[:]
            older_params = params[:]
            if after is not None or before is not None:
                older_clauses.pop(); older_params.pop()
            has_older = bool(oldest and db.execute('SELECT 1 FROM diagnostic_logs WHERE '+
                ' AND '.join(older_clauses)+' AND id < ? LIMIT 1', (*older_params, oldest)).fetchone())
        return {'entries': entries, 'cursor': cursor, 'has_more': extra if after is not None else False,
                'has_older': has_older, 'areas': available,
                'gap': bool(after and bounds[0] and after < bounds[0]-1),
                'retention_days': RETENTION_DAYS, 'max_entries': MAX_ENTRIES, 'dropped': self.dropped}
