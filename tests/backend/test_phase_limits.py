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
    now=utcnow(); s=lambda v,u='W':Sample(v,u,'test',now,now)
    snapshot=SiteSnapshot(now,grid=s(4000),solar=s(0),site_limit_w=12000,
        device_states={'ev':DeviceState('ev',s(2300),'Charging',True,vehicle_connected=True,
            currents={'L1':s(10,'A')})},
        phase_currents={'L1':s(18,'A'),'L2':s(4,'A'),'L3':s(4,'A')},
        phase_limits_a={'L1':20,'L2':20,'L3':20},phase_margin_a=1,phase_control_enabled=True)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700,
        grid_phases=(phase,),voltage=230,min_current_a=6,max_current_a=16)
    engine=EnergyEngine();engine.requested['ev']=2300
    batch=engine.evaluate(snapshot,[spec],{'ev':DevicePolicy('ev','manual',armed=True,
        manual_until=now+timedelta(hours=1))},{})
    assert batch.commands[0].limit_w==expected


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


def test_a_charge_below_minimum_does_not_reserve_current_it_will_never_use():
    from app.engine.phase_limits import phase_power_limit
    now=utcnow();s=lambda v,u='W':Sample(v,u,'test',now,now)
    snapshot=SiteSnapshot(now,phase_control_enabled=True,phase_currents={'L1':s(17,'A')},
        phase_limits_a={'L1':20},device_states={'ev':DeviceState('ev',s(0),'Preparing',True)})
    extra={};power,_=phase_power_limit(snapshot,DeviceSpec('ev','charger',grid_phases=('L1',)),3700,extra)
    assert power==0
    assert extra.get('L1',0)==0
