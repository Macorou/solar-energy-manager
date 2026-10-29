from dataclasses import replace
from datetime import timedelta

from app.domain.devices import DeviceState
from app.domain.measurements import Sample,utcnow
from app.domain.site import SiteSnapshot
from app.runtime.dispatcher import Dispatcher
from app.settings import DeviceConfig
from app.storage.database import SQLiteStore


def test_charger_confirmation_accepts_grid_read_eleven_microseconds_before_power(tmp_path):
    now=utcnow();sent=now-timedelta(seconds=10)
    dispatcher=Dispatcher(SQLiteStore(tmp_path/'db'))
    dispatcher.records['ev']={'id':'limit','action':'set_power','power_w':3680,'status':'accepted',
        'sent_at':sent.isoformat()}
    grid=Sample(4000,'W','HA',now,now,checked_at=now)
    power=Sample(3600,'W','OCPP',now,now,checked_at=now+timedelta(microseconds=11))
    snapshot=SiteSnapshot(now+timedelta(seconds=1),grid=grid,
        device_states={'ev':DeviceState('ev',power,'Charging',True)})
    assert dispatcher.reconcile(snapshot,{'ev':DeviceConfig(id='ev',name='EV',kind='charger')})==['ev']


def test_zero_current_suspension_can_be_observed_with_transaction_still_active(tmp_path):
    now=utcnow();dispatcher=Dispatcher(SQLiteStore(tmp_path/'db'))
    dispatcher.records['ev']={'id':'pause','action':'suspend','power_w':0,'status':'accepted',
        'sent_at':(now-timedelta(seconds=10)).isoformat()}
    power=Sample(0,'W','OCPP',now,now,checked_at=now)
    state=DeviceState('ev',power,'SuspendedEVSE',True,status_measured_at=now,
        transaction_active=True,start_pending=False)
    snapshot=SiteSnapshot(now,grid=Sample(500,'W','HA',now,now,checked_at=now),device_states={'ev':state})
    assert dispatcher.reconcile(snapshot,{'ev':DeviceConfig(id='ev',name='EV',kind='charger')})==['ev']


def test_charger_power_prefers_native_measurement_and_can_derive_it_from_current():
    from app.runtime.charger_measurements import select_power
    now=utcnow();native=Sample(3680,'W','OCPP',now,now,checked_at=now)
    ha=Sample(0,'W','HA',now-timedelta(days=1),now,checked_at=now)
    state=DeviceState('ev',native,'Charging',True)
    config=DeviceConfig(id='ev',name='EV',kind='charger')
    assert select_power(state,ha,config,now,30)==native
    state=replace(state,observed_power=None,currents={'L1':Sample(16,'A','OCPP',now,now,checked_at=now)})
    assert select_power(state,ha,config,now,30).value==3680
