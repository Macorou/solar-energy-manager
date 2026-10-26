from test_ocpp_sessions import ocpp_app,exchange
from fastapi.testclient import TestClient


def test_disconnect_means_unavailable_not_zero_power(tmp_path):
    app=ocpp_app(tmp_path)
    with TestClient(app).websocket_connect('/ocpp/pulsar',subprotocols=['ocpp1.6']) as ws:
        exchange(ws,'b','BootNotification',{'chargePointVendor':'Wallbox','chargePointModel':'Pulsar Plus'})
        exchange(ws,'s','StatusNotification',{'connectorId':1,'status':'Available','errorCode':'NoError'})
        assert app.state.ocpp.state('wallbox').connected
    assert not app.state.ocpp.state('wallbox').connected
