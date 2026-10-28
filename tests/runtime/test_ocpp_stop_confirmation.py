import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest

from app.connectors.ocpp.registry import OcppRegistry
from app.connectors.ocpp.station import Station
from app.domain.devices import DeviceState
from app.domain.measurements import Sample, Quality, utcnow
from app.domain.site import SiteSnapshot
from app.runtime.coordinator import Coordinator
from app.runtime.dispatcher import Dispatcher
from app.settings import DeviceConfig, SettingsDocument
from app.storage.database import SQLiteStore


def stopped_frame(tmp_path):
    now=utcnow(); sent=now-timedelta(seconds=2)
    config=DeviceConfig(id='ev',name='EV',kind='charger',charge_point_id='box',armed=True,mode='planned',
        capabilities_verified=True,offline_behavior_verified=True)
    store=SQLiteStore(tmp_path/'db');store.save_settings(SettingsDocument(devices=[config]).model_dump(mode='json'))
    registry=OcppRegistry(store,lambda:[config],lambda _:None)
    registry.stations['box']=Station('box',None,registry)
    registry.states['ev']=DeviceState('ev',connected=True,observed_state='Charging')
    registry.active[('box',1)]={'transaction_id':42,'meter_start':5000000,'timestamp':sent.isoformat()}
    registry.stations['box'].stop_transaction(5000922,now.isoformat(),42)
    state=replace(registry.state('ev'),observed_power=Sample(0,'W','HA',now-timedelta(days=1),now,checked_at=now),
        status_measured_at=now)
    snapshot=SiteSnapshot(now,Sample(700,'W','HA-grid',now,now,checked_at=now),device_states={'ev':state},site_limit_w=11000)
    dispatcher=Dispatcher(store)
    dispatcher.records['ev']={'id':'stop','status':'accepted','action':'suspend','power_w':0,
        'sent_at':sent.isoformat(),'expires_at':(now+timedelta(seconds=60)).isoformat(),
        'confirm_by':(now+timedelta(seconds=60)).isoformat(),
        'reason':'Courant réel de recharge indisponible'}
    return dispatcher,snapshot,config


def test_native_ocpp_stop_and_checked_unchanged_zero_confirm_the_stop(tmp_path):
    dispatcher,snapshot,config=stopped_frame(tmp_path)
    assert dispatcher.reconcile(snapshot,{'ev':config})==['ev']
    assert dispatcher.records['ev']['status']=='observed'


@pytest.mark.parametrize('invalid',['transaction','pending','unknown_transaction','charging','old_status','future_status','offline','fault','old_check','nonzero','estimated'])
def test_old_zero_cannot_confirm_a_stop_without_native_idle_proof(tmp_path,invalid):
    dispatcher,snapshot,config=stopped_frame(tmp_path)
    state=snapshot.device_states['ev'];power=state.observed_power
    if invalid=='transaction':state=replace(state,transaction_active=True)
    elif invalid=='pending':state=replace(state,start_pending=True)
    elif invalid=='unknown_transaction':state=replace(state,transaction_active=None)
    elif invalid=='charging':state=replace(state,observed_state='Charging')
    elif invalid=='old_status':state=replace(state,status_measured_at=snapshot.at-timedelta(seconds=5))
    elif invalid=='future_status':state=replace(state,status_measured_at=snapshot.at+timedelta(seconds=1))
    elif invalid=='offline':state=replace(state,connected=False)
    elif invalid=='fault':state=replace(state,fault='Faulted')
    elif invalid=='old_check':power=replace(power,checked_at=snapshot.at-timedelta(seconds=5))
    elif invalid=='nonzero':power=replace(power,value=500)
    elif invalid=='estimated':power=replace(power,quality=Quality.ESTIMATED)
    state=replace(state,observed_power=power)
    assert dispatcher.reconcile(replace(snapshot,device_states={'ev':state}),{'ev':config})==[]


async def test_pending_stop_retains_the_real_reason_and_reads_only_status(tmp_path):
    dispatcher,snapshot,config=stopped_frame(tmp_path)
    snapshot=replace(snapshot,device_states={'ev':replace(snapshot.device_states['ev'],status_measured_at=snapshot.at-timedelta(seconds=5))})
    calls=[]
    class Adapter:
        async def request_status(self):calls.append('status');return True
    runtime=Coordinator(dispatcher.store,adapters={'ev':Adapter()})
    runtime.dispatcher.records=dispatcher.records
    runtime.engine.requested['ev']=0
    await runtime.tick(snapshot)
    await asyncio.sleep(0)
    assert 'Courant réel de recharge indisponible' in runtime.reasons['ev']
    assert 'Arrêt demandé' not in runtime.reasons['ev']
    assert calls==['status']
    await runtime.tick(snapshot)
    await asyncio.sleep(0)
    assert calls==['status']
