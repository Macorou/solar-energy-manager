import asyncio
import inspect
import json
import time
from dataclasses import replace
from urllib.parse import urlsplit, urlunsplit
import httpx
import websockets
from app.domain.measurements import Quality, utcnow
from app.domain.site import SiteSnapshot
from app.settings import HomeAssistantConfig
from .mapping import normalize_power


class HomeAssistantSource:
    def __init__(self, config: HomeAssistantConfig, token: str, http=None, max_age_s=30, journal=None):
        self.config, self.token = config, token
        self.http = http
        self.max_age_s = max_age_s
        self.states = {}
        self.received = {}
        self.connected = False
        self.running = False
        self.websocket = None
        self.error = None
        self.journal = journal
        self.logged_at = None
        if journal: journal.redactor.register(token)

    async def connect(self):
        parsed = urlsplit(self.config.url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username:
            raise ValueError('Adresse Home Assistant HTTP(S) requise')
        client = self.http or httpx.AsyncClient(timeout=10)
        try:
            response = await client.get(self.config.url.rstrip('/')+'/api/states',
                headers={'Authorization': 'Bearer '+self.token})
            response.raise_for_status()
            self.states = {state['entity_id']: state for state in response.json()}
            self.received = {entity_id: utcnow() for entity_id in self.states}
            required = [self.config.grid_entity] + list(self.config.device_power_entities.values())
            if not self.config.grid_entity or any(entity not in self.states for entity in required):
                raise ValueError('Mesures configurées introuvables')
            for entity in required:
                normalize_power(self.states[entity], self.received[entity])
            self.connected, self.error = True, None
            # States are re-read every second; one success line a minute is enough.
            # The monotonic clock starts near 0 on a freshly booted host: log the first read.
            if self.journal and (self.logged_at is None or time.monotonic()-self.logged_at>=60):
                self.journal.write('DEBUG','ha',f'Lecture des états réussie : {len(self.states)} entités')
                self.logged_at=time.monotonic()
        except Exception as error:
            self.connected = False
            if self.journal:
                status=f'HTTP {error.response.status_code}' if isinstance(error,httpx.HTTPStatusError) else type(error).__name__
                self.journal.write('ERROR','ha','Lecture des états impossible : '+status)
            raise
        finally:
            if self.http is None:
                await client.aclose()

    def power(self, entity, invert=False):
        if not entity or entity not in self.states:
            return None
        sample = normalize_power(self.states[entity], self.received.get(entity,utcnow()), invert)
        return sample if self.connected else replace(sample, quality=Quality.UNAVAILABLE)

    def snapshot(self):
        # Optional display-only meter: its absence or rejection must not
        # invalidate the electrical sources used by the controller.
        try:
            house=self.power(self.config.house_entity)
        except (ValueError,TypeError,AttributeError,OverflowError):
            house=None
        if house and house.value is not None and house.value<0:
            house=replace(house,quality=Quality.UNAVAILABLE)
        return SiteSnapshot(at=utcnow(), grid=self.power(self.config.grid_entity,self.config.invert_grid),
            solar=self.power(self.config.solar_entity), sample_max_age_s=self.max_age_s,house=house,
            phase_currents={p:self.measure(c.current_entity,{'A':1,'mA':.001},'A') for p,c in self.config.phases.items()},
            phase_voltages={p:self.measure(c.voltage_entity,{'V':1},'V') for p,c in self.config.phases.items()},
            phase_powers={p:self.measure(c.power_entity,{'W':1,'kW':1000},'W') for p,c in self.config.phases.items()},
            phase_limits_a={p:c.max_current_a for p,c in self.config.phases.items()},
            price=self.measure(self.config.price_entity,{'€/kWh':1,'EUR/kWh':1,'EUR/kwh':1},'€/kWh'))

    def measure(self, entity, units, unit):
        if not entity or entity not in self.states: return None
        try:
            raw=self.states[entity]; attrs=raw.get('attributes',{})
            scale=units[attrs.get('unit_of_measurement')]
            normalized=dict(raw,state=str(float(raw['state'])*scale),attributes=dict(attrs,unit_of_measurement='W'))
            result=replace(normalize_power(normalized,self.received.get(entity,utcnow())),unit=unit)
            return result if self.connected else replace(result,quality=Quality.UNAVAILABLE)
        except (ValueError,KeyError,TypeError,AttributeError,OverflowError): return None

    def device_power(self, device_id):
        return self.power(self.config.device_power_entities.get(device_id,''))

    async def subscribe(self, callback):
        self.running = True
        delay = 2
        while self.running:
            try:
                parsed = urlsplit(self.config.url)
                url = urlunsplit(('wss' if parsed.scheme=='https' else 'ws',parsed.netloc,
                                 parsed.path.rstrip('/')+'/api/websocket','',''))
                async with websockets.connect(url,open_timeout=10) as websocket:
                    self.websocket = websocket
                    await websocket.recv()
                    await websocket.send(json.dumps({'type':'auth','access_token':self.token}))
                    authenticated = json.loads(await websocket.recv())
                    if authenticated.get('type') != 'auth_ok':
                        raise ValueError('Authentification Home Assistant refusée')
                    await self.connect()
                    if self.journal:self.journal.write('INFO','ha','Abonnement aux mesures Home Assistant connecté')
                    await websocket.send(json.dumps({'id':1,'type':'subscribe_events','event_type':'state_changed'}))
                    delay = 2
                    interval=min(1,self.max_age_s/2)
                    refresh_at=asyncio.get_running_loop().time()+interval
                    while self.running:
                        try:
                            remaining=refresh_at-asyncio.get_running_loop().time()
                            if remaining <= 0:
                                raise TimeoutError
                            raw=await asyncio.wait_for(websocket.recv(),remaining)
                        except TimeoutError:
                            # Confirm HA's available values even if their value timestamps
                            # have not changed. Busy unrelated events must not starve this read.
                            await self.connect()
                            refresh_at=asyncio.get_running_loop().time()+interval
                            result=callback(self.snapshot())
                            if inspect.isawaitable(result): await result
                            continue
                        message = json.loads(raw)
                        if message.get('type') == 'event':
                            data = message.get('event',{}).get('data',{})
                            state = data.get('new_state')
                            if state:
                                self.states[data['entity_id']] = state
                                self.received[data['entity_id']] = utcnow()
                            elif data.get('entity_id'):
                                self.states.pop(data['entity_id'],None)
                            result = callback(self.snapshot())
                            if inspect.isawaitable(result):
                                await result
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.error = 'Connexion Home Assistant indisponible'
                if self.journal:self.journal.write('ERROR','ha',f'Connexion WebSocket indisponible ({type(error).__name__}) ; nouvelle tentative dans {delay} s')
            finally:
                self.connected = False
                self.websocket = None
            if self.running:
                await asyncio.sleep(delay)
                delay = min(delay*2,30)

    async def close(self):
        self.running = False
        self.connected = False
        if self.websocket:
            await self.websocket.close()

