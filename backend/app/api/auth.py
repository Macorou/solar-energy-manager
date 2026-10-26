import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix='/api/v1')
hasher = PasswordHasher()


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


class Setup(Credentials):
    token: str


def require_auth(request: Request):
    token = request.cookies.get('sem_session', '')
    hashed = hashlib.sha256(token.encode()).hexdigest()
    with request.app.state.store.connection() as db:
        session = db.execute('SELECT expires FROM sessions WHERE token_hash=?', (hashed,)).fetchone()
    if not session or session['expires'] < time.time():
        raise HTTPException(401, 'Connexion requise')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        expected = request.app.state.runtime_settings.public_url or str(request.base_url)
        if origin and urlsplit(origin).netloc != urlsplit(expected).netloc:
            raise HTTPException(403, 'Origine refusée')
        if request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(403, 'Origine refusée')
    return True


def issue_session(request, response):
    token = secrets.token_urlsafe(32)
    with request.app.state.store.connection() as db:
        db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
        db.execute('INSERT INTO sessions VALUES(?,?)',
            (hashlib.sha256(token.encode()).hexdigest(), time.time() + 43200))
    response.set_cookie('sem_session', token, httponly=True, samesite='strict',
        secure=request.app.state.runtime_settings.secure_cookie, max_age=43200)


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
    require_auth(request)
    token = request.cookies.get('sem_session', '')
    with request.app.state.store.connection() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie('sem_session')
    return {'ok': True}
