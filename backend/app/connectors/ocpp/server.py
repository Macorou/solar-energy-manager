import base64
import hmac
import logging
from fastapi import WebSocket
from .station import Station

logging.getLogger('ocpp').setLevel(logging.WARNING)


class Connection:
    def __init__(self,websocket):
        self.websocket=websocket

    async def recv(self):
        return await self.websocket.receive_text()

    async def send(self,value):
        await self.websocket.send_text(value)


def register_server(app,registry):
    @app.websocket('/ocpp/{charge_point_id}')
    async def ocpp_socket(websocket:WebSocket,charge_point_id:str):
        configs=registry.devices(charge_point_id)
        protocols=websocket.headers.get('sec-websocket-protocol','').split(',')
        accepted=bool(configs and 'ocpp1.6' in [p.strip() for p in protocols])
        password=registry.secret_getter('ocpp_'+charge_point_id)
        if accepted and password:
            try:
                scheme,value=websocket.headers.get('authorization','').split(' ',1)
                username,provided=base64.b64decode(value).decode().split(':',1)
                accepted=scheme.lower()=='basic' and hmac.compare_digest(username,charge_point_id) and hmac.compare_digest(provided,password)
            except (ValueError,UnicodeDecodeError):
                accepted=False
        elif accepted:
            accepted=all(d.allow_insecure_identity for d in configs)
        if not accepted or charge_point_id in registry.stations:
            await websocket.close(code=1008)
            return
        await websocket.accept(subprotocol='ocpp1.6')
        station=Station(charge_point_id,Connection(websocket),registry)
        registry.stations[charge_point_id]=station
        try:
            await station.start()
        except Exception:
            pass
        finally:
            if registry.stations.get(charge_point_id) is station:
                registry.stations.pop(charge_point_id,None)
