from types import SimpleNamespace
from datetime import timedelta
import pytest
from app.connectors.ocpp.registry import OcppRegistry,ChargerAdapter
from app.storage.database import SQLiteStore
from app.settings import DeviceConfig
from app.domain.commands import CommandIntent
from app.domain.measurements import utcnow


@pytest.mark.asyncio
async def test_limit_change_does_not_repeat_an_accepted_remote_start(tmp_path):
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='cp',armed=True)
    registry=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda _:None)
    calls=[]
    class Station:
        async def call(self,payload): calls.append(type(payload).__name__);return SimpleNamespace(status='Accepted')
    registry.stations['cp']=Station()
    adapter=ChargerAdapter(registry,config)
    for i,power in enumerate((2500,2700)):
        assert (await adapter.execute(CommandIntent(str(i),'ev','set_power',power,utcnow()+timedelta(seconds=90)))).accepted
    assert calls.count('RemoteStartTransaction')==1
    assert calls.count('SetChargingProfile')==2


@pytest.mark.asyncio
async def test_transaction_arriving_before_remote_start_reply_is_not_an_error(tmp_path):
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='cp',armed=True)
    registry=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda _:None)
    class Station:
        async def call(self,payload):
            if type(payload).__name__=='RemoteStartTransaction':
                registry.pending_start.pop('ev',None)
                registry.active[('cp',1)]={'transaction_id':42}
            return SimpleNamespace(status='Accepted')
    registry.stations['cp']=Station()
    result=await ChargerAdapter(registry,config).execute(CommandIntent('a','ev','set_power',2500,utcnow()+timedelta(seconds=90)))
    assert result.accepted and 'ev' not in registry.pending_start


def test_normal_transaction_keeps_requested_limit_but_cancelled_start_wakes_stop(tmp_path):
    from app.connectors.ocpp.station import Station
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='cp',armed=True)
    registry=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda _:None)
    station=Station('cp',None,registry)
    wakes=[];registry.on_transaction=wakes.append
    registry.allowed_until['ev']=utcnow()+timedelta(seconds=90)
    registry.pending_start['ev']={'state':'accepted'}
    station.start_transaction(1,'SEM',0,utcnow().isoformat())
    assert wakes==[]
    registry.allowed_until.clear();registry.pending_start['ev']={'state':'cancel_requested'}
    station.start_transaction(1,'SEM',1,utcnow().isoformat())
    assert wakes==['ev']
