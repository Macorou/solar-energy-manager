"""Station messages are ordered on the station clock and dated on SEM's clock, never mixed.

A status sent with the end of a session, or stamped slightly ahead of SEM's clock, was
dropped without a trace: SEM kept an outdated state of the charger.
"""
from datetime import timedelta

from app.connectors.ocpp.registry import OcppRegistry
from app.connectors.ocpp.station import Station
from app.domain.measurements import utcnow
from app.settings import DeviceConfig
from app.storage.database import SQLiteStore


def station(tmp_path):
    cfg = DeviceConfig(id='ev', name='Pulsar Plus', kind='charger', charge_point_id='box', armed=True)
    reg = OcppRegistry(SQLiteStore(tmp_path/'db'), lambda: [cfg], lambda _: None)
    return reg, Station('box', None, reg)


def journal(reg):
    return [(entry['level'], entry['message']) for entry in reg.store.journal.query(level='TRACE')['entries']]


def test_status_sent_with_the_end_of_a_session_is_kept(tmp_path):
    reg, box = station(tmp_path)
    unplugged = utcnow()-timedelta(seconds=1)  # the station stamps both messages when the cable is pulled
    reg.active[('box', 1)] = {'transaction_id': 42, 'meter_start': 0, 'timestamp': None}
    box.status(1, 'NoError', 'Charging', timestamp=(unplugged-timedelta(minutes=5)).isoformat())
    box.stop_transaction(meter_stop=1000, timestamp=unplugged.isoformat(), transaction_id=42)
    assert reg.states['ev'].observed_state == 'Finishing'
    box.status(1, 'NoError', 'Available', timestamp=(unplugged+timedelta(milliseconds=200)).isoformat())
    state = reg.states['ev']
    assert state.observed_state == 'Available' and state.vehicle_connected is False


def test_status_stamped_ahead_of_sem_clock_is_kept_and_dated_at_its_reception(tmp_path):
    reg, box = station(tmp_path)
    ahead = lambda seconds: (utcnow()+timedelta(seconds=seconds)).isoformat()
    box.status(1, 'NoError', 'Preparing', timestamp=ahead(20))
    box.status(1, 'NoError', 'Charging', timestamp=ahead(21))
    state = reg.states['ev']
    assert state.observed_state == 'Charging'
    assert state.status_measured_at <= utcnow()
    warnings = [message for level, message in journal(reg) if level == 'WARN']
    assert len(warnings) == 1 and 'Horloge de la borne en avance' in warnings[0]


def test_a_whole_session_start_is_followed_on_a_station_clock_ahead(tmp_path):
    reg, box = station(tmp_path)
    t0 = utcnow()+timedelta(seconds=3)
    stamp = lambda s: (t0+timedelta(seconds=s)).isoformat()
    box.status(1, 'NoError', 'Preparing', timestamp=stamp(0))
    box.status(1, 'NoError', 'SuspendedEV', timestamp=stamp(.5))
    box.start_transaction(1, 'SEM', 5141070, stamp(.3))
    assert reg.states['ev'].observed_state == 'SuspendedEV'
    box.status(1, 'NoError', 'SuspendedEVSE', timestamp=stamp(.8))
    assert reg.states['ev'].observed_state == 'SuspendedEVSE'
    box.stop_transaction(meter_stop=5141080, timestamp=stamp(2), transaction_id=reg.active[('box', 1)]['transaction_id'])
    box.status(1, 'NoError', 'Available', timestamp=stamp(2.1))
    assert reg.states['ev'].observed_state == 'Available'


def test_an_older_or_unreadable_status_is_still_ignored_and_now_leaves_a_trace(tmp_path):
    reg, box = station(tmp_path)
    now = utcnow()
    box.status(1, 'NoError', 'Charging', timestamp=(now-timedelta(seconds=5)).isoformat())
    box.status(1, 'NoError', 'Preparing', timestamp=(now-timedelta(seconds=60)).isoformat())
    box.status(1, 'NoError', 'Available', timestamp='yesterday')
    assert reg.states['ev'].observed_state == 'Charging'
    ignored = [message for _, message in journal(reg) if 'ignoré' in message]
    assert len(ignored) == 2 and 'Preparing' in ignored[0] and 'Available' in ignored[1]


def test_meter_values_stamped_ahead_of_sem_clock_are_kept(tmp_path):
    reg, box = station(tmp_path)
    box.status(1, 'NoError', 'Charging', timestamp=utcnow().isoformat())
    box.meter_values(1, [{'timestamp': (utcnow()+timedelta(seconds=20)).isoformat(), 'sampled_value': [
        {'value': '4000', 'measurand': 'Power.Active.Import', 'unit': 'W'}]}])
    power = reg.states['ev'].observed_power
    assert power.value == 4000 and power.usable(utcnow(), 30)
