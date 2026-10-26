import asyncio
from dataclasses import asdict,replace
from datetime import datetime,timedelta,timezone
from app.settings import SettingsDocument
from app.domain.devices import DeviceSpec,DeviceState,Reservation
from app.domain.measurements import utcnow
from app.domain.site import SiteSnapshot
from app.domain.commands import CommandIntent
from app.engine.engine import EnergyEngine
from app.engine.policies import DevicePolicy
from app.engine.budget import solar_budget_w
from app.scheduling.recurrence import occurrences_for
from app.scheduling.authorization import select_authorization
from app.scheduling.tariff_windows import is_off_peak
from app.connectors.home_assistant.client import HomeAssistantSource
from app.connectors.ocpp.registry import ChargerAdapter
from app.api.water_heaters import adapter as ariston_adapter
from .dispatcher import Dispatcher
from .instance import InstanceLock


class Coordinator:
    def __init__(self,store,app=None,adapters=None):
        self.store,self.app=store,app
        self.adapters=adapters or {}
        self.engine=EnergyEngine()
        self.dispatcher=Dispatcher(store)
        self.reservations={}
        for key,value in store.get('runtime_reservations',{}).items():
            self.reservations[key]=Reservation(key,value['power_w'],value['command_id'],
                datetime.fromisoformat(value['expires_at']))
        for key,record in self.dispatcher.records.items():
            if record['status']!='observed' and record['power_w']:
                self.reservations[key]=Reservation(key,record['power_w'],record['id'],
                    datetime.fromisoformat(record['sent_at'])+timedelta(seconds=90))
        self.lock=asyncio.Lock()
        self.command_tasks={}; self.workers={}; self.cache={}; self.telemetry={}; self.errors={}
        self.ha=None; self.ha_signature=None; self.worker_signatures={}
        self.snapshot=SiteSnapshot(utcnow())
        self.reasons={}; self.authorizations={}; self.running=False; self.loop_task=None
        self.last_tick=None
        self.instance=InstanceLock(store.path.parent/'controller.lock')

    async def start(self):
        self.instance.acquire()
        self.running=True
        self.loop_task=asyncio.create_task(self.run())

    async def stop(self):
        self.running=False
        jobs=[self.loop_task,*self.workers.values(),*self.command_tasks.values()]
        for job in jobs:
            if job: job.cancel()
        await asyncio.gather(*(j for j in jobs if j),return_exceptions=True)
        if self.ha: await self.ha.close()
        if self.app: await self.app.state.peugeot.close()
        self.instance.close()

    async def run(self):
        while self.running:
            try: await self.tick()
            except asyncio.CancelledError: raise
            except Exception: self.errors['runtime']='Évaluation indisponible'
            await asyncio.sleep(2)

    def worker(self,key,signature,coroutine):
        old=self.workers.get(key)
        if old and self.worker_signatures.get(key)==signature and not old.done():
            coroutine.close(); return
        if old: old.cancel()
        self.worker_signatures[key]=signature
        self.workers[key]=asyncio.create_task(coroutine)

    async def poll_ariston(self,device):
        from types import SimpleNamespace
        source=ariston_adapter(SimpleNamespace(app=self.app),device)
        self.adapters[device.id]=source
        while self.running:
            try:
                state=await asyncio.wait_for(source.connect() if not source.device else source.read_state(),25)
                self.cache[device.id]=state
                if source.device and not source.report: await source.probe_capabilities()
            except asyncio.CancelledError: raise
            except Exception: self.cache[device.id]=DeviceState(device.id,fault='provider_unavailable')
            await asyncio.sleep(SettingsDocument.model_validate(self.store.load_settings()).ariston.poll_interval_s)

    async def poll_vehicle(self,vehicle):
        while self.running:
            try:
                self.telemetry[vehicle.id]=await asyncio.wait_for(self.app.state.peugeot.read_telemetry(vehicle.vin),25)
                self.errors.pop('vehicle_'+vehicle.id,None)
            except asyncio.CancelledError: raise
            except Exception as error:
                # Only known provider codes can reach the public state.
                code=str(error)
                self.errors['vehicle_'+vehicle.id]=code if code in ('not_configured','reconnect_required',
                    'rate_limited','vehicle_not_found','vin_required') else 'provider_unavailable'
            await asyncio.sleep(SettingsDocument.model_validate(self.store.load_settings()).peugeot.poll_interval_s)

    async def acquire(self,config):
        if self.app:
            token=self.app.state.secrets.get('ha_token') or ''
            signature=(config.home_assistant.model_dump_json(),token)
            if signature!=self.ha_signature:
                if self.ha: await self.ha.close()
                self.ha=HomeAssistantSource(config.home_assistant,token,max_age_s=config.sample_max_age_s)
                self.ha_signature=signature
                if token and config.home_assistant.url:
                    self.worker('ha',signature,self.ha.subscribe(lambda _:None))
                elif 'ha' in self.workers:
                    self.workers.pop('ha').cancel()
            for device in config.devices:
                if device.kind=='charger': self.adapters[device.id]=ChargerAdapter(self.app.state.ocpp,device)
                elif self.running:
                    self.worker('dhw_'+device.id,device.model_dump_json()+config.ariston.model_dump_json(),
                                self.poll_ariston(device))
            self.app.state.peugeot.config=config.peugeot
            for vehicle in config.vehicles:
                if self.running:
                    self.worker('vehicle_'+vehicle.id,vehicle.model_dump_json()+config.peugeot.model_dump_json(),
                                self.poll_vehicle(vehicle))
            valid={'ha'}|{'dhw_'+d.id for d in config.devices if d.kind=='water_heater'}|{'vehicle_'+v.id for v in config.vehicles}
            for key in list(self.workers):
                if key not in valid: self.workers.pop(key).cancel()
        states={}
        now=utcnow()
        for device in config.devices:
            if device.kind=='charger' and device.id in self.adapters:
                state=await self.adapters[device.id].read_state()
            else: state=self.cache.get(device.id,DeviceState(device.id))
            if device.kind=='water_heater' and state.measured_at and (now-state.measured_at).total_seconds()>config.ariston.max_age_s:
                state=replace(state,connected=False,fault='stale_cloud_state')
            power=self.ha.device_power(device.id) if self.ha else None
            states[device.id]=replace(state,observed_power=power or state.observed_power)
        base=self.ha.snapshot() if self.ha else SiteSnapshot(now)
        return replace(base,at=now,device_states=states,vehicle_telemetry=dict(self.telemetry),
            site_limit_w=config.site_limit_w,export_margin_w=config.export_margin_w,
            sample_max_age_s=config.sample_max_age_s,reservations=tuple(self.reservations.values()))

    def policies(self,config,now):
        manuals=self.store.get('manual_controls',{})
        policies={}
        changed=False
        for device in config.devices:
            entry=manuals.get(device.id)
            until=datetime.fromisoformat(entry['until']) if entry else None
            if device.mode=='manual' and (not until or until<=now):
                device.mode=entry.get('previous_mode','off') if entry else 'off'
                manuals.pop(device.id,None); changed=True
            cloud=device.cloud.model_dump()
            policies[device.id]=DevicePolicy(device.id,device.mode,**cloud,target=device.target,
                armed=device.armed,vehicle_id=device.vehicle_id,soc_max_age_s=config.peugeot.max_age_s,
                manual_until=until,off_peak=is_off_peak(now,config.off_peak,config.timezone))
        if changed:
            self.store.set('manual_controls',manuals)
            self.store.save_settings(config.model_dump(mode='json'))
        return policies

    async def tick(self,snapshot=None):
        async with self.lock:
            config=SettingsDocument.model_validate(self.store.load_settings())
            snapshot=snapshot or await self.acquire(config)
            snapshot=replace(snapshot,reservations=tuple(self.reservations.values()))
            configs={d.id:d for d in config.devices}
            for key in self.dispatcher.reconcile(snapshot,configs): self.reservations.pop(key,None)
            policies=self.policies(config,snapshot.at)
            occurrences=[o for p in config.schedules for o in occurrences_for(p,snapshot.at,
                snapshot.at+timedelta(days=8),config.timezone)]
            authorizations={d.id:select_authorization(d.vehicle_id,snapshot.at,occurrences,d.default_soc_target)
                            for d in config.devices if d.kind=='charger'}
            for key,record in self.dispatcher.records.items():
                if record['status'] in ('sending','accepted','unknown'):
                    age=(snapshot.at-datetime.fromisoformat(record['sent_at'])).total_seconds()
                    if record['status']=='unknown' or age>90:
                        # Pending physical effects are never retried as new starts.
                        if key in policies: policies[key]=replace(policies[key],mode='off')
                        self.errors[key]='Résultat de commande inconnu : vérification requise'
            specs=[DeviceSpec(d.id,d.kind,min_power_w=d.min_power_w,max_power_w=d.max_power_w,
                priority=d.priority) for d in config.devices]
            batch=self.engine.evaluate(snapshot,specs,policies,authorizations)
            self.reasons=batch.reasons
            self.authorizations=authorizations
            for reservation in batch.reservations:
                old=self.reservations.get(reservation.device_id)
                self.reservations[reservation.device_id]=replace(reservation,power_w=max(reservation.power_w,old.power_w if old else 0))
            for intent in batch.commands:
                self.enqueue(intent,configs[intent.device_id])
            # Renew finite OCPP profiles without issuing another remote start before observation.
            for device in config.devices:
                record=self.dispatcher.records.get(device.id)
                if (device.kind=='charger' and device.armed and record and record['status']=='observed'
                    and record['power_w']>0 and self.engine.requested.get(device.id,0)>0
                    and (snapshot.at-datetime.fromisoformat(record['sent_at'])).total_seconds()>40
                    and not any(c.device_id==device.id for c in batch.commands)):
                    import uuid
                    self.enqueue(CommandIntent(str(uuid.uuid4()),device.id,'set_power',record['power_w'],
                        snapshot.at+timedelta(seconds=90),'Renouvellement du profil autorisé'),device)
            self.snapshot=snapshot
            self.store.set('runtime_reservations',{key:{'power_w':r.power_w,'command_id':r.command_id,
                'expires_at':r.expires_at.isoformat()} for key,r in self.reservations.items()})
            self.last_tick=utcnow()
            return batch

    def enqueue(self,intent,config):
        existing=self.command_tasks.get(intent.device_id)
        if existing and not existing.done(): return
        if not config.armed or intent.device_id not in self.adapters: return
        async def send():
            # Re-read immediately before sending: a queued command cannot bypass a pause.
            current=SettingsDocument.model_validate(self.store.load_settings())
            device=next((d for d in current.devices if d.id==intent.device_id),None)
            if not device or not device.armed or (intent.action!='suspend' and device.mode!=config.mode):
                self.engine.forget(intent.device_id); return
            await self.dispatcher.dispatch(intent,self.adapters[intent.device_id])
        self.command_tasks[intent.device_id]=asyncio.create_task(send())

    def public_state(self):
        config=SettingsDocument.model_validate(self.store.load_settings())
        now=utcnow()
        def sample(value):
            if value is None:return None
            data=asdict(value)
            data['usable']=value.usable(now,config.sample_max_age_s)
            return data
        return {'simulation':False,'at':self.last_tick,'running':self.running,
            'grid':sample(self.snapshot.grid),'solar':sample(self.snapshot.solar),
            'solar_budget_w':solar_budget_w(replace(self.snapshot,at=now)),
            'off_peak':is_off_peak(now,config.off_peak,config.timezone),'errors':self.errors,
            'devices':[{'config':d.model_dump(mode='json'),
                'state':asdict(self.snapshot.device_states.get(d.id,DeviceState(d.id))),
                'reason':self.reasons.get(d.id,'En attente de mesures'),
                'command':self.dispatcher.records.get(d.id),
                'reservation_w':self.reservations[d.id].power_w if d.id in self.reservations else 0,
                'authorization':asdict(self.authorizations[d.id]) if d.id in self.authorizations else None}
                for d in config.devices],
            'vehicles':{key:asdict(value)|{'fresh':value.fresh(now,config.peugeot.max_age_s)}
                        for key,value in self.telemetry.items()}}
