import base64
import hmac
import logging
import asyncio
from contextlib import suppress
from fastapi import WebSocket
from .station import Station

logging.getLogger('ocpp').setLevel(logging.WARNING)


class Connection:
    def __init__(self,websocket,idle_timeout=120):
        self.websocket=websocket
        self.idle_timeout=idle_timeout

    async def recv(self):
        return await asyncio.wait_for(self.websocket.receive_text(),self.idle_timeout)

    async def send(self,value):
        await self.websocket.send_text(value)


def register_server(app,registry):
    @app.websocket('/ocpp/{charge_point_id}')
    async def ocpp_socket(websocket:WebSocket,charge_point_id:str):
        configs=registry.devices(charge_point_id)
        protocols=websocket.headers.get('sec-websocket-protocol','').split(',')
        accepted=bool(configs and 'ocpp1.6' in [p.strip() for p in protocols])
        reason='unknown_station' if not configs else 'protocol_required' if not accepted else 'authentication_refused'
        try:password=registry.secret_getter('ocpp_'+charge_point_id)
        except Exception:
            password=None;accepted=False;reason='secret_unavailable'
        if accepted and password:
            try:
                scheme,value=websocket.headers.get('authorization','').split(' ',1)
                username,provided=base64.b64decode(value,validate=True).decode().split(':',1)
                accepted=scheme.lower()=='basic' and hmac.compare_digest(username,charge_point_id) and hmac.compare_digest(provided,password)
            except (ValueError,UnicodeDecodeError,TypeError):
                accepted=False
        elif accepted:
            accepted=all(d.allow_insecure_identity for d in configs)
        if not accepted or charge_point_id in registry.stations:
            reason='duplicate_connection' if accepted else reason
            if configs:registry.connection_errors[charge_point_id]=reason
            logging.getLogger(__name__).warning('OCPP connection rejected station=%r reason=%s',charge_point_id,reason)
            await websocket.close(code=1008)
            return
        await websocket.accept(subprotocol='ocpp1.6')
        station=Station(charge_point_id,Connection(websocket),registry)
        registry.stations[charge_point_id]=station
        registry.connection_errors.pop(charge_point_id,None)
        try:
            await station.start()
        except TimeoutError:
            registry.connection_errors[charge_point_id]='heartbeat_timeout'
            logging.getLogger(__name__).warning('OCPP heartbeat timeout station=%r',charge_point_id)
        except Exception:
            registry.connection_errors[charge_point_id]='connection_closed'
        finally:
            if registry.stations.get(charge_point_id) is station:
                registry.stations.pop(charge_point_id,None)
            with suppress(Exception):await websocket.close(code=1001)
