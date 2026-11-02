"""A charger reservation follows its latest offer and ends once the real draw is measured."""
from dataclasses import replace
from datetime import timedelta
import pytest
from app.domain.commands import CommandResult
from app.domain.devices import Reservation
from app.domain.measurements import Sample, utcnow
from app.runtime.coordinator import Coordinator
from app.settings import SettingsDocument
from test_charging_accounting import setup_tracker, frame


def charger_runtime(tmp_path, mode='manual'):
    _, store, cfg = setup_tracker(tmp_path)
    cfg.devices[0].armed = True; cfg.devices[0].mode = mode
    cfg.devices[0].min_power_w = 1380; cfg.devices[0].max_power_w = 3680; cfg.devices[0].max_current_a = 16
    store.save_settings(cfg.model_dump(mode='json'))

    class Adapter:
        async def execute(self, intent):
            return CommandResult(intent.id, True)
    return Coordinator(store, adapters={'ev': Adapter()}), cfg


def state(snapshot, status, power, at):
    sample = Sample(power, 'W', 'OCPP ev', at, at, checked_at=at)
    return replace(snapshot, device_states={'ev': replace(snapshot.device_states['ev'],
        observed_state=status, observed_power=sample)})


@pytest.mark.asyncio
async def test_a_lower_offer_replaces_the_previous_charger_reservation(tmp_path):
    runtime, _ = charger_runtime(tmp_path); now = utcnow()
    await runtime.tick(frame(now, 10000, stamp=now))
    for job in runtime.command_tasks.values(): await job
    assert runtime.reservations['ev'].power_w == pytest.approx(3680)
    # A lower site limit forces 10 A before the 16 A offer is confirmed (no reading after it):
    # its reservation must not be kept as a maximum.
    unconfirmed = state(frame(now+timedelta(seconds=2), 10000, stamp=now), 'Charging', 2000, now)
    await runtime.tick(replace(unconfirmed, site_limit_w=1300))
    assert runtime.dispatcher.records['ev']['status'] == 'accepted'
    for job in runtime.command_tasks.values(): await job
    assert runtime.dispatcher.records['ev']['power_w'] == pytest.approx(2300)
    assert runtime.reservations['ev'].power_w == pytest.approx(2300)


@pytest.mark.parametrize('status,age,released', [
    ('SuspendedEV', 0, True),      # the car declines: its measured zero is the real draw
    ('Charging', 0, True),         # the meter already includes the new offer
    ('SuspendedEVSE', 0, False),   # the station is still starting the charge
    ('Preparing', 0, False),
    ('SuspendedEV', 95, False),    # no measurement after the command
])
def test_expired_charger_reservation_needs_a_fresh_native_state(tmp_path, status, age, released):
    runtime, cfg = charger_runtime(tmp_path); now = utcnow()
    runtime.reservations['ev'] = Reservation('ev', 3680, 'cmd', now+timedelta(seconds=90))
    configs = {d.id: d for d in cfg.devices}
    later = now+timedelta(seconds=91)
    snapshot = state(frame(later, 10000, stamp=now), status, 0 if status != 'Charging' else 2300,
                     later-timedelta(seconds=age))
    runtime.release_charger_reservations(replace(snapshot, sample_max_age_s=120), configs)
    assert ('ev' not in runtime.reservations) is released


@pytest.mark.asyncio
async def test_an_offer_to_a_car_in_suspendedev_is_confirmed_by_a_status_reread(tmp_path):
    _, store, cfg = setup_tracker(tmp_path)
    cfg.devices[0].armed = True; cfg.devices[0].mode = 'manual'
    cfg.devices[0].min_power_w = 1380; cfg.devices[0].max_power_w = 3680; cfg.devices[0].max_current_a = 16
    store.save_settings(cfg.model_dump(mode='json'))
    requests = []

    class Station:
        async def execute(self, intent):
            return CommandResult(intent.id, True)

        async def request_status(self):
            requests.append(utcnow())
            return True
    runtime = Coordinator(store, adapters={'ev': Station()}); now = utcnow()
    await runtime.tick(frame(now, 10000, stamp=now))
    for job in runtime.command_tasks.values(): await job
    assert runtime.dispatcher.records['ev']['status'] == 'accepted'
    # The car declines: no draw, no Current.Offered, and a status older than the offer.
    idle = state(frame(now+timedelta(seconds=2), 10000, stamp=now), 'SuspendedEV', 0, now+timedelta(seconds=2))
    idle = replace(idle, device_states={'ev': replace(idle.device_states['ev'], status_measured_at=now-timedelta(minutes=5),
                                                      status_received_at=now-timedelta(minutes=5))})
    await runtime.tick(idle)
    for job in list(runtime.refresh_tasks): await job
    assert len(requests) == 1 and runtime.dispatcher.records['ev']['status'] == 'accepted'
    # The re-sent StatusNotification carries a time after the offer: the offer is confirmed.
    at = now+timedelta(seconds=4)
    reread = replace(idle, at=at, device_states={'ev': replace(idle.device_states['ev'], status_measured_at=at,
        status_received_at=at, observed_power=Sample(0, 'W', 'OCPP ev', at, at, checked_at=at))},
        grid=Sample(1000, 'W', 'test', at, at, checked_at=at))
    await runtime.tick(reread)
    assert runtime.dispatcher.records['ev']['status'] == 'observed'


@pytest.mark.asyncio
async def test_a_lost_stop_does_not_block_the_next_charge(tmp_path):
    _, store, cfg = setup_tracker(tmp_path)
    cfg.devices[0].armed = True; cfg.devices[0].mode = 'manual'
    cfg.devices[0].min_power_w = 1380; cfg.devices[0].max_power_w = 3680; cfg.devices[0].max_current_a = 16
    store.save_settings(cfg.model_dump(mode='json'))
    now = utcnow()
    # A stop (end of window, target reached...) whose OCPP exchange was lost: no reservation
    # and no draw, so no decision would ever send a new command.
    store.set('runtime_commands', {'ev': {'id': 'lost', 'device_id': 'ev', 'action': 'suspend', 'status': 'unknown',
        'power_w': 0, 'sent_at': (now-timedelta(minutes=10)).isoformat(), 'expires_at': None,
        'confirm_by': (now-timedelta(minutes=8)).isoformat(), 'reason': 'Fin du créneau réseau'}})
    sent = []

    class Station:
        async def execute(self, intent):
            sent.append(intent.action)
            return CommandResult(intent.id, True)

        async def request_status(self):
            return True
    runtime = Coordinator(store, adapters={'ev': Station()})

    def idle(seconds):
        at = now+timedelta(seconds=seconds)
        snapshot = state(frame(at, 10000, stamp=now), 'Preparing', 0, at)
        return replace(snapshot, device_states={'ev': replace(snapshot.device_states['ev'], status_measured_at=at,
            status_received_at=at, transaction_active=False, start_pending=False)})

    async def tick(seconds):
        await runtime.tick(idle(seconds))
        for job in list(runtime.command_tasks.values()): await job
    # A fresh idle status re-read after the lost stop confirms it; the same cycle restarts the charge.
    await tick(0)
    assert sent == ['set_power']
    assert runtime.dispatcher.records['ev']['action'] == 'set_power' and 'ev' not in runtime.errors


def test_an_unexpired_or_water_heater_reservation_is_kept(tmp_path):
    runtime, cfg = charger_runtime(tmp_path); now = utcnow()
    runtime.reservations['ev'] = Reservation('ev', 3680, 'cmd', now+timedelta(seconds=90))
    configs = {d.id: d for d in cfg.devices}
    runtime.release_charger_reservations(state(frame(now+timedelta(seconds=30), 10000, stamp=now),
        'SuspendedEV', 0, now+timedelta(seconds=30)), configs)
    assert 'ev' in runtime.reservations
    heater = SettingsDocument(devices=[{'id': 'ev', 'name': 'Ballon', 'kind': 'water_heater'}])
    later = now+timedelta(seconds=91)
    runtime.release_charger_reservations(state(frame(later, 10000, stamp=now), 'off', 0, later),
                                         {d.id: d for d in heater.devices})
    assert 'ev' in runtime.reservations
