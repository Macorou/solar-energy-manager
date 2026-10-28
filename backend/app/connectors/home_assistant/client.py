import asyncio
import inspect
import json
from dataclasses import replace
from urllib.parse import urlsplit, urlunsplit
import httpx
import websockets
from app.domain.measurements import Quality, utcnow
from app.domain.site import SiteSnapshot
from app.settings import HomeAssistantConfig
from .mapping import normalize_power


class HomeAssistantSource:
    def __init__(self, config: HomeAssistantConfig, token: str, http=None, max_age_s=30):
        self.config, self.token = config, token
        self.http = http
        self.max_age_s = max_age_s
        self.states = {}
        self.received = {}
        self.connected = False
        self.running = False
        self.websocket = None
        self.error = None

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
        except Exception:
            self.connected = False
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
            solar=self.power(self.config.solar_entity), sample_max_age_s=self.max_age_s,house=house)

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
            except Exception:
                self.error = 'Connexion Home Assistant indisponible'
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

