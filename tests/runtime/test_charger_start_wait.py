import asyncio
from dataclasses import replace
from datetime import datetime,timedelta

from app.domain.commands import CommandIntent,CommandResult
from app.domain.devices import DeviceState
from app.domain.measurements import Sample,utcnow
from app.domain.site import SiteSnapshot
from app.runtime.coordinator import Coordinator
from app.settings import DeviceConfig,SettingsDocument
from app.storage.database import SQLiteStore


class Adapter:
    def __init__(self):self.calls=[]
    async def execute(self,intent):
        self.calls.append(intent)
        return CommandResult(intent.id,True)


def runtime(tmp_path):
    device=DeviceConfig(id='ev',name='EV',kind='charger',armed=True,
        capabilities_verified=True,offline_behavior_verified=True,mode='manual',
        min_power_w=1380,max_power_w=3910)
    config=SettingsDocument(devices=[device],site_limit_w=11000)
    store=SQLiteStore(tmp_path/'db');store.save_settings(config.model_dump(mode='json'))
    store.set('manual_controls',{'ev':{'until':(utcnow()+timedelta(hours=1)).isoformat(),'previous_mode':'planned'}})
    source=Adapter()
    return Coordinator(store,adapters={'ev':source}),device,source


async def test_new_charge_has_five_minutes_to_confirm_power(tmp_path):
    controller,device,_=runtime(tmp_path);now=utcnow()
    controller.enqueue(CommandIntent('start','ev','set_power',3910,now+timedelta(seconds=90)),device)
    await controller.command_tasks['ev']
    record=controller.dispatcher.records['ev']
    assert (datetime.fromisoformat(record['confirm_by'])-datetime.fromisoformat(record['sent_at'])).total_seconds()==300


async def test_pending_profile_renews_without_resetting_the_five_minute_deadline(tmp_path):
    controller,device,source=runtime(tmp_path);now=utcnow();initial=now-timedelta(seconds=120)
    deadline=(initial+timedelta(seconds=300)).isoformat()
    controller.dispatcher.records['ev']={'id':'start','device_id':'ev','action':'set_power','power_w':3910,
        'sent_at':initial.isoformat(),'expires_at':(initial+timedelta(seconds=90)).isoformat(),
        'confirm_by':deadline,'reason':'Planning','status':'accepted'}
    controller.engine.requested['ev']=3910
    s=lambda v:Sample(v,'W','HA',now-timedelta(days=1),now,checked_at=now)
    snapshot=SiteSnapshot(now,grid=s(700),site_limit_w=11000,
        device_states={'ev':DeviceState('ev',s(0),'Charging',True)})
    await controller.tick(snapshot)
    await asyncio.gather(*controller.command_tasks.values())
    assert len(source.calls)==1 and source.calls[0].action=='set_power' and source.calls[0].limit_w==3910
    record=controller.dispatcher.records['ev']
    assert record['confirm_by']==deadline
    assert record['effect_since']==initial.isoformat()
    assert datetime.fromisoformat(record['expires_at'])>now+timedelta(seconds=80)
    # A measurement made after the first start but before the renewal is valid.
    power=Sample(3600,'W','HA',now-timedelta(seconds=5),now,checked_at=now)
    observed=replace(snapshot,device_states={'ev':replace(snapshot.device_states['ev'],observed_power=power)})
    assert controller.dispatcher.reconcile(observed,{'ev':device})==['ev']


async def test_pending_charge_still_stops_after_five_minutes_without_power(tmp_path):
    controller,device,source=runtime(tmp_path);now=utcnow();initial=now-timedelta(seconds=301)
    controller.dispatcher.records['ev']={'id':'start','action':'set_power','power_w':3910,
        'sent_at':initial.isoformat(),'expires_at':(initial+timedelta(seconds=90)).isoformat(),
        'confirm_by':(initial+timedelta(seconds=300)).isoformat(),'reason':'Planning','status':'accepted'}
    controller.engine.requested['ev']=3910
    s=lambda v:Sample(v,'W','HA',now-timedelta(days=1),now,checked_at=now)
    await controller.tick(SiteSnapshot(now,grid=s(700),site_limit_w=11000,
        device_states={'ev':DeviceState('ev',s(0),'Charging',True)}))
    await asyncio.gather(*controller.command_tasks.values())
    assert len(source.calls)==1 and source.calls[0].action=='suspend'
