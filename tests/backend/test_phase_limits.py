from dataclasses import replace
from datetime import timedelta

import pytest
from app.domain.measurements import Sample, utcnow
from app.domain.devices import DeviceState, DeviceSpec
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.settings import HomeAssistantConfig
from app.connectors.home_assistant.client import HomeAssistantSource


def test_evcc_delta_limit_credits_measured_charge_and_reduces_overload():
    from app.engine.phase_limits import validate_current
    assert validate_current(10,16,18,20,1)==11
    assert validate_current(10,16,22,20,1)==7
    assert validate_current(0,16,15,20,1)==4
    assert validate_current(10,5,18,20,1)==5


@pytest.mark.parametrize('phase,expected',[('L1',2530),('L2',3680)])
def test_engine_applies_only_used_phase_without_cloud_grace(phase,expected):
    from app.simulation.clock import SimulatedClock
    from app.engine.engine import CHARGER_RAISE_S
    clock=SimulatedClock(utcnow())
    def frame():
        now=clock.now(); s=lambda v,u='W':Sample(v,u,'test',now,now)
        return SiteSnapshot(now,grid=s(4000),solar=s(0),site_limit_w=12000,
            device_states={'ev':DeviceState('ev',s(2300),'Charging',True,vehicle_connected=True,
                currents={'L1':s(10,'A')})},
            phase_currents={'L1':s(18,'A'),'L2':s(4,'A'),'L3':s(4,'A')},
            phase_limits_a={'L1':20,'L2':20,'L3':20},phase_margin_a=1,phase_control_enabled=True)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700,
        grid_phases=(phase,),voltage=230,min_current_a=6,max_current_a=16)
    engine=EnergyEngine(clock);engine.requested['ev']=2300
    policies={'ev':DevicePolicy('ev','manual',armed=True,manual_until=clock.now()+timedelta(hours=1))}
    assert engine.evaluate(frame(),[spec],policies,{}).commands==()  # an increase holds for a minute
    clock.advance(CHARGER_RAISE_S)
    assert engine.evaluate(frame(),[spec],policies,{}).commands[0].limit_w==expected


def test_ha_reads_amperes_and_price_without_power_unit_confusion():
    now=utcnow(); cfg=HomeAssistantConfig(grid_entity='grid',price_entity='price',
        phases={'L1':{'current_entity':'amps','power_entity':'bad_va','max_current_a':20}})
    source=HomeAssistantSource(cfg,'test');source.connected=True
    def entity(v,u):return {'entity_id':'x','state':str(v),'attributes':{'unit_of_measurement':u},'last_updated':(now-timedelta(days=1)).isoformat()}
    source.states={'grid':entity(400,'W'),'amps':entity(3300,'mA'),'price':entity(.1654,'€/kWh'),'bad_va':entity(500,'VA')}
    source.received=dict.fromkeys(source.states,now)
    state=source.snapshot()
    assert state.phase_currents['L1'].value==pytest.approx(3.3)
    assert state.phase_currents['L1'].usable(now,30)
    assert state.price.value==.1654
    assert state.phase_powers['L1'] is None or not state.phase_powers['L1'].usable(now,30)


def test_pending_other_charger_does_not_spend_phase_margin_twice():
    from app.domain.devices import Reservation
    now=utcnow();s=lambda v,u='W':Sample(v,u,'test',now,now)
    snapshot=SiteSnapshot(now,grid=s(500),solar=s(0),site_limit_w=12000,
        device_states={k:DeviceState(k,s(0),'Preparing',True,vehicle_connected=True) for k in ('first','second')},
        reservations=(Reservation('first',2300,'pending',now+timedelta(minutes=1)),),
        phase_currents={'L1':s(3,'A')},phase_limits_a={'L1':20},phase_margin_a=1,phase_control_enabled=True)
    specs=[DeviceSpec(k,'charger',min_power_w=1380,max_power_w=3700,grid_phases=('L1',),max_current_a=16,priority=2 if k=='first' else 1) for k in ('first','second')]
    policies={k:DevicePolicy(k,'manual',armed=True,manual_until=now+timedelta(hours=1)) for k in ('first','second')}
    engine=EnergyEngine();engine.requested['first']=2300
    result=engine.evaluate(snapshot,specs,policies,{})
    assert next(c for c in result.commands if c.device_id=='second').limit_w<=1380


def test_ocpp_energy_only_and_current_frames_are_not_lost(tmp_path):
    from app.connectors.ocpp.registry import OcppRegistry
    from app.connectors.ocpp.station import Station
    from app.storage.database import SQLiteStore
    from app.settings import DeviceConfig
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='box')
    registry=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda _:None)
    station=Station('box',None,registry); stamp=utcnow().isoformat()
    station.meter_values(1,[{'timestamp':stamp,'sampled_value':[
        {'measurand':'Energy.Active.Import.Register','value':'12.5','unit':'kWh'},
        {'measurand':'Current.Import','value':'10','unit':'A','phase':'L1'}]}])
    assert registry.states['ev'].energy_wh==12500
    assert registry.states['ev'].energy_measured_at.isoformat()==stamp
    assert registry.states['ev'].currents['L1'].value==10


def test_ocpp_start_keeps_transaction_meter_base_until_later_meter_frames(tmp_path,monkeypatch):
    from app.connectors.ocpp.registry import OcppRegistry
    from app.connectors.ocpp.station import Station
    from app.storage.database import SQLiteStore
    from app.settings import DeviceConfig
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='box')
    registry=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda _:None)
    station=Station('box',None,registry);now=utcnow()
    monkeypatch.setattr('app.connectors.ocpp.readings.utcnow',lambda:now+timedelta(seconds=11))
    result=station.start_transaction(1,'SEM',5000922,now.isoformat())
    station.meter_values(1,[{'timestamp':(now+timedelta(seconds=5)).isoformat(),
        'sampled_value':[{'value':'5000928','unit':'Wh'}]}],transaction_id=result.transaction_id)
    state=registry.states['ev']
    assert state.energy_transaction_id==result.transaction_id
    assert state.energy_transaction_start_wh==5000922
    assert state.energy_transaction_started_at==now
    assert state.energy_wh==5000928
    # A controller restart must recover that identity from the active transaction.
    restored=OcppRegistry(registry.store,lambda:[config],lambda _:None)
    reconnected=Station('box',None,restored)
    reconnected.meter_values(1,[{'timestamp':(now+timedelta(seconds=10)).isoformat(),
        'sampled_value':[{'value':'5000934','unit':'Wh'}]}],transaction_id=result.transaction_id)
    state=restored.states['ev']
    assert state.energy_transaction_id==result.transaction_id
    assert state.energy_transaction_start_wh==5000922
    assert state.energy_transaction_started_at==now


def test_a_charge_below_minimum_does_not_reserve_current_it_will_never_use():
    from app.engine.phase_limits import phase_power_limit
    now=utcnow();s=lambda v,u='W':Sample(v,u,'test',now,now)
    snapshot=SiteSnapshot(now,phase_control_enabled=True,phase_currents={'L1':s(17,'A')},
        phase_limits_a={'L1':20},device_states={'ev':DeviceState('ev',s(0),'Preparing',True)})
    extra={};power,_=phase_power_limit(snapshot,DeviceSpec('ev','charger',grid_phases=('L1',)),3700,extra)
    assert power==0
    assert extra.get('L1',0)==0


@pytest.mark.parametrize('idle,stale_grid',[(True,False),(False,True)])
def test_current_credit_requires_grid_to_include_the_observed_charge(idle,stale_grid):
    now=utcnow();past=now-timedelta(seconds=10)
    grid_stamp=past if stale_grid else now
    own_stamp=now if stale_grid else past
    s=lambda v,u='W',t=now:Sample(v,u,'test',t,t)
    snapshot=SiteSnapshot(now,grid=s(5290),solar=s(0),site_limit_w=12000,
        device_states={'ev':DeviceState('ev',s(0 if idle else 2300),
            'SuspendedEVSE' if idle else 'Charging',True,measured_at=now,
            vehicle_connected=True,currents={'L1':s(10,'A',own_stamp)})},
        phase_currents={'L1':s(13,'A',grid_stamp)},phase_limits_a={'L1':20},
        phase_margin_a=1,phase_control_enabled=True)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700,grid_phases=('L1',),max_current_a=16)
    engine=EnergyEngine()
    if not idle:engine.requested['ev']=2300
    batch=engine.evaluate(snapshot,[spec],{'ev':DevicePolicy('ev','manual',armed=True,
        manual_until=now+timedelta(hours=1))},{})
    assert max([c.limit_w or 0 for c in batch.commands]+[0])<=(1380 if idle else 3680)


@pytest.mark.parametrize('aggregate', [False,True])
@pytest.mark.parametrize('configured_phases',[1,3])
def test_ocpp_energy_prefers_total_or_sums_complete_phase_set(tmp_path,aggregate,configured_phases):
    from app.connectors.ocpp.registry import OcppRegistry
    from app.connectors.ocpp.station import Station
    from app.storage.database import SQLiteStore
    from app.settings import DeviceConfig
    cfg=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='box',phases=configured_phases)
    reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[cfg],lambda _:None)
    values=[{'measurand':'Energy.Active.Import.Register','value':'100','unit':'Wh','phase':p} for p in ('L1','L2','L3')]
    if aggregate:values.append({'measurand':'Energy.Active.Import.Register','value':'350','unit':'Wh'})
    Station('box',None,reg).meter_values(1,[{'timestamp':utcnow().isoformat(),'sampled_value':values}])
    assert reg.states['ev'].energy_wh==(350 if aggregate else 300)


@pytest.mark.asyncio
async def test_meter_refresh_requests_telemetry_without_starting_or_changing_charge(tmp_path):
    from types import SimpleNamespace
    from app.connectors.ocpp.registry import OcppRegistry,ChargerAdapter
    from app.storage.database import SQLiteStore
    from app.settings import DeviceConfig
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='box')
    reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda _:None)
    requests=[]
    class Station:
        async def call(self,request):
            requests.append(request)
            return SimpleNamespace(status='Accepted')
    reg.stations['box']=Station()
    assert await ChargerAdapter(reg,config).request_meter()
    assert len(requests)==1
    assert requests[0].__class__.__name__=='TriggerMessage'
    assert requests[0].requested_message=='MeterValues'
    assert requests[0].connector_id==1


def test_delayed_power_frame_does_not_erase_newer_idle_evidence(tmp_path):
    from app.connectors.ocpp.registry import OcppRegistry
    from app.connectors.ocpp.station import Station
    from app.engine.phase_limits import current_credit
    from app.storage.database import SQLiteStore
    from app.settings import DeviceConfig
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='box')
    reg=OcppRegistry(SQLiteStore(tmp_path/'db'),lambda:[config],lambda _:None)
    station=Station('box',None,reg);now=utcnow();old=now-timedelta(seconds=5)
    station.meter_values(1,[{'timestamp':old.isoformat(),'sampled_value':[
        {'measurand':'Current.Import','value':'10','unit':'A','phase':'L1'}]}])
    station.status(1,'NoError','SuspendedEVSE')
    station.meter_values(1,[{'timestamp':(old-timedelta(seconds=5)).isoformat(),'sampled_value':[
        {'measurand':'Power.Active.Import','value':'2300','unit':'W'}]}])
    snapshot=SiteSnapshot(utcnow(),device_states={'ev':reg.states['ev']},
        phase_currents={'L1':Sample(13,'A','test',old,old)})
    assert current_credit(snapshot,DeviceSpec('ev','charger',grid_phases=('L1',)),0)==(0,True)


def test_asynchronous_maintenance_still_respects_other_pending_current():
    from app.engine.phase_limits import phase_power_limit
    now=utcnow();past=now-timedelta(seconds=10)
    state=DeviceState('ev',Sample(2300,'W','test',now,now),'Charging',True,
        currents={'L1':Sample(10,'A','test',now,now)})
    snapshot=SiteSnapshot(now,phase_control_enabled=True,device_states={'ev':state},
        phase_currents={'L1':Sample(13,'A','test',past,past)},phase_limits_a={'L1':20})
    spec=DeviceSpec('ev','charger',grid_phases=('L1',),max_current_a=16)
    power,_=phase_power_limit(snapshot,spec,3700,{'L1':10},2300)
    assert power<=1380


def test_three_phase_charge_is_limited_by_its_most_constrained_mapped_phase():
    from app.engine.phase_limits import phase_power_limit
    now=utcnow();s=lambda value:Sample(value,'A','test',now,now)
    state=DeviceState('ev',observed_state='Charging',connected=True,
        currents={'L1':s(6),'L2':s(6),'L3':s(6)})
    snapshot=SiteSnapshot(now,phase_control_enabled=True,device_states={'ev':state},
        phase_currents={'L1':s(13),'L2':s(12),'L3':s(4)},phase_limits_a={'L1':20,'L2':18,'L3':20})
    spec=DeviceSpec('ev','charger',grid_phases=('L1','L2','L3'),max_current_a=16)
    assert phase_power_limit(snapshot,spec,11000,{})[0]==7590


def test_first_current_can_arrive_after_charging_status_without_a_premature_stop():
    from app.simulation.clock import SimulatedClock
    clock=SimulatedClock();engine=EnergyEngine(clock)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=6000,grid_phases=('L1',),max_current_a=20)
    policy=DevicePolicy('ev','manual',armed=True,manual_until=clock.now()+timedelta(hours=1))
    def frame(status,amps):
        now=clock.now();s=lambda v,u='W':Sample(v,u,'test',now,now)
        return SiteSnapshot(now,grid=s(700),solar=s(0),site_limit_w=11000,
            device_states={'ev':DeviceState('ev',s(0),status,True,vehicle_connected=True)},
            phase_currents={'L1':s(1.5 if status=='Preparing' else amps,'A')},
            phase_limits_a={'L1':20},phase_margin_a=1,phase_control_enabled=True)
    initial=engine.evaluate(frame('Preparing',1.5),[spec],{'ev':policy},{})
    assert initial.commands[0].limit_w==3910
    clock.advance(7)
    waiting=engine.evaluate(frame('Charging',18.5),[spec],{'ev':policy},{})
    assert not waiting.commands
    assert 'premier courant' in waiting.reasons['ev']
    clock.advance(3)
    overload=engine.evaluate(frame('Charging',22),[spec],{'ev':policy},{})
    assert overload.commands[0].limit_w==3220
    clock.advance(290)
    timeout=engine.evaluate(frame('Charging',15),[spec],{'ev':policy},{})
    assert timeout.commands[0].action=='suspend'
    assert timeout.reasons['ev']=='Courant réel de recharge indisponible'


def test_startup_wait_never_spends_other_pending_current_or_ignores_a_missing_grid():
    from app.engine.phase_limits import phase_power_limit
    now=utcnow();s=lambda v:Sample(v,'A','test',now,now)
    snapshot=SiteSnapshot(now,phase_control_enabled=True,
        device_states={'ev':DeviceState('ev',observed_state='Charging',connected=True)},
        phase_currents={'L1':s(13)},phase_limits_a={'L1':20},phase_margin_a=1)
    spec=DeviceSpec('ev','charger',grid_phases=('L1',),max_current_a=20)
    assert phase_power_limit(snapshot,spec,4600,{'L1':10},2300,True)[0]==1380
    missing=replace(snapshot,phase_currents={})
    assert phase_power_limit(missing,spec,4600,{},2300,True)[0]==0


def test_lost_current_during_an_established_charge_gets_no_startup_wait():
    from app.simulation.clock import SimulatedClock
    clock=SimulatedClock();engine=EnergyEngine(clock)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700,grid_phases=('L1',),max_current_a=16)
    policy=DevicePolicy('ev','manual',armed=True,manual_until=clock.now()+timedelta(hours=1))
    def frame(currents):
        now=clock.now();s=lambda v,u='W':Sample(v,u,'test',now,now)
        return SiteSnapshot(now,grid=s(3000),solar=s(0),site_limit_w=11000,
            device_states={'ev':DeviceState('ev',s(2300),'Charging',True,currents=currents)},
            phase_currents={'L1':s(13,'A')},phase_limits_a={'L1':20},phase_margin_a=1,phase_control_enabled=True)
    engine.evaluate(frame({'L1':Sample(10,'A','test',clock.now(),clock.now())}),[spec],{'ev':policy},{})
    clock.advance(2)
    lost=engine.evaluate(frame({}),[spec],{'ev':policy},{})
    assert lost.commands[0].action=='suspend'
    assert lost.reasons['ev']=='Courant réel de recharge indisponible'


@pytest.mark.parametrize('elapsed,expected',[(7,2300),(299,2300),(300,0)])
def test_preparing_after_start_cannot_raise_profile_or_extend_first_current_timeout(elapsed,expected):
    from app.simulation.clock import SimulatedClock
    clock=SimulatedClock();engine=EnergyEngine(clock)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=6000,grid_phases=('L1',),max_current_a=20)
    policy=DevicePolicy('ev','manual',armed=True,manual_until=clock.now()+timedelta(hours=1))
    def frame(amps,pending=False):
        now=clock.now();s=lambda v,u='W':Sample(v,u,'test',now,now)
        return SiteSnapshot(now,grid=s(700),solar=s(0),site_limit_w=11000,
            device_states={'ev':DeviceState('ev',s(0),'Preparing',True,start_pending=pending,transaction_active=False)},
            phase_currents={'L1':s(amps,'A')},phase_limits_a={'L1':20},phase_margin_a=1,phase_control_enabled=True)
    initial=engine.evaluate(frame(8.5),[spec],{'ev':policy},{})
    assert initial.commands[0].limit_w==2300
    clock.advance(elapsed)
    result=engine.evaluate(frame(1,pending=True),[spec],{'ev':policy},{})
    assert engine.requested['ev']==expected
    if not expected:assert result.commands[0].action=='suspend'
