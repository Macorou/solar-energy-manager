"""Read-only PSA connected-car adapter. See docs/third-party/peugeot-provenance.md."""
import asyncio
import hashlib
import base64
import secrets as random
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode, urlparse, parse_qs
import httpx
from app.settings import PeugeotConfig
from .telemetry import parse_telemetry

CLIENT_ID = '1eebc2d5-5df3-459b-a624-20abfcf82530'
# Public mobile OAuth client identity from EVCC (MIT); never a user's credential.
CLIENT_SECRET = 'T5tP7iS0cO8sC0lA2iE2aR7gK6uE5rF3lJ8pC3nO1pR7tL8vU1'
AUTH_URL = 'https://idpcvs.peugeot.com/am/oauth2/authorize'
TOKEN_URL = 'https://idpcvs.peugeot.com/am/oauth2/access_token'
API_URL = 'https://api.groupe-psa.com/connectedcar/v4'


class ProviderError(Exception): pass


class PeugeotAdapter:
    def __init__(self, secrets, config=None, http=None, journal=None):
        self.secrets = secrets
        self.config = config or PeugeotConfig()
        self.http = http or httpx.AsyncClient(timeout=20)
        self.owns_http = http is None
        self.access = None
        self.expires = datetime.min.replace(tzinfo=timezone.utc)
        self.retry_at = self.expires
        self.error = 'not_configured'
        self.lock = asyncio.Lock()
        self.pending = None
        self.cache = {}
        self.vehicle_ids = {}
        self.journal = journal

    @property
    def client_id(self): return self.config.client_id or CLIENT_ID

    @property
    def redirect(self): return f'mymap://oauth2redirect/{self.config.country.lower()}'

    def begin_auth(self):
        state, verifier = random.token_urlsafe(32), random.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        self.pending = (state,verifier,datetime.now(timezone.utc)+timedelta(minutes=10))
        return {'url':AUTH_URL+'?'+urlencode({'client_id':self.client_id,'response_type':'code',
            'redirect_uri':self.redirect,'scope':'openid profile','state':state,
            'code_challenge':challenge,'code_challenge_method':'S256'}),
            'instructions':'Après connexion Peugeot, collez ici l’adresse mymap:// de redirection.'}

    async def complete_auth(self, response):
        parsed = urlparse(response)
        query = parse_qs(parsed.query)
        pending = self.pending
        self.pending = None
        if (not pending or datetime.now(timezone.utc) >= pending[2]
            or f'{parsed.scheme}://{parsed.netloc}{parsed.path}' != self.redirect
            or not random.compare_digest(query.get('state',[''])[0],pending[0])
            or not query.get('code')):
            raise ProviderError('invalid_callback')
        await self._token({'grant_type':'authorization_code','code':query['code'][0],
            'redirect_uri':self.redirect,'code_verifier':pending[1]})
        return {'ok':True}

    async def _token(self, data):
        now = datetime.now(timezone.utc)
        if now < self.retry_at: raise ProviderError(self.error)
        try:
            response = await self.http.post(TOKEN_URL,data=data,
                auth=(self.client_id,self.secrets.get('peugeot_client_secret') or CLIENT_SECRET))
            self._check(response)
            payload = response.json()
            self.access = payload['access_token']
            if payload.get('refresh_token'): self.secrets.set('peugeot_refresh',payload['refresh_token'])
            self.expires = now+timedelta(seconds=max(60,int(payload.get('expires_in',3600))-60))
            self.error = None
            if self.journal:self.journal.write('DEBUG','peugeot','Renouvellement de l’accès Peugeot réussi')
        except ProviderError: raise
        except Exception as error:
            if self.journal:self.journal.write('ERROR','peugeot',f'Authentification indisponible ({type(error).__name__})')
            raise ProviderError('provider_unavailable') from None

    def _check(self, response):
        if response.is_success: return
        status = response.status_code
        self.error = ('rate_limited' if status == 429 else
            'reconnect_required' if status in (400,401,403) else 'provider_unavailable')
        self.retry_at = datetime.now(timezone.utc)+timedelta(seconds=300 if status != 429 else 900)
        if self.journal:self.journal.write('ERROR','peugeot',f'Communication Peugeot : HTTP {status} ({self.error})')
        raise ProviderError(self.error)

    async def refresh_access(self):
        token = self.secrets.get('peugeot_refresh')
        if not token: raise ProviderError('not_configured')
        await self._token({'grant_type':'refresh_token','refresh_token':token})

    async def _get(self, path):
        if datetime.now(timezone.utc) >= self.expires: await self.refresh_access()
        if datetime.now(timezone.utc) < self.retry_at: raise ProviderError(self.error)
        try:
            response = await self.http.get(API_URL+path,params={'client_id':self.client_id},
                headers={'Authorization':'Bearer '+self.access,'Accept':'application/hal+json',
                         'X-Introspect-Realm':'clientsB2CPeugeot'})
            self._check(response)
            if self.journal:self.journal.write('DEBUG','peugeot','Lecture '+('des véhicules' if path=='/user/vehicles' else 'de la télémétrie')+' réussie')
            return response.json()
        except ProviderError: raise
        except Exception as error:
            if self.journal:self.journal.write('ERROR','peugeot',f'Lecture indisponible ({type(error).__name__})')
            raise ProviderError('provider_unavailable') from None

    async def read_telemetry(self, vin):
        async with self.lock:
            now = datetime.now(timezone.utc)
            if vin in self.cache and (now-self.cache[vin][0]).total_seconds() < self.config.poll_interval_s:
                return self.cache[vin][1]
            if not vin: raise ProviderError('vin_required')
            if vin not in self.vehicle_ids:
                payload = await self._get('/user/vehicles')
                self.vehicle_ids = {v['vin']:v['id'] for v in payload.get('_embedded',{}).get('vehicles',[])}
            if vin not in self.vehicle_ids: raise ProviderError('vehicle_not_found')
            value = parse_telemetry(await self._get('/user/vehicles/'+self.vehicle_ids[vin]+'/status'))
            self.cache[vin] = (now,value)
            return value

    async def close(self):
        if self.owns_http: await self.http.aclose()
