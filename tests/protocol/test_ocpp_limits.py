from types import SimpleNamespace
from datetime import timedelta
from app.domain.commands import CommandIntent
from app.domain.measurements import utcnow
import pytest


async def test_current_is_floored_and_acceptance_is_not_observation(tmp_path):
    from app.connectors.ocpp.profiles import build_profile
    from app.settings import DeviceConfig
    config=DeviceConfig(id='ev',name='EV',kind='charger',phases=1,min_power_w=1380,max_power_w=7400)
    profile=build_profile(config,3700,None,utcnow()+timedelta(seconds=90))
    assert profile['charging_schedule']['charging_schedule_period'][0]['limit']==16
    with pytest.raises(ValueError):
        build_profile(config,100,None,utcnow()+timedelta(seconds=90))


async def test_suspend_uses_zero_profile_and_preserves_transaction(tmp_path):
    from app.connectors.ocpp.registry import OcppRegistry,ChargerAdapter
    from app.storage.database import SQLiteStore
    from app.settings import DeviceConfig
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='pulsar')
    registry=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda key:None)
    registry.active[('pulsar',1)]={'transaction_id':42}
    calls=[]
    class Wire:
        async def call(self,message):
            calls.append(message)
            return SimpleNamespace(status='Accepted')
    registry.stations['pulsar']=Wire()
    result=await ChargerAdapter(registry,config).execute(CommandIntent('stop','ev','suspend'))
    profiles=[call for call in calls if call.__class__.__name__=='SetChargingProfile']
    assert profiles[0].cs_charging_profiles['charging_schedule']['charging_schedule_period'][0]['limit']==0
    assert registry.active[('pulsar',1)]['transaction_id']==42
    assert not any(call.__class__.__name__=='RemoteStopTransaction' for call in calls)
    assert result.accepted and not result.observed
