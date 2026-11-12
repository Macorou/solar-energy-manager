from dataclasses import replace
from datetime import timedelta

import pytest

from app.domain.devices import DeviceSpec,DeviceState
from app.domain.measurements import Sample
from app.domain.site import SiteSnapshot
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.simulation.clock import SimulatedClock


def test_evcc_pv_starts_at_minimum_then_tracks_actual_current_and_cloud_timer():
    from app.engine.evcc_loadpoint import PvController
    pv=PvController()
    def target(now,grid,enabled=False,actual=0,offered=0):
        return pv.current(now=now,site_power_w=grid,voltage=230,phases=1,
            charging=enabled,enabled=enabled,actual_a=actual,offered_a=offered,
            minimum_a=6,maximum_a=20,enable_delay_s=60,disable_delay_s=180)
    assert target(0,-2000)==0
    assert target(59,-2000)==0
    assert target(60,-2000)==6
    assert target(90,-1000,True,5.8,6)==pytest.approx(6+1000/230)
    assert target(120,1500,True,6,6)==6
    assert target(299,1500,True,6,6)==6
    assert target(300,1500,True,6,6)==0


def test_evcc_grid_phase_limiter_replays_live_overload_without_cascade():
    clock=SimulatedClock();engine=EnergyEngine(clock);now=clock.now()
    def sample(value,unit='W',lag=0):
        stamp=now-timedelta(seconds=lag)
        return Sample(value,unit,'OCPP' if unit=='A' else 'HA',stamp,stamp,checked_at=stamp)
    frame=SiteSnapshot(now,grid=sample(5130.961),solar=sample(0),site_limit_w=11000,
        phase_control_enabled=True,phase_currents={'L1':sample(22.376,'A',3)},
        phase_limits_a={'L1':20},phase_margin_a=1,
        device_states={'ev':DeviceState('ev',sample(4669),'Charging',True,vehicle_connected=True,
            currents={'L1':sample(20.3,'A',7)})})
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=6000,
        grid_phases=('L1',),max_current_a=20)
    policy=DevicePolicy('ev','manual',armed=True,manual_until=now+timedelta(hours=1))
    engine.requested['ev']=3910
    decisions=[]
    for _ in range(4):
        decisions+=list(engine.evaluate(replace(frame,at=clock.now()),[spec],{'ev':policy},{}).commands)
        assert engine.requested['ev']==pytest.approx(16*230)
        clock.advance(2)
    assert len(decisions)==1
    assert decisions[0].action=='set_power'


@pytest.mark.parametrize('grid,expected',[(19,1380),(21,0)])
def test_evcc_nominal_minimum_is_kept_only_without_real_circuit_overload(grid,expected):
    from app.engine.phase_limits import phase_power_limit
    now=SimulatedClock().now();sample=lambda v:Sample(v,'A','OCPP',now,now,checked_at=now)
    snapshot=SiteSnapshot(now,phase_control_enabled=True,phase_margin_a=1,
        phase_currents={'L1':sample(grid)},phase_limits_a={'L1':20},
        device_states={'ev':DeviceState('ev',observed_state='Charging',connected=True,currents={'L1':sample(5.9)})})
    spec=DeviceSpec('ev','charger',grid_phases=('L1',),max_current_a=16)
    assert phase_power_limit(snapshot,spec,3680,{},1380)[0]==expected


def test_successful_source_checks_need_no_two_second_ordering():
    from app.engine.budget import measurements_coherent
    now=SimulatedClock().now();old=now-timedelta(seconds=7)
    snapshot=SiteSnapshot(now,grid=Sample(1000,'W','HA',now,now,checked_at=now),
        device_states={'ev':DeviceState('ev',Sample(3000,'W','OCPP',old,old,checked_at=old),connected=True)})
    assert measurements_coherent(snapshot)


def test_evcc_minimum_does_not_drop_on_a_full_power_circuit_at_5_9_amps():
    clock=SimulatedClock();now=clock.now();engine=EnergyEngine(clock)
    sample=lambda v,u='W':Sample(v,u,'OCPP',now,now,checked_at=now)
    snapshot=SiteSnapshot(now,grid=sample(11000),site_limit_w=11000,
        device_states={'ev':DeviceState('ev',sample(1357),'Charging',True,currents={'L1':sample(5.9,'A')})})
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700)
    engine.requested['ev']=1380
    result=engine.evaluate(snapshot,[spec],{'ev':DevicePolicy('ev','manual',armed=True,
        manual_until=now+timedelta(hours=1))},{})
    assert not result.commands
    assert engine.requested['ev']==1380


def test_pv_control_does_not_reapply_import_to_its_new_offer_every_two_seconds():
    clock=SimulatedClock();now=clock.now();engine=EnergyEngine(clock)
    sample=lambda v:Sample(v,'W','OCPP',now,now,checked_at=now)
    snapshot=SiteSnapshot(now,grid=sample(500),site_limit_w=11000,export_margin_w=0,
        device_states={'ev':DeviceState('ev',sample(2300),'Charging',True)})
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700)
    policy=DevicePolicy('ev',armed=True,start_delay_s=0)
    engine.requested['ev']=3910
    commands=[]
    for _ in range(4):
        commands+=list(engine.evaluate(replace(snapshot,at=clock.now()),[spec],{'ev':policy},{}).commands)
        assert engine.requested['ev']==pytest.approx(9*230)
        clock.advance(2)
    assert len(commands)==1


def test_ignored_suspend_is_reconciled_again_after_the_evcc_settling_time():
    clock=SimulatedClock();engine=EnergyEngine(clock)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3700)
    policy=DevicePolicy('ev','off',armed=True)
    def frame():
        now=clock.now();sample=lambda v:Sample(v,'W','OCPP',now,now,checked_at=now)
        return SiteSnapshot(now,grid=sample(4000),site_limit_w=11000,
            device_states={'ev':DeviceState('ev',sample(3680),'Charging',True)})
    assert engine.evaluate(frame(),[spec],{'ev':policy},{}).commands[0].action=='suspend'
    clock.advance(59)
    assert not engine.evaluate(frame(),[spec],{'ev':policy},{}).commands
    clock.advance(2)
    assert engine.evaluate(frame(),[spec],{'ev':policy},{}).commands[0].action=='suspend'


def test_reported_offered_current_is_synchronized_before_pv_regulation():
    clock=SimulatedClock();now=clock.now();engine=EnergyEngine(clock)
    sample=lambda v,u='W':Sample(v,u,'OCPP',now,now,checked_at=now)
    snapshot=SiteSnapshot(now,grid=sample(0),export_margin_w=0,site_limit_w=11000,
        device_states={'ev':DeviceState('ev',sample(3680),'Charging',True,
            currents={'L1':sample(16,'A')},offered_current=sample(16,'A'))})
    engine.requested['ev']=1380
    result=engine.evaluate(snapshot,[DeviceSpec('ev','charger',min_power_w=1380,max_power_w=4600)],
        {'ev':DevicePolicy('ev',armed=True)}, {})
    assert engine.requested['ev']==3680
    assert not result.commands


@pytest.mark.parametrize('kind',['phase','site'])
def test_unapplied_cap_with_persistent_physical_overload_suspends_and_latches(kind):
    from app.domain.commands import CommandIntent
    clock=SimulatedClock();now=clock.now();engine=EnergyEngine(clock)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=6000,
        grid_phases=('L1',),max_current_a=20)
    policy=DevicePolicy('ev','manual',armed=True,manual_until=now+timedelta(hours=1))
    cap=16*230
    engine.requested['ev']=cap
    engine.command_result(CommandIntent('cap','ev','set_power',cap),True,now)
    def frame():
        now=clock.now();sample=lambda v,u='W':Sample(v,u,'OCPP',now,now,checked_at=now)
        return SiteSnapshot(now,grid=sample(5130.961),site_limit_w=11000 if kind=='phase' else 4350,
            phase_control_enabled=kind=='phase',phase_margin_a=1,
            phase_currents={'L1':sample(22.376,'A')},phase_limits_a={'L1':20},
            device_states={'ev':DeviceState('ev',sample(4669),'Charging',True,
                currents={'L1':sample(20.3,'A')},offered_current=sample(16,'A'))})
    assert not engine.evaluate(frame(),[spec],{'ev':policy},{}).commands
    clock.advance(59)
    assert not engine.evaluate(frame(),[spec],{'ev':policy},{}).commands
    clock.advance(2)
    result=engine.evaluate(frame(),[spec],{'ev':policy},{})
    assert result.commands[0].action=='suspend'
    assert 'non appliquée' in result.reasons['ev']
    # An acknowledged zero or a mode re-evaluation must not restart it before the pause...
    engine.command_result(result.commands[0],True,clock.now());engine.forget('ev')
    def clear():
        now=clock.now();sample=lambda v,u='W':Sample(v,u,'OCPP',now,now,checked_at=now)
        return SiteSnapshot(now,grid=sample(500),site_limit_w=11000 if kind=='phase' else 4350,
            phase_control_enabled=kind=='phase',phase_margin_a=1,
            phase_currents={'L1':sample(2,'A')},phase_limits_a={'L1':20},
            device_states={'ev':DeviceState('ev',sample(0),'SuspendedEVSE',True,vehicle_connected=True)})
    assert not any(c.action=='set_power' for c in engine.evaluate(clear(),[spec],{'ev':policy},{}).commands)
    clock.advance(298)
    waiting=engine.evaluate(clear(),[spec],{'ev':policy},{})
    assert not waiting.commands and waiting.reasons['ev'].endswith('nouvelle tentative dans 1 min')
    # ...but a night charge is not left blocked: it is retried after 5 minutes.
    clock.advance(2)
    assert [c.action for c in engine.evaluate(clear(),[spec],{'ev':policy},{}).commands]==['set_power']


def test_reduction_watchdog_resets_after_the_physical_current_follows_the_cap():
    from app.engine.charger_feedback import unapplied_overload
    clock=SimulatedClock();now=clock.now();sample=lambda v,u='W':Sample(v,u,'OCPP',now,now,checked_at=now)
    spec=DeviceSpec('ev','charger',grid_phases=('L1',))
    state=DeviceState('ev',sample(16.9*230),'Charging',True,currents={'L1':sample(16.9,'A')})
    frame=SiteSnapshot(now,grid=sample(4350),phase_control_enabled=True,phase_margin_a=1,
        phase_currents={'L1':sample(18.9,'A')},phase_limits_a={'L1':20},device_states={'ev':state})
    assert not unapplied_overload(frame,spec,16.9*230)


@pytest.mark.parametrize('status,transaction,resent',[
    ('SuspendedEVSE',True,True),('SuspendedEVSE',False,False),('SuspendedEV',True,False)])
def test_offer_ignored_by_the_station_is_sent_again_after_the_settling_time(status,transaction,resent):
    # Wallbox fw 5 can accept a positive profile of a paused session and stay in SuspendedEVSE.
    clock=SimulatedClock();engine=EnergyEngine(clock)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3680,max_current_a=16)
    policy=DevicePolicy('ev','manual',armed=True,manual_until=clock.now()+timedelta(hours=1))
    def frame():
        now=clock.now();sample=lambda v:Sample(v,'W','OCPP',now,now,checked_at=now)
        return SiteSnapshot(now,grid=sample(0),site_limit_w=11000,
            device_states={'ev':DeviceState('ev',sample(0),status,True,vehicle_connected=True,
                transaction_active=transaction)})
    first=engine.evaluate(frame(),[spec],{'ev':policy},{}).commands
    assert [c.action for c in first]==['set_power']
    engine.command_result(first[0],True,clock.now())
    clock.advance(59)
    assert not engine.evaluate(frame(),[spec],{'ev':policy},{}).commands
    clock.advance(2)
    again=engine.evaluate(frame(),[spec],{'ev':policy},{}).commands
    assert [(c.action,c.limit_w) for c in again]==([('set_power',first[0].limit_w)] if resent else [])


def test_disconnected_charger_is_never_commanded_and_keeps_its_offer():
    # 2026-11-11 01:27: SEM restarted before the station reconnected; a stop could not be
    # delivered, became "unknown" and then cut the running charge once it reconnected.
    from app.domain.commands import CommandIntent
    clock=SimulatedClock();engine=EnergyEngine(clock)
    spec=DeviceSpec('ev','charger',min_power_w=1380,max_power_w=3680,max_current_a=16)
    policy=DevicePolicy('ev','manual',armed=True,manual_until=clock.now()+timedelta(hours=1))
    def frame(connected):
        now=clock.now();sample=lambda v:Sample(v,'W','OCPP',now,now,checked_at=now)
        return SiteSnapshot(now,grid=sample(3680),site_limit_w=11000,
            device_states={'ev':DeviceState('ev',sample(3680),'Charging',connected,vehicle_connected=True)})
    first=engine.evaluate(frame(True),[spec],{'ev':policy},{}).commands
    engine.command_result(first[0],True,clock.now())
    clock.advance(30)
    assert not engine.evaluate(frame(False),[spec],{'ev':policy},{}).commands
    clock.advance(30)
    assert not engine.evaluate(frame(True),[spec],{'ev':policy},{}).commands
    assert engine.requested['ev']==first[0].limit_w
