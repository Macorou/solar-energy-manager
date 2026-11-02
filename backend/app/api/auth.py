import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix='/api/v1')
hasher = PasswordHasher()
# A session lasts 30 days after its last use; renewing at most hourly avoids a write per poll.
SESSION_S = 30 * 86400
RENEW_AFTER_S = 3600
BROWSERS = (('Home Assistant', 'Home Assistant'), ('Edg', 'Edge'), ('OPR/', 'Opera'), ('FxiOS', 'Firefox'),
            ('Firefox/', 'Firefox'), ('CriOS', 'Chrome'), ('Chrome/', 'Chrome'), ('Safari/', 'Safari'))
SYSTEMS = (('iPhone', 'iPhone'), ('iPad', 'iPad'), ('Android', 'Android'), ('Windows', 'Windows'),
           ('Macintosh', 'macOS'), ('iOS', 'iOS'), ('Linux', 'Linux'))


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


class Setup(Credentials):
    token: str


class ConnectedDevice(BaseModel):
    id: str
    device: str
    ip: str
    created_at: datetime | None
    last_seen_at: datetime | None
    current: bool


def describe_agent(agent):
    found = [next((label for key, label in table if key in agent), None) for table in (BROWSERS, SYSTEMS)]
    return ' · '.join(label for label in found if label) or 'Appareil inconnu'


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def stamp(value):
    return None if value is None else datetime.fromtimestamp(value, timezone.utc)


def set_session_cookie(request, response, token):
    response.set_cookie('sem_session', token, httponly=True, samesite='strict',
        secure=request.app.state.runtime_settings.secure_cookie, max_age=SESSION_S)


def remember(db, hashed, request, now, created=None):
    """Record the device behind a session; sessions from older releases have none yet."""
    agent, ip = request.headers.get('user-agent', '')[:300], request.client.host if request.client else ''
    if not db.execute('UPDATE session_info SET last_seen=?, user_agent=?, ip=? WHERE token_hash=?',
            (now, agent, ip, hashed)).rowcount:
        db.execute('INSERT INTO session_info VALUES(?,?,?,?,?,?)',
            (hashed, secrets.token_urlsafe(9), created, now, agent, ip))


def forget(db, hashed):
    db.execute('DELETE FROM sessions WHERE token_hash=?', (hashed,))
    db.execute('DELETE FROM session_info WHERE token_hash=?', (hashed,))


def require_auth(request: Request, response: Response):
    token = request.cookies.get('sem_session', '')
    hashed = token_hash(token)
    now = time.time()
    with request.app.state.store.connection() as db:
        session = db.execute('SELECT expires FROM sessions WHERE token_hash=?', (hashed,)).fetchone()
    if not session or session['expires'] < now:
        raise HTTPException(401, 'Connexion requise')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        expected = request.app.state.runtime_settings.public_url or str(request.base_url)
        if origin and urlsplit(origin).netloc != urlsplit(expected).netloc:
            raise HTTPException(403, 'Origine refusée')
        if request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(403, 'Origine refusée')
    if session['expires'] < now + SESSION_S - RENEW_AFTER_S:
        with request.app.state.store.connection() as db:
            db.execute('UPDATE sessions SET expires=? WHERE token_hash=?', (now + SESSION_S, hashed))
            remember(db, hashed, request, now)
        set_session_cookie(request, response, token)
    return True


def issue_session(request, response):
    token = secrets.token_urlsafe(32)
    now = time.time()
    with request.app.state.store.connection() as db:
        db.execute('DELETE FROM sessions WHERE expires < ?', (now,))
        db.execute('DELETE FROM session_info WHERE token_hash NOT IN (SELECT token_hash FROM sessions)')
        db.execute('INSERT INTO sessions VALUES(?,?)', (token_hash(token), now + SESSION_S))
        remember(db, token_hash(token), request, now, created=now)
    set_session_cookie(request, response, token)


@router.get('/setup/status')
def setup_status(request: Request):
    with request.app.state.store.connection() as db:
        configured = db.execute('SELECT 1 FROM users LIMIT 1').fetchone() is not None
    return {'configured': configured}


@router.post('/setup')
def setup(body: Setup, request: Request, response: Response):
    store = request.app.state.store
    with store.connection() as db:
        if db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            raise HTTPException(409, 'Installation déjà configurée')
        expected = (request.app.state.runtime_settings.data_dir / 'bootstrap-token').read_text().strip()
        if not hmac.compare_digest(body.token.strip(), expected):
            raise HTTPException(403, 'Code de première installation incorrect')
        if len(body.password) < 12:
            raise HTTPException(422, 'Utilisez au moins 12 caractères')
        db.execute('INSERT INTO users VALUES(?,?)', (body.username, hasher.hash(body.password)))
    issue_session(request, response)
    return {'ok': True}


@router.post('/auth/login')
def login(body: Credentials, request: Request, response: Response):
    ip = request.client.host if request.client else 'local'
    recent = [ts for ts in request.app.state.login_attempts.get(ip, []) if ts > time.time()-60]
    if len(recent) >= 10:
        raise HTTPException(429, 'Réessayez dans une minute')
    request.app.state.login_attempts[ip] = recent + [time.time()]
    with request.app.state.store.connection() as db:
        row = db.execute('SELECT password_hash FROM users WHERE username=?', (body.username,)).fetchone()
    try:
        if not row or not hasher.verify(row['password_hash'], body.password):
            raise HTTPException(401, 'Identifiants incorrects')
    except VerificationError:
        raise HTTPException(401, 'Identifiants incorrects') from None
    request.app.state.login_attempts[ip] = []
    issue_session(request, response)
    return {'ok': True}


@router.post('/auth/logout')
def logout(request: Request, response: Response):
    require_auth(request, response)
    with request.app.state.store.connection() as db:
        forget(db, token_hash(request.cookies.get('sem_session', '')))
    response.delete_cookie('sem_session')
    return {'ok': True}


@router.get('/auth/sessions', response_model=list[ConnectedDevice], dependencies=[Depends(require_auth)])
def connected_devices(request: Request):
    current, now = token_hash(request.cookies.get('sem_session', '')), time.time()
    with request.app.state.store.connection() as db:
        for row in db.execute('SELECT token_hash FROM sessions WHERE expires >= ? AND token_hash NOT IN '
                '(SELECT token_hash FROM session_info)', (now,)).fetchall():
            db.execute('INSERT INTO session_info VALUES(?,?,?,?,?,?)',
                (row['token_hash'], secrets.token_urlsafe(9), None, None, '', ''))
        rows = db.execute('SELECT i.* FROM session_info i JOIN sessions s USING(token_hash) WHERE s.expires >= ? '
            'ORDER BY i.created IS NULL, i.created DESC', (now,)).fetchall()
    return [ConnectedDevice(id=row['id'], device=describe_agent(row['user_agent']), ip=row['ip'],
        created_at=stamp(row['created']), last_seen_at=stamp(row['last_seen']),
        current=row['token_hash'] == current) for row in rows]


@router.delete('/auth/sessions/{device_id}', dependencies=[Depends(require_auth)])
def disconnect_device(device_id: str, request: Request, response: Response):
    with request.app.state.store.connection() as db:
        row = db.execute('SELECT token_hash, user_agent FROM session_info WHERE id=?', (device_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Appareil introuvable')
        forget(db, row['token_hash'])
    request.app.state.store.journal.write('INFO', 'auth', 'Appareil déconnecté : '+describe_agent(row['user_agent']))
    if row['token_hash'] == token_hash(request.cookies.get('sem_session', '')):
        response.delete_cookie('sem_session')
    return {'ok': True}


@router.post('/auth/sessions/revoke-others', dependencies=[Depends(require_auth)])
def disconnect_other_devices(request: Request):
    current, now = token_hash(request.cookies.get('sem_session', '')), time.time()
    with request.app.state.store.connection() as db:
        others = db.execute('SELECT token_hash, expires FROM sessions WHERE token_hash<>?', (current,)).fetchall()
        for row in others:
            forget(db, row['token_hash'])
    revoked = sum(row['expires'] >= now for row in others)
    if revoked:
        request.app.state.store.journal.write('INFO', 'auth', f'Autres appareils déconnectés : {revoked}')
    return {'revoked': revoked}
