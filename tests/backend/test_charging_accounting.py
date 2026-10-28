from dataclasses import replace
from datetime import timedelta
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
        vehicles=[{'id':'car','capacity_kwh':40,'efficiency':1}])
    return ChargingTracker(store),store,config


def frame(now,energy,price=.2,grid=1000,solar=1000,soc=75,stamp=None,plugged=True):
    s=lambda v:Sample(v,'W','test',now,now)
    return SiteSnapshot(now,grid=s(grid),solar=s(solar),site_limit_w=12000,price=Sample(price,'€/kWh','test',now,now) if price is not None else None,
        device_states={'ev':DeviceState('ev',s(2000 if plugged else 0),'Charging' if plugged else 'Available',True,
            vehicle_connected=plugged,energy_wh=energy,energy_measured_at=now)},
        vehicle_telemetry={'car':VehicleTelemetry(soc,measured_at=stamp or now-timedelta(hours=1),received_at=now,quality=Quality.FRESH)})


def test_energy_cost_solar_soc_and_reboot_are_cumulative(tmp_path):
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();stamp=now-timedelta(hours=1)
    tracker.update(frame(now,10000,stamp=stamp),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=stamp),cfg)
    out=tracker.summary('ev')
    assert out['energy_kwh']==2
    assert out['cost_eur']==pytest.approx(.2)
    assert out['solar_percent']==pytest.approx(50)
    assert out['soc']==pytest.approx(80)
    from app.runtime.charging import ChargingTracker
    tracker=ChargingTracker(store);tracker.update(frame(now+timedelta(seconds=30),12000,stamp=stamp),cfg)
    assert tracker.summary('ev')['energy_kwh']==2
    assert tracker.summary('ev')['soc']==80


def test_new_delayed_api_measurement_reanchors_with_energy_since_its_date(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=60),14000,soc=76,stamp=now+timedelta(seconds=30)),cfg)
    assert tracker.summary('ev')['soc']==pytest.approx(81)


def test_tariff_change_is_integrated_and_unknown_price_is_not_zero(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
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
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=60),10,stamp=old),cfg)
    assert tracker.summary('ev')['energy_kwh']==2
    assert tracker.summary('ev')['soc_usable'] is False


def test_pure_solar_cost_does_not_require_a_grid_tariff(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
    tracker.update(frame(now,10000,price=None,grid=-500,solar=2000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,price=None,grid=-500,solar=2000,stamp=old),cfg)
    assert tracker.summary('ev')['cost_eur']==0
    assert tracker.summary('ev')['solar_percent']==100


@pytest.mark.asyncio
async def test_runtime_stops_manual_car_at_estimated_target_even_with_repeated_old_api(tmp_path):
    from app.runtime.coordinator import Coordinator
    from app.domain.commands import CommandResult
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
    cfg.devices[0].armed=True;cfg.devices[0].mode='manual'
    cfg.devices[0].min_power_w=1380;cfg.devices[0].max_power_w=3700
    cfg.vehicles[0].capacity_kwh=.4  # Small simulated battery:20Wh means5%.
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
    tracker,store,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
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
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=60),10,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=90),110,soc=78,stamp=now+timedelta(seconds=90)),cfg)
    assert tracker.summary('ev')['soc']==78
    assert tracker.summary('ev')['soc_usable'] is True
    assert tracker.summary('ev')['energy_partial'] is True


def test_goal_latch_ignores_repeated_old_api_but_accepts_real_new_lower_measurement(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),12000,stamp=old),cfg)
    assert tracker.target_reached('ev',80)
    tracker.update(frame(now+timedelta(seconds=60),12000,stamp=old),cfg)
    assert tracker.target_reached('ev',80)
    tracker.update(frame(now+timedelta(seconds=90),12000,soc=77,stamp=now+timedelta(seconds=90)),cfg)
    assert tracker.summary('ev')['soc']==77
    assert tracker.target_reached('ev',80) is False


def test_unplug_keeps_last_session_and_replug_starts_new_counters(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);now=utcnow();old=now-timedelta(hours=1)
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
    later=frame(now+timedelta(minutes=3),10000,stamp=now)
    later=replace(later,device_states={'ev':replace(later.device_states['ev'],energy_wh=None,energy_measured_at=None)})
    tracker.update(later,cfg)
    assert tracker.summary('ev')['soc_usable'] is False


def test_impossible_counter_jump_does_not_create_energy_or_infinite_cost(tmp_path):
    tracker,_,cfg=setup_tracker(tmp_path);cfg.devices[0].max_power_w=3700
    now=utcnow();old=now-timedelta(hours=1)
    tracker.update(frame(now,10000,stamp=old),cfg)
    tracker.update(frame(now+timedelta(seconds=30),1e308,price=1e308,stamp=old),cfg)
    assert tracker.summary('ev')['energy_kwh']==0
    assert tracker.summary('ev')['energy_partial'] is True
    assert tracker.summary('ev')['soc_usable'] is False
