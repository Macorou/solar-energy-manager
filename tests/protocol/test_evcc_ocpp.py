import base64
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.connectors.ocpp.profiles import build_profile
from app.connectors.ocpp.registry import OcppRegistry,ChargerAdapter
from app.connectors.ocpp.station import Station
from app.domain.commands import CommandIntent
from app.domain.devices import DeviceState
from app.domain.measurements import utcnow
from app.settings import DeviceConfig,RuntimeSettings
from app.storage.database import SQLiteStore


def config():return DeviceConfig(id='ev',name='Pulsar Plus',kind='charger',charge_point_id='box',armed=True)


def test_evcc_zero_profile_and_tenth_amp_persistent_limit():
    profile=build_profile(config(),16.9*230,42,utcnow()+timedelta(seconds=90))
    assert profile['charging_schedule']['charging_schedule_period'][0]['limit']==16.9
    assert profile['charging_profile_purpose']=='TxDefaultProfile'
    assert 'valid_to' not in profile and 'duration' not in profile['charging_schedule']
    assert 'transaction_id' not in profile
    zero=build_profile(config(),0,42,None)
    assert zero['charging_schedule']['charging_schedule_period'][0]['limit']==0


@pytest.mark.parametrize('firmware,expected_kind,expected_stack',[
    ('6.8.2','Relative',4),('5.17.20','Absolute',0)])
async def test_wallbox_firmware_profile_and_pause_resume_keep_transaction(tmp_path,firmware,expected_kind,expected_stack):
    cfg=config();reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None)
    reg.active[('box',1)]={'transaction_id':42}
    reg.metadata['box']={'vendor':'Wallbox','firmware':firmware,'model':'Pulsar Plus'}
    calls=[]
    class Wire:
        sem_profile_values={'ChargeProfileMaxStackLevel':'4','MaxChargingProfilesInstalled':'3'}
        async def call(self,message):
            calls.append(message)
            if type(message).__name__=='GetConfiguration':
                return SimpleNamespace(configuration_key=[{'key':'ChargeProfileMaxStackLevel','value':'4'},
                    {'key':'MaxChargingProfilesInstalled','value':'3'}])
            return SimpleNamespace(status='Accepted')
    reg.stations['box']=Wire();adapter=ChargerAdapter(reg,cfg)
    assert (await adapter.execute(CommandIntent('pause','ev','suspend'))).accepted
    assert (await adapter.execute(CommandIntent('resume','ev','set_power',3680,utcnow()+timedelta(seconds=90)))).accepted
    assert reg.active[('box',1)]['transaction_id']==42
    assert not any(type(item).__name__ in ('RemoteStopTransaction','RemoteStartTransaction') for item in calls)
    profiles=[item.cs_charging_profiles for item in calls if type(item).__name__=='SetChargingProfile']
    assert [item['charging_schedule']['charging_schedule_period'][0]['limit'] for item in profiles]==[0,16]
    assert all(item['charging_profile_kind']==expected_kind and item['stack_level']==expected_stack for item in profiles)


def test_periodic_meter_value_wins_over_boundary_context_and_uses_local_freshness(tmp_path):
    cfg=config();reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None)
    station=Station('box',None,reg);now=utcnow();stamp=now-timedelta(seconds=45)
    station.meter_values(1,[{'timestamp':stamp.isoformat(),'sampled_value':[
        {'value':'1010','unit':'Wh','context':'Sample.Periodic'},
        {'value':'1000','unit':'Wh','context':'Transaction.Begin'},
        {'value':'16','unit':'A','measurand':'Current.Import','phase':'L1'},
        {'value':'3.68','unit':'kW','measurand':'Power.Active.Import'}]}])
    state=reg.states['ev']
    assert state.energy_wh==1010
    assert state.currents['L1'].usable(utcnow(),30)
    assert state.observed_power.usable(utcnow(),30)


def test_reconnect_recovers_live_transaction_without_remote_start(tmp_path):
    cfg=config();reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None)
    station=Station('box',None,reg);station.status(1,'NoError','Charging')
    station.meter_values(1,[{'timestamp':utcnow().isoformat(),
        'sampled_value':[{'value':'1010','unit':'Wh'}]}],transaction_id=42)
    assert reg.active[('box',1)]['transaction_id']==42
    assert reg.states['ev'].energy_transaction_id==42


def test_ocpp_auth_survives_new_application_and_reconnect(tmp_path):
    from app.main import create_app
    from test_ocpp_sessions import exchange
    secret='test-only-ocpp-password'
    first=create_app(RuntimeSettings(data_dir=tmp_path))
    settings=first.state.store.load_settings();cfg=config();cfg.allow_insecure_identity=False
    settings['devices']=[cfg.model_dump(mode='json')];first.state.store.save_settings(settings)
    first.state.secrets.set('ocpp_box',secret)
    second=create_app(RuntimeSettings(data_dir=tmp_path))
    basic=base64.b64encode(('box:'+secret).encode()).decode()
    client=TestClient(second)
    for _ in range(2):
        with client.websocket_connect('/ocpp/box',subprotocols=['ocpp1.6'],headers={'Authorization':'Basic '+basic}) as ws:
            assert exchange(ws,'boot','BootNotification',{'chargePointVendor':'Wallbox','chargePointModel':'Pulsar Plus'})['status']=='Accepted'
    assert second.state.secrets.get('ocpp_box')==secret


def test_connection_status_exposes_saved_flag_and_blank_save_retains_secret(tmp_path):
    from app.main import create_app
    app=create_app(RuntimeSettings(data_dir=tmp_path));client=TestClient(app)
    client.post('/api/v1/setup',json={'token':(tmp_path/'bootstrap-token').read_text(),
        'username':'admin','password':'test-only-admin-password'})
    settings=app.state.store.load_settings();settings['devices']=[config().model_dump(mode='json')]
    app.state.store.save_settings(settings);app.state.secrets.set('ocpp_box','test-only-ocpp-password')
    response=client.get('/api/v1/connections/ocpp')
    assert response.status_code==200
    assert response.json()['stations'][0]['credentials_saved'] is True
    assert 'test-only-ocpp-password' not in response.text
    assert client.put('/api/v1/connections/ocpp/box',json={'password':''}).status_code==200
    assert app.state.secrets.get('ocpp_box')=='test-only-ocpp-password'


async def test_idle_socket_read_has_a_deadline():
    from app.connectors.ocpp.server import Connection
    import asyncio
    class Socket:
        async def receive_text(self):await asyncio.Event().wait()
    with pytest.raises(TimeoutError):
        await Connection(Socket(),idle_timeout=.01).recv()


async def test_ignored_zero_profile_falls_back_only_after_fresh_persistent_charge(tmp_path,monkeypatch):
    from app.domain.measurements import Sample
    cfg=config();reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None)
    reg.active[('box',1)]={'transaction_id':42};calls=[];now=utcnow()
    monkeypatch.setattr('app.connectors.ocpp.registry.utcnow',lambda:now)
    class Wire:
        async def call(self,message):
            calls.append(type(message).__name__)
            return SimpleNamespace(status='Accepted')
    reg.stations['box']=Wire();adapter=ChargerAdapter(reg,cfg)
    def charging():return DeviceState('ev',Sample(3680,'W','OCPP',now,now,checked_at=now),'Charging',True)
    reg.states['ev']=charging()
    assert (await adapter.execute(CommandIntent('pause','ev','suspend'))).accepted
    assert 'RemoteStopTransaction' not in calls
    now+=timedelta(seconds=61);reg.states['ev']=charging()
    assert (await adapter.execute(CommandIntent('retry','ev','suspend'))).accepted
    assert calls.count('RemoteStopTransaction')==1


async def test_migration_clears_only_sem_legacy_transaction_profile_after_new_cap(tmp_path):
    import zlib
    cfg=config();reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None);calls=[]
    class Wire:
        async def call(self,message):calls.append(message);return SimpleNamespace(status='Accepted')
    reg.stations['box']=Wire()
    assert (await ChargerAdapter(reg,cfg).execute(CommandIntent('cap','ev','set_power',3680))).accepted
    names=[type(message).__name__ for message in calls]
    assert names.index('SetChargingProfile')<names.index('ClearChargingProfile')<names.index('RemoteStartTransaction')
    clear=next(message for message in calls if type(message).__name__=='ClearChargingProfile')
    assert clear.id==zlib.crc32(cfg.id.encode())&0x7fffffff
    assert clear.connector_id==1 and clear.charging_profile_purpose=='TxProfile'


async def test_rejected_remote_start_rolls_positive_profile_back_to_zero(tmp_path):
    cfg=config();reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None);limits=[]
    class Wire:
        async def call(self,message):
            if type(message).__name__=='SetChargingProfile':
                limits.append(message.cs_charging_profiles['charging_schedule']['charging_schedule_period'][0]['limit'])
            return SimpleNamespace(status='Rejected' if type(message).__name__=='RemoteStartTransaction' else 'Accepted')
    reg.stations['box']=Wire()
    assert not (await ChargerAdapter(reg,cfg).execute(CommandIntent('cap','ev','set_power',3680))).accepted
    assert limits==[16,0]


def test_reconnect_boot_without_firmware_keeps_previously_detected_variant(tmp_path):
    cfg=config();reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None)
    station=Station('box',None,reg)
    station.boot('Wallbox','Pulsar Plus',firmware_version='5.17.20')
    station.boot('Wallbox','Pulsar Plus')
    assert reg.metadata['box']['firmware']=='5.17.20'


@pytest.mark.parametrize('failure',[None,'zero','cleanup'])
async def test_stop_never_depends_on_capability_query_and_revokes_authorization(tmp_path,failure):
    cfg=config();reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None)
    reg.active[('box',1)]={'transaction_id':42}
    reg.allowed_until['ev']=utcnow()+timedelta(minutes=5)
    reg.pending_start['ev']={'state':'accepted'}
    calls=[]
    class Wire:
        async def call(self,message):
            name=type(message).__name__;calls.append(name)
            assert 'ev' not in reg.allowed_until
            assert reg.pending_start['ev']['state']=='cancel_requested'
            if name=='GetConfiguration':raise TimeoutError('configuration unavailable')
            if name=='SetChargingProfile' and failure=='zero':raise TimeoutError('zero unconfirmed')
            if name=='ClearChargingProfile' and failure=='cleanup':raise TimeoutError('cleanup unconfirmed')
            return SimpleNamespace(status='Accepted')
    reg.stations['box']=Wire()
    result=await ChargerAdapter(reg,cfg).execute(CommandIntent('stop','ev','suspend'))
    assert result.accepted
    assert 'GetConfiguration' not in calls
    assert ('RemoteStopTransaction' in calls)==(failure is not None)


async def test_stop_after_restart_reuses_last_negotiated_profile_options_without_query(tmp_path):
    cfg=config();store=SQLiteStore(tmp_path/'db');limits=[]
    class Wire:
        async def call(self,message):
            if type(message).__name__=='GetConfiguration':
                return SimpleNamespace(configuration_key=[{'key':'ChargeProfileMaxStackLevel','value':'4'},
                    {'key':'MaxChargingProfilesInstalled','value':'3'}])
            if type(message).__name__=='SetChargingProfile':limits.append(message.cs_charging_profiles)
            return SimpleNamespace(status='Accepted')
    reg=OcppRegistry(store,lambda:[cfg],lambda _:None);reg.stations['box']=Wire()
    reg.active[('box',1)]={'transaction_id':42};reg.save_transactions()
    assert (await ChargerAdapter(reg,cfg).execute(CommandIntent('cap','ev','set_power',3680))).accepted
    restarted=OcppRegistry(store,lambda:[cfg],lambda _:None);restarted.stations['box']=Wire()
    assert (await ChargerAdapter(restarted,cfg).execute(CommandIntent('stop','ev','suspend'))).accepted
    assert limits[-1]['stack_level']==4
    assert limits[-1]['charging_profile_id']==3


async def test_offline_stop_cancels_a_pending_start_and_revokes_authorization(tmp_path):
    cfg=config();reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None)
    reg.allowed_until['ev']=utcnow()+timedelta(minutes=5);reg.pending_start['ev']={'state':'accepted'}
    assert not (await ChargerAdapter(reg,cfg).execute(CommandIntent('stop','ev','suspend'))).accepted
    assert not reg.authorized(cfg)
    assert reg.pending_start['ev']['state']=='cancel_requested'
