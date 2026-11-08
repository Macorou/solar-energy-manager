from dataclasses import replace
from datetime import datetime,timedelta
import pytest
from app.domain.devices import DeviceState
from app.domain.measurements import Sample, Quality, utcnow
from app.domain.site import SiteSnapshot
from app.domain.vehicles import VehicleTelemetry
from app.settings import SettingsDocument
from app.storage.database import SQLiteStore


def setup_tracker(tmp_path):
    from app.runtime.charging import ChargingTracker
    store=SQLiteStore(tmp_path/'db')
    config=SettingsDocument(devices=[{'id':'ev','name':'EV','kind':'charger','vehicle_id':'car'}],
        vehicles=[{'id':'car','capacity_kwh':34,'efficiency':1}])
    return ChargingTracker(store),store,config


def frame(now,energy,price=.2,grid=1000,solar=1000,soc=75,stamp=None,plugged=True):
    s=lambda v:Sample(v,'W','test',now,now)
    return SiteSnapshot(now,grid=s(grid),solar=s(solar),site_limit_w=12000,price=Sample(price,'€/kWh','test',now,now) if price is not None else None,
        device_states={'ev':DeviceState('ev',s(2000 if plugged else 0),'Charging' if plugged else 'Available',True,
            vehicle_connected=plugged,energy_wh=energy,energy_measured_at=now)},
        vehicle_telemetry={'car':VehicleTelemetry(soc,measured_at=stamp or now-timedelta(hours=1),received_at=now,quality=Quality.FRESH)})


def test_energy_cost_solar_soc_and_reboot_are_cumulative(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();stamp=now
    tracker.update(frame(now,10000,stamp=stamp),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=stamp),cfg)
    out=tracker.summary('ev')
    assert out['energy_kwh']==2
    assert out['cost_eur']==pytest.approx(.2)
    assert out['solar_percent']==pytest.approx(50)
    assert out['solar_partial'] is False
    assert out['soc']==pytest.approx(80)
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store);tracker.update(frame(now+timedelta(seconds=30),12000,stamp=stamp),cfg)
    assert tracker.summary('ev')['energy_kwh']==2
    assert tracker.summary('ev')['soc']==80


def test_session_cost_uses_the_site_mix(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow()
    cfg=cfg.model_copy(update={'devices':[*cfg.devices,
        *SettingsDocument(devices=[{'id':'tank','name':'Tank','kind':'water_heater'}]).devices]})
    def with_tank(snapshot):
        stamp=snapshot.at
        tank=DeviceState('tank',Sample(2000,'W','test',stamp,stamp),'on',True)
        return replace(snapshot,device_states={**snapshot.device_states,'tank':tank})
    first=with_tank(frame(now,10000,grid=2000,solar=2000,stamp=now))
    second=with_tank(frame(now+timedelta(seconds=30),12000,grid=2000,solar=2000,stamp=now))
    tracker.update(first,cfg);tracker.update(second,cfg)
    out=tracker.summary('ev')
    # 2 kW imported and 2 kW of solar used on the site: every kWh of the car is 50 % solar.
    assert out['cost_eur']==pytest.approx(.2)
    assert out['solar_percent']==pytest.approx(50)


@pytest.mark.parametrize('grid,cost,solar_percent',[(1500,.24,40),(-1000,0,100)])
def test_session_price_does_not_depend_on_the_car_power(tmp_path,grid,cost,solar_percent):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow()
    def stale(snapshot):
        old=snapshot.at-timedelta(seconds=300)
        state=replace(snapshot.device_states['ev'],observed_power=Sample(2000,'W','test',old,snapshot.at))
        return replace(snapshot,device_states={'ev':state})
    tracker.update(stale(frame(now,10000,grid=grid,solar=1000,stamp=now)),cfg)
    tracker.update(stale(frame(now+timedelta(seconds=30),12000,grid=grid,solar=1000,stamp=now)),cfg)
    out=tracker.summary('ev')
    assert out['cost_partial'] is False
    assert out['cost_eur']==pytest.approx(cost)
    assert out['solar_percent']==pytest.approx(solar_percent)


def test_changed_peugeot_percentage_reanchors_at_current_energy_ignoring_its_date(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=60),14000,soc=76,stamp=now+timedelta(seconds=30)),cfg)
    assert tracker.summary('ev')['soc']==pytest.approx(76)


def test_tariff_change_is_integrated_and_unknown_price_is_not_zero(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now
    tracker.update(frame(now,10000,price=.2,grid=1000,solar=0,stamp=old),cfg)
    # New price half-way through a two-kWh counter interval.
    middle=frame(now+timedelta(seconds=15),10000,price=.4,grid=1000,solar=0,stamp=old)
    middle=replace(middle,device_states={'ev':replace(middle.device_states['ev'],energy_measured_at=now)})
    tracker.update(middle,cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,price=.4,grid=1000,solar=0,stamp=old),cfg)
    assert tracker.summary('ev')['cost_eur']==pytest.approx(.6)
    tracker.update(frame(now+timedelta(seconds=31),12000,price=None,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=60),14000,price=None,stamp=old),cfg)
    assert tracker.summary('ev')['cost_partial'] is True


def test_counter_reset_never_decreases_energy_and_marks_soc_unreliable(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=60),10,stamp=old),cfg)
    assert tracker.summary('ev')['energy_kwh']==2
    assert tracker.summary('ev')['soc_usable'] is False
    assert tracker.summary('ev')['soc_reason']=="Compteur d’énergie de la borne incohérent"


def test_transaction_start_rebases_an_initial_placeholder_index_without_inventing_energy(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=8)
    cfg.devices[0].max_power_w=6000
    tracker.update(frame(now,0,soc=60,stamp=old),cfg)
    later=frame(now+timedelta(seconds=30),5000928,soc=60,stamp=old)
    later=replace(later,device_states={'ev':replace(later.device_states['ev'],
        energy_transaction_id=42,energy_transaction_start_wh=5000922,
        energy_transaction_started_at=now+timedelta(seconds=20))})
    tracker.update(later,cfg)
    assert tracker.summary('ev')['energy_kwh']==pytest.approx(.006)
    assert tracker.summary('ev')['soc']==pytest.approx(60.015)
    assert tracker.summary('ev')['soc_usable'] is True
    assert tracker.summary('ev')['energy_partial'] is False
    # Repeated protocol frames never rebase or add the same interval twice.
    tracker.update(later,cfg)
    assert tracker.summary('ev')['energy_kwh']==pytest.approx(.006)


def test_zero_energy_legacy_gap_recovers_only_when_idle_power_is_confirmed(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=8)
    cfg.devices[0].max_power_w=6000
    tracker.update(frame(now,0,soc=60,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=3),5000922,soc=60,stamp=old),cfg)
    assert tracker.summary('ev')['soc_usable'] is False
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store)
    idle=frame(now+timedelta(minutes=5),5000922,soc=60,stamp=old)
    # On reconnect, StatusNotification can precede the first new index frame.
    state=replace(idle.device_states['ev'],observed_state='Finishing',
        observed_power=Sample(0,'W','HA',idle.at,idle.at),energy_wh=None,energy_measured_at=None)
    unavailable=replace(state,observed_power=None)
    tracker.update(replace(idle,device_states={'ev':unavailable},vehicle_telemetry={}),cfg)
    assert tracker.summary('ev')['soc_usable'] is False
    tracker.update(replace(idle,device_states={'ev':state},vehicle_telemetry={}),cfg)
    assert tracker.summary('ev')['soc']==60
    assert tracker.summary('ev')['soc_usable'] is True
    assert tracker.summary('ev')['energy_partial'] is True


def test_new_transaction_preserves_previous_energy_and_reboot_does_not_rebase_it_again(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow()
    tracker.update(frame(now,10000,stamp=now),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=now),cfg)
    next_tx=frame(now+timedelta(seconds=60),2,stamp=now)
    next_tx=replace(next_tx,device_states={'ev':replace(next_tx.device_states['ev'],
        energy_transaction_id=2,energy_transaction_start_wh=0,
        energy_transaction_started_at=now+timedelta(seconds=50))})
    tracker.update(next_tx,cfg)
    assert tracker.summary('ev')['energy_kwh']==pytest.approx(2.002)
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store);tracker.update(next_tx,cfg)
    assert tracker.summary('ev')['energy_kwh']==pytest.approx(2.002)


@pytest.mark.parametrize('prior_wh',[0,30])
def test_counter_below_declared_start_is_rejected_even_before_first_tracker_tick(tmp_path,prior_wh):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();cfg.devices[0].max_power_w=6000
    tracker.update(frame(now,10000,soc=60,stamp=now),cfg)
    tracker.update(frame(now+timedelta(seconds=30),10000+prior_wh,soc=60,stamp=now),cfg)
    bad=frame(now+timedelta(seconds=50),1,soc=60,stamp=now)
    bad=replace(bad,device_states={'ev':replace(bad.device_states['ev'],observed_state='Preparing',
        observed_power=Sample(0,'W','HA',bad.at,bad.at),energy_transaction_id=42,
        energy_transaction_start_wh=5000922,energy_transaction_started_at=now+timedelta(seconds=40))})
    tracker.update(bad,cfg)
    assert tracker.summary('ev')['energy_kwh']==pytest.approx(prior_wh/1000)
    assert tracker.summary('ev')['energy_partial'] is True
    assert tracker.summary('ev')['soc_usable'] is False


@pytest.mark.parametrize('known_start',[False,True])
def test_active_legacy_transaction_adopts_identity_without_losing_continuous_interval(tmp_path,known_start):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();cfg.devices[0].max_power_w=6000
    tracker.update(frame(now,10000,soc=60,stamp=now),cfg)
    tracker.update(frame(now+timedelta(seconds=30),10030,soc=60,stamp=now),cfg)
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store)
    reading=frame(now+timedelta(hours=1),14000,soc=60,stamp=now)
    reading=replace(reading,device_states={'ev':replace(reading.device_states['ev'],energy_transaction_id=42,
        energy_transaction_start_wh=9000,energy_transaction_started_at=now-timedelta(minutes=10) if known_start else None)})
    tracker.update(reading,cfg)
    assert tracker.summary('ev')['energy_kwh']==4
    assert tracker.summary('ev')['energy_partial'] is False
    assert tracker.summary('ev')['soc']==70


def test_unprovable_legacy_transaction_interval_is_explicitly_partial(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();cfg.devices[0].max_power_w=6000
    tracker.update(frame(now,10000,soc=60,stamp=now),cfg)
    tracker.update(frame(now+timedelta(seconds=30),10030,soc=60,stamp=now),cfg)
    reading=frame(now+timedelta(seconds=60),5000922,soc=60,stamp=now)
    reading=replace(reading,device_states={'ev':replace(reading.device_states['ev'],energy_transaction_id=42,
        energy_transaction_start_wh=5000000)})
    tracker.update(reading,cfg)
    assert tracker.summary('ev')['energy_kwh']==pytest.approx(.03)
    assert tracker.summary('ev')['energy_partial'] is True
    assert tracker.summary('ev')['soc_usable'] is False


def test_new_peugeot_reference_supersedes_gap_reason_when_only_meter_age_blocks(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow()
    tracker.update(frame(now,10000,stamp=now),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=now),cfg)
    tracker.update(frame(now+timedelta(seconds=60),10,stamp=now),cfg)
    reference_at=now+timedelta(seconds=90)
    tracker.update(frame(reference_at,110,soc=78,stamp=reference_at),cfg)
    assert tracker.summary('ev')['soc_usable'] is True
    stale=frame(now+timedelta(seconds=270),110,soc=78,stamp=reference_at)
    stale=replace(stale,device_states={'ev':replace(stale.device_states['ev'],energy_measured_at=reference_at)})
    tracker.update(stale,cfg)
    assert tracker.summary('ev')['soc_usable'] is False
    assert tracker.summary('ev')['soc_reason']=='Index d’énergie de la borne trop ancien'


@pytest.mark.asyncio
async def test_planned_charge_recovers_the_live_zero_energy_gap_with_confirmed_stop(tmp_path,monkeypatch):
    from app.runtime.coordinator import Coordinator
    from app.domain.commands import CommandResult
    from app.settings import ChargeProgram
    tracker,store,cfg=setup_tracker(tmp_path)
    now=datetime.fromisoformat('2026-10-28T21:16:20+00:00');old=now-timedelta(hours=8)
    monkeypatch.setattr('app.runtime.coordinator.utcnow',lambda:now)
    cfg.devices[0].armed=True;cfg.devices[0].mode='planned';cfg.devices[0].grid_phases=['L1']
    cfg.devices[0].max_current_a=20;cfg.devices[0].max_power_w=6000;cfg.devices[0].min_power_w=1380
    cfg.phase_control_enabled=True
    cfg.schedules=[ChargeProgram(id='p',name='80%',vehicle_id='car',weekdays=[0,1,2,3,4],
        earliest_start='22:00',deadline='05:45',target_soc=80)]
    tracker.update(frame(now-timedelta(seconds=10),0,soc=60,stamp=old),cfg)
    tracker.update(frame(now-timedelta(seconds=7),5000922,soc=60,stamp=old),cfg)
    store.save_settings(cfg.model_dump(mode='json'))
    class Adapter:
        async def execute(self,intent):return CommandResult(intent.id,True)
    runtime=Coordinator(store,adapters={'ev':Adapter()})
    live=frame(now,5000922,soc=60,stamp=old)
    s=lambda v,u='W':Sample(v,u,'HA',now,now)
    live=replace(live,grid=s(799),solar=s(0),phase_control_enabled=True,
        phase_currents={'L1':s(1.5,'A')},phase_powers={'L1':s(84)},phase_limits_a={'L1':20},phase_margin_a=1,
        device_states={'ev':replace(live.device_states['ev'],observed_state='Finishing',observed_power=s(0))})
    await runtime.tick(live)
    for job in list(runtime.command_tasks.values()):await job
    device=runtime.public_state()['devices'][0]
    assert device['authorization']['allow_grid'] is True
    assert device['charging']['soc']==60
    assert device['command']['action']=='set_power'
    assert device['command']['power_w']==4025


@pytest.mark.parametrize('quality',[Quality.FRESH,Quality.STALE])
def test_last_peugeot_soc_is_the_automatic_reference_even_before_meter_history(tmp_path,quality):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(days=2)
    for seconds,energy in [(0,10000),(30,12000)]:
        snapshot=frame(now+timedelta(seconds=seconds),energy,stamp=old)
        snapshot=replace(snapshot,vehicle_telemetry={'car':replace(snapshot.vehicle_telemetry['car'],
            received_at=old,quality=quality)})
        tracker.update(snapshot,cfg)
        assert tracker.summary('ev')['soc_usable'] is True
    assert tracker.summary('ev')['soc']==80
    assert tracker.summary('ev')['soc_reference_missing'] is False
    assert tracker.summary('ev')['soc_reference_source']=='vehicle'
    assert tracker.target_reached('ev',80)


def test_a_percentage_kept_through_a_peugeot_error_never_seeds_the_session(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow()
    for seconds,energy in [(0,10000),(30,12000)]:
        snapshot=frame(now+timedelta(seconds=seconds),energy,soc=85)
        snapshot=replace(snapshot,vehicle_telemetry={'car':replace(snapshot.vehicle_telemetry['car'],
            quality=Quality.UNAVAILABLE)})
        tracker.update(snapshot,cfg)
    out=tracker.summary('ev')
    assert out['soc'] is None and out['soc_usable'] is False and out['soc_known'] is False
    assert out['soc_reason']=='Batterie Peugeot indisponible'
    assert not tracker.target_reached('ev',80)
    tracker.update(frame(now+timedelta(seconds=60),12000,soc=40),cfg)
    tracker.update(frame(now+timedelta(seconds=90),14000,soc=40),cfg)
    assert tracker.summary('ev')['soc']==pytest.approx(45)


def test_changed_peugeot_soc_replaces_estimate_without_readding_previous_energy(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow()
    tracker.update(frame(now,10000,stamp=now-timedelta(hours=2)),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,soc=76,stamp=now-timedelta(hours=1)),cfg)
    assert tracker.summary('ev')['soc']==76
    assert tracker.summary('ev')['soc_usable'] is True


def test_terminal_counter_after_available_is_reconciled_into_last_session(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow()
    tracker.update(frame(now,10000,grid=1000,solar=0,stamp=now),cfg)
    tracker.update(frame(now+timedelta(seconds=10),10020,grid=1000,solar=0,stamp=now),cfg)
    unplug=frame(now+timedelta(seconds=20),10020,grid=1000,solar=0,stamp=now,plugged=False)
    unplug=replace(unplug,device_states={'ev':replace(unplug.device_states['ev'],energy_measured_at=now+timedelta(seconds=10))})
    tracker.update(unplug,cfg)
    assert tracker.summary('ev')['cost_partial'] is True
    # The measured part keeps its share, flagged as partial until the terminal value.
    assert tracker.summary('ev')['solar_percent']==pytest.approx(0)
    assert tracker.summary('ev')['solar_partial'] is True
    terminal=frame(now+timedelta(seconds=25),10030,grid=1000,solar=0,stamp=now,plugged=False)
    terminal=replace(terminal,device_states={'ev':replace(terminal.device_states['ev'],energy_terminal=True)})
    tracker.update(terminal,cfg)
    assert tracker.summary('ev')['energy_kwh']==pytest.approx(.03)
    assert tracker.summary('ev')['cost_eur']==pytest.approx(.006)


def test_short_unknown_mix_interval_is_not_silently_priced(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow()
    tracker.update(frame(now,10000,grid=1000,solar=0,stamp=now),cfg)
    gap=frame(now+timedelta(seconds=2),10000,grid=1000,solar=0,stamp=now)
    tracker.update(replace(gap,grid=None,device_states={'ev':replace(gap.device_states['ev'],energy_measured_at=now)}),cfg)
    tracker.update(frame(now+timedelta(seconds=8),10008,grid=1000,solar=0,stamp=now),cfg)
    assert tracker.summary('ev')['cost_partial'] is True
    assert tracker.summary('ev')['cost_eur']==pytest.approx(.0004)
    # Only the 2 Wh with a known mix carry the share; the rest makes it partial.
    assert tracker.summary('ev')['solar_percent']==pytest.approx(0)
    assert tracker.summary('ev')['solar_partial'] is True


def test_solar_share_covers_the_measured_part_after_a_restart_gap(tmp_path):
    from app.runtime.charging import ChargingTracker
    from app.storage.charging_sessions import SessionHistory
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow()
    tracker.update(frame(now,10000,grid=0,solar=2000,stamp=now),cfg)
    tracker.update(frame(now+timedelta(seconds=30),11000,grid=0,solar=2000,stamp=now),cfg)
    # SEM is down for 30 minutes: the energy charged meanwhile has no known mix.
    tracker=ChargingTracker(store)
    tracker.update(frame(now+timedelta(minutes=30),12000,grid=0,solar=2000,stamp=now),cfg)
    out=tracker.summary('ev')
    assert out['energy_kwh']==pytest.approx(2)
    assert out['solar_percent']==pytest.approx(100)
    assert out['solar_partial'] is True
    row=SessionHistory(store).all()[0]
    assert row['solar_percent']==pytest.approx(100)
    assert row['solar_partial'] is True


@pytest.mark.asyncio
async def test_schedule_completion_accepts_trusted_effective_soc(tmp_path):
    from app.runtime.coordinator import Coordinator
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow()
    store.save_settings(cfg.model_dump(mode='json'))
    store.set('schedule_results',{'due':{'program_id':'p','vehicle_id':'car','target_soc':80,
        'deadline':now.isoformat(),'result':'pending'}})
    runtime=Coordinator(store)
    await runtime.tick(frame(now,10000,soc=90,stamp=now))
    assert store.get('schedule_results')['due']['result']=='complete'


@pytest.mark.asyncio
async def test_schedule_does_not_count_untracked_old_soc_as_verified_completion(tmp_path):
    from app.runtime.coordinator import Coordinator
    _,store,cfg=setup_tracker(tmp_path);now=utcnow()
    store.save_settings(cfg.model_dump(mode='json'))
    store.set('schedule_results',{'due':{'program_id':'p','vehicle_id':'car','target_soc':80,
        'deadline':now.isoformat(),'result':'pending'}})
    runtime=Coordinator(store)
    await runtime.tick(frame(now,10000,soc=90,stamp=now-timedelta(hours=1),plugged=False))
    assert store.get('schedule_results')['due']['result']=='incomplete'


def test_persisted_manual_reference_is_replaced_by_last_peugeot_even_if_older(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
    tracker.update(frame(now,10000,stamp=old),cfg)
    # A session persisted by 0.1.10 may contain a more recent manual anchor.
    tracker.sessions['ev']['anchor']={'soc':20,'at':now.timestamp(),'energy':0.,'covered':True,'source':'manual'}
    tracker.sessions['ev']['reached_target']=90;tracker.sessions['ev']['reached_at']=now.timestamp()
    store.set('charging_sessions',tracker.sessions)
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    assert tracker.summary('ev')['soc']==80
    assert tracker.summary('ev')['soc_usable'] is True
    assert tracker.summary('ev')['soc_reference_source']=='vehicle'
    assert not tracker.target_reached('ev',90)


def test_persisted_uncovered_peugeot_reference_survives_repeat_reboot_and_replug(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.sessions['ev']['anchor']['covered']=False
    store.set('charging_sessions',tracker.sessions)
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    assert tracker.summary('ev')['soc']==80
    tracker=ChargingTracker(store)
    tracker.update(frame(now+timedelta(seconds=60),12000,stamp=old),cfg)
    assert tracker.summary('ev')['soc']==80
    tracker.update(frame(now+timedelta(seconds=90),12000,stamp=old,plugged=False),cfg)
    tracker.update(frame(now+timedelta(seconds=120),12000,stamp=old),cfg)
    assert tracker.summary('ev')['soc']==75
    assert tracker.summary('ev')['soc_usable'] is True


def test_restart_and_replug_without_cloud_waits_for_peugeot(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(days=2)
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=60),12000,stamp=old,plugged=False),cfg)
    # Upgrade path: 0.1.10 persisted only the session's raw Peugeot anchor.
    store.set('peugeot_soc_references',{})
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store)
    tracker.update(replace(frame(now+timedelta(seconds=90),12000),vehicle_telemetry={}),cfg)
    assert tracker.summary('ev')['soc'] is None
    assert tracker.summary('ev')['soc_usable'] is False
    assert store.get('peugeot_soc_references')['car|']['soc']==75
    tracker.update(frame(now+timedelta(seconds=120),14000,soc=50),cfg)
    assert tracker.summary('ev')['soc']==50


def test_latest_peugeot_received_while_unplugged_is_remembered_but_not_reused_without_cloud(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow()
    tracker.update(frame(now,10000,stamp=now-timedelta(days=2)),cfg)
    tracker.update(frame(now+timedelta(seconds=30),10000,plugged=False),cfg)
    tracker.update(frame(now+timedelta(seconds=60),10000,soc=70,stamp=now+timedelta(seconds=60),plugged=False),cfg)
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store)
    tracker.update(replace(frame(now+timedelta(seconds=90),10000),vehicle_telemetry={}),cfg)
    assert store.get('peugeot_soc_references')['car|']['soc']==70
    assert tracker.summary('ev')['soc'] is None


def test_persisted_peugeot_reference_is_never_reused_for_a_different_vin(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow()
    cfg.vehicles[0].vin='VF3AAAAAAAAAAAAAA'
    tracker.update(frame(now,10000,stamp=now-timedelta(days=2)),cfg)
    tracker.update(frame(now+timedelta(seconds=30),10000,plugged=False),cfg)
    cfg.vehicles[0].vin='VF3BBBBBBBBBBBBBB'
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store)
    tracker.update(replace(frame(now+timedelta(seconds=60),10000),vehicle_telemetry={}),cfg)
    assert tracker.summary('ev')['soc'] is None
    assert tracker.summary('ev')['soc_usable'] is False


def test_manual_soc_reference_api_is_no_longer_available(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.settings import RuntimeSettings
    app=create_app(RuntimeSettings(data_dir=tmp_path/'api'));client=TestClient(app)
    url='/api/v1/devices/ev/soc-reference'
    assert client.post('/api/v1/setup',json={'token':(tmp_path/'api'/'bootstrap-token').read_text(),
        'username':'admin','password':'a-secure-test-password'}).status_code==200
    _,_,cfg=setup_tracker(tmp_path);app.state.store.save_settings(cfg.model_dump(mode='json'))
    assert client.post(url,json={'soc':75,'session_id':'arbitrary'}).status_code in (404,405)
    assert app.state.coordinator.command_tasks=={}


def test_pure_solar_cost_does_not_require_a_grid_tariff(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now
    tracker.update(frame(now,10000,price=None,grid=-500,solar=2000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,price=None,grid=-500,solar=2000,stamp=old),cfg)
    assert tracker.summary('ev')['cost_eur']==0
    assert tracker.summary('ev')['solar_percent']==100


@pytest.mark.asyncio
async def test_runtime_stops_manual_car_at_estimated_target_even_with_repeated_old_api(tmp_path):
    from app.runtime.coordinator import Coordinator
    from app.domain.commands import CommandResult
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(days=2)
    cfg.devices[0].armed=True;cfg.devices[0].mode='manual'
    cfg.devices[0].min_power_w=1380;cfg.devices[0].max_power_w=3700
    cfg.vehicles[0].capacity_kwh=.34  # EVCC 85%: 20Wh means 5%.
    store.save_settings(cfg.model_dump(mode='json'))
    store.set('manual_controls',{'ev':{'until':(now+timedelta(hours=2)).isoformat(),'previous_mode':'solar'}})
    class Adapter:
        async def execute(self,intent):return CommandResult(intent.id,True)
    runtime=Coordinator(store,adapters={'ev':Adapter()})
    await runtime.tick(frame(now,10000,stamp=old))
    for job in runtime.command_tasks.values(): await job
    assert runtime.dispatcher.records['ev']['action']=='set_power'
    # Start is observed before a second meter interval raises the effective SOC.
    await runtime.tick(frame(now+timedelta(seconds=30),10020,stamp=old))
    for job in runtime.command_tasks.values(): await job
    assert runtime.dispatcher.records['ev']['action']=='suspend'
    assert runtime.public_state()['devices'][0]['charging']['soc']==80


def test_pruned_energy_history_keeps_the_original_soc_energy_reference(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();old=now
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    # A persisted, bounded history may retain only recent meter points.
    tracker.sessions['ev']['points']=tracker.sessions['ev']['points'][-1:]
    store.set('charging_sessions',tracker.sessions)
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store)
    tracker.update(frame(now+timedelta(seconds=60),12000,stamp=old),cfg)
    assert tracker.summary('ev')['soc']==80


def test_new_measured_soc_after_counter_reset_recovers_without_erasing_energy_gap(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=60),10,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=90),110,soc=78,stamp=now+timedelta(seconds=90)),cfg)
    assert tracker.summary('ev')['soc']==78
    assert tracker.summary('ev')['soc_usable'] is True
    assert tracker.summary('ev')['energy_partial'] is True


def test_goal_latch_ignores_repeated_old_api_but_accepts_real_new_lower_measurement(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    assert tracker.target_reached('ev',80)
    tracker.update(frame(now+timedelta(seconds=60),12000,stamp=old),cfg)
    assert tracker.target_reached('ev',80)
    tracker.update(frame(now+timedelta(seconds=90),12000,soc=77,stamp=now+timedelta(seconds=90)),cfg)
    assert tracker.summary('ev')['soc']==77
    assert tracker.target_reached('ev',80) is False


def test_unplug_keeps_last_session_and_replug_starts_new_counters(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=60),12000,stamp=old,plugged=False),cfg)
    assert tracker.summary('ev')['energy_kwh']==2
    assert not tracker.summary('ev')['active']
    tracker.update(frame(now+timedelta(seconds=90),12000,soc=70,stamp=now+timedelta(seconds=90)),cfg)
    assert tracker.summary('ev')['energy_kwh']==0


def test_missing_meter_does_not_permit_targeted_charging_indefinitely_on_fresh_soc(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow()
    first=frame(now,10000,stamp=now)
    first=replace(first,device_states={'ev':replace(first.device_states['ev'],energy_wh=None,energy_measured_at=None)})
    tracker.update(first,cfg)
    later=frame(now+timedelta(minutes=6),10000,stamp=now)
    later=replace(later,device_states={'ev':replace(later.device_states['ev'],energy_wh=None,energy_measured_at=None)})
    tracker.update(later,cfg)
    assert tracker.summary('ev')['soc_usable'] is False


def test_impossible_counter_jump_does_not_create_energy_or_infinite_cost(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);cfg.devices[0].max_power_w=3700
    now=utcnow();old=now
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),1e308,price=1e308,stamp=old),cfg)
    assert tracker.summary('ev')['energy_kwh']==0
    assert tracker.summary('ev')['energy_partial'] is True
    assert tracker.summary('ev')['soc_usable'] is False


@pytest.mark.asyncio
async def test_engine_never_sees_a_peugeot_percentage_kept_through_an_api_error(tmp_path):
    from app.runtime.coordinator import Coordinator
    _,store,cfg=setup_tracker(tmp_path);now=utcnow()
    store.save_settings(cfg.model_dump(mode='json'))
    runtime=Coordinator(store)
    error=lambda snapshot:replace(snapshot,vehicle_telemetry={'car':replace(snapshot.vehicle_telemetry['car'],
        quality=Quality.UNAVAILABLE)})
    await runtime.tick(error(frame(now,10000,soc=90,plugged=False)))
    assert runtime.snapshot.vehicle_telemetry['car'].soc is None
    # An estimate started from a good reading survives a later Peugeot error.
    await runtime.tick(frame(now+timedelta(seconds=30),10000,soc=60))
    await runtime.tick(error(frame(now+timedelta(seconds=60),12000,soc=60)))
    car=runtime.snapshot.vehicle_telemetry['car']
    assert car.quality==Quality.ESTIMATED and car.soc==pytest.approx(65)


@pytest.mark.parametrize('grid,solar,fraction',[(-1200,1000,0.),(-500,0,0.),(0,1000,0.),(0,0,None),(1000,0,1.)])
def test_mix_when_nothing_is_measured_as_used(grid,solar,fraction):
    # Export above production comes from two meters read at different moments: nothing is imported.
    from app.runtime.charging import mix_context
    now=utcnow();s=lambda v:Sample(v,'W','test',now,now)
    snapshot=SiteSnapshot(now,grid=s(grid),solar=s(solar),site_limit_w=9000,price=Sample(.2,'€/kWh','test',now,now))
    assert mix_context(snapshot,0)[0]==fraction
