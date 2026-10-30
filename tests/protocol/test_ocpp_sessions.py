from datetime import datetime,timezone
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest


def ocpp_app(tmp_path):
    from app.main import create_app
    from app.settings import RuntimeSettings
    app=create_app(RuntimeSettings(data_dir=tmp_path))
    settings=app.state.store.load_settings()
    settings['devices']=[{'id':'wallbox','name':'Garage','kind':'charger','charge_point_id':'pulsar',
        'connector_id':1,'allow_insecure_identity':True}]
    app.state.store.save_settings(settings)
    return app


def exchange(ws,uid,action,body):
    ws.send_json([2,uid,action,body])
    result=ws.receive_json()
    assert result[0]==3, result
    return result[2]


def test_ocpp_boot_status_meter_and_durable_transaction(tmp_path):
    app=ocpp_app(tmp_path)
    client=TestClient(app)
    with client.websocket_connect('/ocpp/pulsar',subprotocols=['ocpp1.6']) as ws:
        boot=exchange(ws,'b','BootNotification',{'chargePointVendor':'Wallbox','chargePointModel':'Pulsar Plus'})
        assert boot['status']=='Accepted'
        stamp=datetime.now(timezone.utc).isoformat()
        exchange(ws,'s','StatusNotification',{'connectorId':1,'status':'Charging','errorCode':'NoError'})
        start={'connectorId':1,'idTag':'SEM','meterStart':1000,'timestamp':stamp}
        tx=exchange(ws,'t','StartTransaction',start)['transactionId']
        exchange(ws,'m','MeterValues',{'connectorId':1,'transactionId':tx,'meterValue':[
            {'timestamp':stamp,'sampledValue':[{'measurand':'Power.Active.Import','unit':'kW','value':'3.6'}]}]})
        assert app.state.ocpp.state('wallbox').observed_power.value==3600
    with client.websocket_connect('/ocpp/pulsar',subprotocols=['ocpp1.6']) as ws:
        assert exchange(ws,'t2','StartTransaction',start)['transactionId']==tx


def test_unknown_station_is_rejected(tmp_path):
    app=ocpp_app(tmp_path)
    with pytest.raises(WebSocketDisconnect) as error:
        with TestClient(app).websocket_connect('/ocpp/unknown',subprotocols=['ocpp1.6']):
            pass
    assert error.value.code==1008


def test_terminal_meter_after_available_preserves_unplugged_state(tmp_path):
    app=ocpp_app(tmp_path)
    with TestClient(app).websocket_connect('/ocpp/pulsar',subprotocols=['ocpp1.6']) as ws:
        stamp=datetime.now(timezone.utc).isoformat()
        tx=exchange(ws,'t','StartTransaction',{'connectorId':1,'idTag':'SEM','meterStart':1000,'timestamp':stamp})['transactionId']
        exchange(ws,'a','StatusNotification',{'connectorId':1,'status':'Available','errorCode':'NoError'})
        exchange(ws,'e','StopTransaction',{'meterStop':1500,'timestamp':stamp,'transactionId':tx})
        state=app.state.ocpp.state('wallbox')
        assert state.energy_wh==1500
        assert state.energy_terminal is True
        assert state.vehicle_connected is False
        assert state.observed_state=='Available'
