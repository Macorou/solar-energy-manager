from app.connectors.ocpp.registry import OcppRegistry
from app.storage.database import SQLiteStore
from app.settings import DeviceConfig
from app.domain.devices import DeviceState
from app.domain.measurements import Quality,utcnow


def test_idle_protocol_state_is_a_labelled_estimate_not_unknown_charging_power(tmp_path):
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='cp')
    registry=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda _:None)
    registry.stations['cp']=object()
    registry.states['ev']=DeviceState('ev',observed_state='Preparing',connected=True)
    power=registry.state('ev').observed_power
    assert power and power.value==0 and power.quality==Quality.ESTIMATED
    assert 'estimation' in power.source and power.usable(utcnow(),30)
    registry.states['ev']=DeviceState('ev',observed_state='Charging',connected=True)
    assert registry.state('ev').observed_power is None
