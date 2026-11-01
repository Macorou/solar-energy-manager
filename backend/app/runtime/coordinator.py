import asyncio
import re
import uuid
from dataclasses import asdict,replace
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from app.settings import SettingsDocument
from app.domain.devices import DeviceSpec,DeviceState,Reservation
from app.domain.measurements import Quality,utcnow
from app.domain.site import SiteSnapshot
from app.domain.commands import CommandIntent,CHARGER_START_WAIT_S,RESERVATION_S
from app.engine.engine import EnergyEngine,charger_goals
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
from .charging import ChargingTracker
from .energy_prices import device_prices
from .charger_measurements import select_power
from app.domain.vehicles import VehicleTelemetry


CHARGE_EFFICIENCY=.85  # EVCC's initial grid-to-battery efficiency


def plan_warnings(snapshot,config,occurrences):
    """Warn, never act, when a planned target needs more grid time than its window gives."""
    def duration(seconds):
        return f'{int(seconds//3600)} h {int(seconds%3600//60):02d}'
    warnings={}
    zone=ZoneInfo(config.timezone)
    vehicles={v.id:v for v in config.vehicles}
    for device in config.devices:
        vehicle=vehicles.get(device.vehicle_id)
        if device.kind!='charger' or device.mode!='planned' or not vehicle or not vehicle.capacity_kwh:
            continue
        upcoming=[o for o in occurrences if o.vehicle_id==vehicle.id and o.deadline_at>snapshot.at]
        telemetry=snapshot.vehicle_telemetry.get(vehicle.id)
        if not upcoming or not telemetry or not telemetry.usable(snapshot.at,config.peugeot.max_age_s):
            continue
        occurrence=min(upcoming,key=lambda o:o.deadline_at)
        power=min(device.max_power_w,device.max_current_a*device.voltage*device.phases)
        if telemetry.soc>=occurrence.target_soc or power<=0:
            continue
        needed=(occurrence.target_soc-telemetry.soc)/100*vehicle.capacity_kwh*1000/CHARGE_EFFICIENCY/power*3600
        available=max(0,(occurrence.deadline_at-max(snapshot.at,occurrence.network_start_at)).total_seconds())
        if needed>available:
            warnings[device.id]=(f'Objectif {occurrence.target_soc:g} % probablement non atteint à '
                f'{occurrence.deadline_at.astimezone(zone):%H:%M} : environ {duration(needed)} de charge réseau '
                f'nécessaires, {duration(available)} disponibles dans le créneau')
    return warnings


def command_reason(record):
    value=record.get('error') or record.get('reason') or 'Arrêt demandé'
    prefixes=('Arrêt en cours : ','Vérification requise : ')
    while any(value.startswith(prefix) for prefix in prefixes):
        value=next(value[len(prefix):] for prefix in prefixes if value.startswith(prefix))
    return value


class Coordinator:
    def __init__(self,store,app=None,adapters=None):
        self.store,self.app=store,app
        self.adapters=adapters or {}
        self.engine=EnergyEngine()
        self.engine.charger_limit_faults=set(store.get('charger_limit_faults',[]))
        self.engine.charger_fault_retry={key:{'until':datetime.fromisoformat(value['until']),'attempt':value['attempt']}
            for key,value in store.get('charger_limit_retry',{}).items()}
        self.charging=ChargingTracker(store)
        self.last_plugged: dict[str,bool]={}
        self.link_seen: dict[str,datetime|None]={}
        network_state=store.get('runtime_network_state',{})
        self.engine.network_allowed=network_state.get('allowed',{})
        self.engine.network_stop_pending=set(network_state.get('stop_pending',[]))
        self.dispatcher=Dispatcher(store)
        kinds={item['id']:item['kind'] for item in (store.load_settings() or {}).get('devices',[])}
        for key,record in self.dispatcher.records.items():
            if kinds.get(key)=='charger' and record['status'] in ('accepted','observed'):
                self.engine.requested[key]=record['power_w']
                self.engine.charger_offered[key]=record['power_w']
                self.engine.charger_commanded[key]=record['power_w']
        self.reservations={}
        for key,value in store.get('runtime_reservations',{}).items():
            self.reservations[key]=Reservation(key,value['power_w'],value['command_id'],
                datetime.fromisoformat(value['expires_at']))
        for key,record in self.dispatcher.records.items():
            if record['status']!='observed' and record['power_w']:
                self.reservations[key]=Reservation(key,record['power_w'],record['id'],
                    datetime.fromisoformat(record['sent_at'])+timedelta(seconds=RESERVATION_S))
        self.lock=asyncio.Lock()
        self.command_tasks={}; self.workers={}; self.cache={}; self.telemetry={}; self.errors={}
        self.queued_intents={};self.refresh_tasks=set()
        self.stop_status_requests={}
        if store.get('queued_intents',{}):
            store.append_event({'kind':'queued_commands_require_reconciliation'})
        store.set('queued_intents',{})  # Recalculate from fresh state; never replay queued starts.
        self.ha=None; self.ha_signature=None; self.worker_signatures={}
        self.snapshot=SiteSnapshot(utcnow())
        self.reasons={}; self.authorizations={}; self.running=False; self.loop_task=None
        self.effective_targets={}; self.target_sources={}; self.plan_warnings={}
        self.last_tick=None
        self.last_diagnostic=None;self.last_diagnostic_reasons={}
        self.instance=InstanceLock(store.path.parent/'controller.lock')

    async def start(self):
        self.instance.acquire()
        self.running=True
        self.loop_task=asyncio.create_task(self.run())

    async def stop(self):
        self.running=False
        jobs=[self.loop_task,*self.workers.values(),*self.command_tasks.values(),*self.refresh_tasks]
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
            except Exception as error:
                self.errors['runtime']='Évaluation indisponible'
                self.store.journal.write('ERROR','runtime',f'Évaluation indisponible ({type(error).__name__})')
            await asyncio.sleep(2)

    def worker(self,key,signature,coroutine):
        old=self.workers.get(key)
        if old and self.worker_signatures.get(key)==signature and not old.done():
            coroutine.close(); return
        if old: old.cancel()
        self.worker_signatures[key]=signature
        self.workers[key]=asyncio.create_task(coroutine)

    async def poll_ariston(self,device,source):
        while self.running:
            try:
                state=await asyncio.wait_for(source.connect() if not source.initialized else source.read_state(),25)
                if self.adapters.get(device.id) is source: self.cache[device.id]=state
                if source.device and not source.report: await source.probe_capabilities()
            except asyncio.CancelledError: raise
            except Exception as error:
                if self.adapters.get(device.id) is source:
                    self.cache[device.id]=DeviceState(device.id,fault='provider_unavailable')
                self.store.journal.write('ERROR','ariston:'+device.id,f'Lecture impossible ({type(error).__name__})')
            await asyncio.sleep(SettingsDocument.model_validate(self.store.load_settings()).ariston.poll_interval_s)

    async def poll_vehicle(self,vehicle):
        while self.running:
            try:
                self.telemetry[vehicle.id]=await asyncio.wait_for(self.app.state.peugeot.read_telemetry(vehicle.vin),25)
                self.errors.pop('vehicle_'+vehicle.id,None)
            except asyncio.CancelledError: raise
            except Exception as error:
                if vehicle.id in self.telemetry:
                    self.telemetry[vehicle.id]=replace(self.telemetry[vehicle.id],quality=Quality.UNAVAILABLE)
                # Only known provider codes can reach the public state.
                code=str(error)
                self.errors['vehicle_'+vehicle.id]=code if code in ('not_configured','reconnect_required',
                    'rate_limited','vehicle_not_found','vin_required') else 'provider_unavailable'
                self.store.journal.write('WARN','peugeot','Télémétrie indisponible : '+self.errors['vehicle_'+vehicle.id])
            await asyncio.sleep(SettingsDocument.model_validate(self.store.load_settings()).peugeot.poll_interval_s)

    async def acquire(self,config):
        if self.app:
            token=self.app.state.secrets.get('ha_token') or ''
            signature=(config.home_assistant.model_dump_json(),token)
            if signature!=self.ha_signature:
                if self.ha: await self.ha.close()
                self.ha=HomeAssistantSource(config.home_assistant,token,max_age_s=config.sample_max_age_s,journal=self.store.journal)
                self.ha_signature=signature
                if token and config.home_assistant.url:
                    self.worker('ha',signature,self.ha.subscribe(lambda _:None))
                elif 'ha' in self.workers:
                    self.workers.pop('ha').cancel()
            for device in config.devices:
                if device.kind=='charger': self.adapters[device.id]=ChargerAdapter(self.app.state.ocpp,device,config.phase_control_enabled)
                elif self.running:
                    from types import SimpleNamespace
                    source=ariston_adapter(SimpleNamespace(app=self.app),device)
                    if self.adapters.get(device.id) is not source:
                        self.cache.pop(device.id,None)
                        self.adapters[device.id]=source
                    self.worker('dhw_'+device.id,id(source),
                                self.poll_ariston(device,source))
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
            if device.kind=='water_heater':
                state=replace(state,target_reached=bool(state.temperature is not None and device.target is not None
                                                       and state.temperature>=device.target))
            power=self.ha.device_power(device.id) if self.ha else None
            states[device.id]=replace(state,observed_power=select_power(state,power,device,now,config.sample_max_age_s)
                if device.kind=='charger' else power or state.observed_power)
        base=self.ha.snapshot() if self.ha else SiteSnapshot(now)
        return replace(base,at=now,device_states=states,vehicle_telemetry=dict(self.telemetry),
            phase_control_enabled=config.phase_control_enabled,phase_margin_a=config.phase_margin_a,
            site_limit_w=config.site_limit_w,export_margin_w=config.export_margin_w,
            sample_max_age_s=config.sample_max_age_s,reservations=tuple(self.reservations.values()),
            grid_fallback_current_a=config.grid_fallback_current_a)

    def policies(self,config,now):
        manuals=self.store.get('manual_controls',{})
        policies={}
        changed=False
        for device in config.devices:
            entry=manuals.get(device.id)
            until=datetime.fromisoformat(entry['until']) if entry and entry.get('until') else None
            if device.kind=='charger' and device.mode=='manual':
                # Migrate old timed car overrides without changing the selected mode.
                if entry and entry.get('until') is not None:
                    entry['until']=None; changed=True
                until=None
            elif device.mode=='manual' and (not until or until<=now):
                device.mode=entry.get('previous_mode','off') if entry else 'off'
                manuals.pop(device.id,None); changed=True
            cloud=device.cloud.model_dump()
            last_command=getattr(self.adapters.get(device.id),'last_command',None)
            policies[device.id]=DevicePolicy(device.id,device.mode,**cloud,
                target=device.default_soc_target if device.kind=='charger' else device.target,
                solar_target=device.solar_target,
                armed=device.armed,vehicle_id=device.vehicle_id,soc_max_age_s=config.peugeot.max_age_s,
                manual_until=until,off_peak=is_off_peak(now,config.off_peak,config.timezone),
                start_not_before=last_command+timedelta(seconds=60)
                    if device.kind=='water_heater' and last_command else None)
        if changed:
            self.store.set('manual_controls',manuals)
            self.store.save_settings(config.model_dump(mode='json'))
        return policies

    def end_manual_on_unplug(self,snapshot,config):
        """Manual ends only on an observed plugged -> unplugged transition of a connected charger."""
        changed=False
        for device in config.devices:
            if device.kind!='charger': continue
            state=snapshot.device_states.get(device.id)
            if not state or not state.connected:
                self.last_plugged.pop(device.id,None); continue
            if self.link_seen.get(device.id)!=state.connected_since:
                self.link_seen[device.id]=state.connected_since; self.last_plugged.pop(device.id,None)
            # Only a StatusNotification received on the current link counts: the value kept across a
            # reconnect, or any value of a charger still flagged as restarted, is doubtful.
            fresh=bool(state.connected_since and state.status_received_at
                       and state.status_received_at>state.connected_since and not state.rebooted)
            plugged=state.vehicle_connected if fresh else None
            if plugged is None: continue
            was=self.last_plugged.get(device.id,False)
            self.last_plugged[device.id]=plugged
            if plugged or not was or device.mode!='manual': continue
            device.mode='planned'
            manuals=self.store.get('manual_controls',{})
            manuals.pop(device.id,None)
            self.store.set('manual_controls',manuals)
            self.store.save_settings(config.model_dump(mode='json'))
            self.engine.forget(device.id)
            self.store.journal.write('INFO','device:'+device.id,'Voiture débranchée : fin du mode Manuel, retour en Auto (Planifié)')
            changed=True
        return changed

    async def tick(self,snapshot=None):
        async with self.lock:
            config=SettingsDocument.model_validate(self.store.load_settings())
            snapshot=snapshot or await self.acquire(config)
            self.charging.update(snapshot,config)
            self.end_manual_on_unplug(snapshot,config)
            # A Peugeot percentage kept through an API error is ignored: the car may have
            # been driven since. Only this session's estimate may still end a charge.
            effective={key:value if value.quality!=Quality.UNAVAILABLE else replace(value,soc=None)
                       for key,value in snapshot.vehicle_telemetry.items()}
            for d in config.devices:
                summary=self.charging.summary(d.id) if d.kind=='charger' else None
                if summary and summary['active'] and d.vehicle_id:
                    raw=effective.get(d.vehicle_id,VehicleTelemetry())
                    effective[d.vehicle_id]=replace(raw,soc=summary['soc'] if summary['soc_known'] else None,
                        measured_at=snapshot.at,received_at=snapshot.at,
                        quality=Quality.ESTIMATED if summary['soc_usable'] else Quality.UNAVAILABLE,
                        unavailable_reason=summary.get('soc_reason'))
            snapshot=replace(snapshot,vehicle_telemetry=effective)
            snapshot=replace(snapshot,reservations=tuple(self.reservations.values()))
            configs={d.id:d for d in config.devices}
            for key in self.dispatcher.reconcile(snapshot,configs):
                self.reservations.pop(key,None);self.errors.pop(key,None)
                if self.dispatcher.records[key]['action']=='suspend':
                    if key in self.engine.network_stop_pending: self.engine.heater_targets.reset(key)
                    self.engine.network_stop_pending.discard(key)
                    self.engine.network_stop_issued.discard(key)
            self.release_charger_reservations(snapshot,configs)
            snapshot=replace(snapshot,reservations=tuple(self.reservations.values()),
                transition_blocked=any(r['status']!='observed' and configs.get(key)
                    and configs[key].kind!='charger' for key,r in self.dispatcher.records.items()))
            policies=self.policies(config,snapshot.at)
            occurrences=[o for p in config.schedules for o in occurrences_for(p,snapshot.at,
                snapshot.at+timedelta(days=8),config.timezone)]
            self.record_schedules(snapshot,occurrences,config)
            authorizations={d.id:select_authorization(d.vehicle_id,snapshot.at,occurrences,d.default_soc_target)
                            for d in config.devices if d.kind=='charger'}
            self.plan_warnings=plan_warnings(snapshot,config,occurrences)
            states=dict(snapshot.device_states)
            for d in config.devices:
                if d.kind=='charger' and d.id in states:
                    _,target=charger_goals(policies[d.id],authorizations[d.id])
                    states[d.id]=replace(states[d.id],target_reached=self.charging.target_reached(d.id,target))
            snapshot=replace(snapshot,device_states=states)
            waiting_manual_stops=set()
            blocked_reasons={}
            for key,record in self.dispatcher.records.items():
                if record['status'] in ('sending','accepted','unknown'):
                    confirmation=datetime.fromisoformat(record.get('confirm_by',record['expires_at'] or record['sent_at']))
                    if record['status']=='unknown' or snapshot.at>confirmation:
                        # Pending physical effects are never retried as new starts.
                        if key in policies: policies[key]=replace(policies[key],mode='off')
                        self.errors[key]='Résultat de commande inconnu : vérification requise'
                        blocked_reasons[key]='Vérification requise : '+command_reason(record)
                    elif record['action']=='suspend' and key in policies:
                        policies[key]=replace(policies[key],mode='off')
                        blocked_reasons[key]='Arrêt en cours : '+command_reason(record)
                        if configs[key].kind=='water_heater' and configs[key].mode=='manual':
                            waiting_manual_stops.add(key)
                    # A stop, or an offer to a car that stays in SuspendedEV (no draw to measure,
                    # possibly no Current.Offered), is confirmed by a status re-read after sending.
                    state=snapshot.device_states.get(key)
                    declined_offer=bool(record['action']=='set_power' and record['status']!='sending'
                        and state and state.observed_state=='SuspendedEV')
                    if ((record['action']=='suspend' or declined_offer)
                            and key in configs and configs[key].kind=='charger'):
                        source=self.adapters.get(key)
                        last=self.stop_status_requests.get(key)
                        if (hasattr(source,'request_status') and (not last or last[0]!=record['id']
                                or snapshot.at.timestamp()-last[1]>=15)):
                            self.stop_status_requests[key]=(record['id'],snapshot.at.timestamp())
                            async def read_status(adapter=source):
                                try:await asyncio.wait_for(adapter.request_status(),10)
                                except (Exception,asyncio.CancelledError):pass
                            task=asyncio.create_task(read_status())
                            self.refresh_tasks.add(task);task.add_done_callback(self.refresh_tasks.discard)
            for key,(queued,_) in self.queued_intents.items():
                if queued.action=='suspend' and key in policies: policies[key]=replace(policies[key],mode='off')
            specs=[DeviceSpec(d.id,d.kind,min_power_w=d.min_power_w,max_power_w=d.max_power_w,
                priority=d.priority,grid_phases=tuple(d.grid_phases),voltage=d.voltage,
                min_current_a=d.min_current_a,max_current_a=d.max_current_a) for d in config.devices]
            faults_before=set(self.engine.charger_limit_faults)
            batch=self.engine.evaluate(snapshot,specs,policies,authorizations)
            self.store.set('charger_limit_faults',sorted(self.engine.charger_limit_faults))
            self.store.set('charger_limit_retry',{key:{'until':value['until'].isoformat(),'attempt':value['attempt']}
                for key,value in self.engine.charger_fault_retry.items()})
            for key in self.engine.charger_limit_faults-faults_before:
                retry=self.engine.charger_fault_retry[key]
                self.store.append_event({'kind':'charger_limit_fault','device_id':key,
                    'details':{'retry_at':retry['until'].isoformat(),'attempt':retry['attempt']}})
            for key in self.engine.charger_limit_faults:
                self.errors[key]='Limite de recharge non appliquée : coupure puis nouvelle tentative automatique'
            for key in faults_before-self.engine.charger_limit_faults:
                if self.errors.get(key,'').startswith('Limite de recharge non appliquée'):
                    self.errors.pop(key)
            if blocked_reasons:
                batch=replace(batch,reasons=batch.reasons|blocked_reasons,
                    commands=tuple(replace(command,reason=blocked_reasons[command.device_id])
                        if command.device_id in blocked_reasons else command for command in batch.commands))
            # Persist a boundary stop before queueing it: a crash cannot turn
            # an expired network authorization into a new cloud grace period.
            self.store.set('runtime_network_state',{'allowed':self.engine.network_allowed,
                'stop_pending':sorted(self.engine.network_stop_pending)})
            if waiting_manual_stops:
                batch=replace(batch,reasons=batch.reasons|{key:
                    'Chauffe demandée : attente de confirmation de l’arrêt précédent'
                    for key in waiting_manual_stops})
            self.reasons=batch.reasons
            self.effective_targets=batch.effective_targets
            self.target_sources=batch.target_sources
            self.authorizations=authorizations
            for reservation in batch.reservations:
                old=self.reservations.get(reservation.device_id)
                if configs[reservation.device_id].kind=='charger':
                    # The latest offer replaces the previous one at the station; its
                    # reservation already covers the measured draw at sending time.
                    self.reservations[reservation.device_id]=reservation
                else:
                    self.reservations[reservation.device_id]=replace(reservation,power_w=max(reservation.power_w,old.power_w if old else 0))
            for intent in batch.commands:
                if not self.enqueue(intent,configs[intent.device_id]) and intent.action=='suspend':
                    self.engine.network_stop_issued.discard(intent.device_id)
            # EVCC caps are persistent. Refresh only legacy finite profiles once,
            # using the recalculated, currently authorized demand.
            for device in config.devices:
                record=self.dispatcher.records.get(device.id)
                if (device.kind=='charger' and device.armed and record
                    and (record['status']=='observed' or record['status']=='accepted'
                         and snapshot.at<datetime.fromisoformat(record['confirm_by']))
                    and record['power_w']>0 and self.engine.requested.get(device.id,0)>0
                    and not record.get('profile_persistent',False)
                    and not any(c.device_id==device.id for c in batch.commands)):
                    self.enqueue(CommandIntent(str(uuid.uuid4()),device.id,'set_power',record['power_w'],
                        snapshot.at+timedelta(seconds=90),'Migration du profil EVCC'),device)
                source=self.adapters.get(device.id)
                if (device.kind=='charger' and device.armed and self.engine.requested.get(device.id,0)>0
                    and hasattr(source,'keep_authorized')):
                    source.keep_authorized(snapshot.at+timedelta(seconds=90))
            self.snapshot=snapshot
            self.store.set('runtime_reservations',{key:{'power_w':r.power_w,'command_id':r.command_id,
                'expires_at':r.expires_at.isoformat()} for key,r in self.reservations.items()})
            self.last_tick=utcnow()
            # Periodic detail every 30 s, and at once when a device decision changes
            # (countdown seconds inside a reason are not a change).
            decisions={key:re.sub(r'\d+','#',value) for key,value in self.reasons.items()}
            if (not self.last_diagnostic or decisions!=self.last_diagnostic_reasons
                    or (snapshot.at-self.last_diagnostic).total_seconds()>=30):
                def reading(sample):
                    return f'{sample.value} {sample.unit}' if sample and sample.value is not None else 'indisponible'
                self.store.journal.write('TRACE','site',f'Réseau={reading(snapshot.grid)} ; solaire={reading(snapshot.solar)}')
                for phase,sample in snapshot.phase_currents.items():
                    self.store.journal.write('TRACE','site',f'{phase} : courant={reading(sample)} ; limite={snapshot.phase_limits_a.get(phase)} A')
                for device in config.devices:
                    state=snapshot.device_states.get(device.id)
                    if state:
                        self.store.journal.write('TRACE','device:'+device.id,f'État={state.observed_state} ; puissance={reading(state.observed_power)} ; décision={self.reasons.get(device.id,"—")}')
                self.last_diagnostic=snapshot.at
                self.last_diagnostic_reasons=decisions
            return batch

    def release_charger_reservations(self,snapshot,configs):
        """End an expired charger reservation once a fresh native state measures the real draw.

        An unconfirmed offer (no Current.Offered, car declining in SuspendedEV) must not hold
        surplus forever. A station still starting (Preparing, SuspendedEVSE) keeps it; heaters
        keep theirs until their slower cloud confirmation.
        """
        for key,reservation in list(self.reservations.items()):
            config=configs.get(key)
            state=snapshot.device_states.get(key)
            power=state.observed_power if state else None
            if (config and config.kind=='charger' and snapshot.at>=reservation.expires_at
                    and state and state.connected and state.observed_state in ('Charging','SuspendedEV','Finishing','Available')
                    and power and power.usable(snapshot.at,snapshot.sample_max_age_s)
                    and power.measured_at>reservation.expires_at-timedelta(seconds=RESERVATION_S)):
                self.reservations.pop(key)

    def record_schedules(self,snapshot,occurrences,config):
        tracked=self.store.get('schedule_results',{})
        for occurrence in occurrences:
            if occurrence.solar_start_at<=snapshot.at and occurrence.id not in tracked:
                tracked[occurrence.id]={'program_id':occurrence.program_id,'vehicle_id':occurrence.vehicle_id,
                    'deadline':occurrence.deadline_at.isoformat(),'target_soc':occurrence.target_soc,'result':'pending'}
        for value in tracked.values():
            if value['result']!='pending' or datetime.fromisoformat(value['deadline'])>snapshot.at: continue
            telemetry=snapshot.vehicle_telemetry.get(value['vehicle_id'])
            complete=bool(telemetry and (telemetry.fresh(snapshot.at,config.peugeot.max_age_s)
                          or telemetry.quality==Quality.ESTIMATED and telemetry.usable(snapshot.at,config.peugeot.max_age_s))
                          and telemetry.soc>=value['target_soc'])
            value['estimated']=bool(telemetry and telemetry.quality==Quality.ESTIMATED)
            value['result']='complete' if complete else 'incomplete'
            self.store.append_event({'kind':'schedule_'+value['result'],'at':snapshot.at.isoformat(),
                'details':{k:v for k,v in value.items() if k!='vehicle_id'}})
        self.store.set('schedule_results',dict(list(tracked.items())[-2000:]))

    def enqueue(self,intent,config):
        if not config.armed or intent.device_id not in self.adapters: return False
        queued=self.queued_intents.get(intent.device_id)
        if queued and queued[0].action=='suspend' and intent.action!='suspend':
            self.engine.forget(intent.device_id);return False
        self.queued_intents[intent.device_id]=(intent,config.mode)
        self.save_queue()
        existing=self.command_tasks.get(intent.device_id)
        if existing and not existing.done(): return True
        async def send():
            while intent.device_id in self.queued_intents:
                command,expected_mode=self.queued_intents.pop(intent.device_id)
                self.save_queue()
                current=SettingsDocument.model_validate(self.store.load_settings())
                device=next((d for d in current.devices if d.id==command.device_id),None)
                if (not device or not device.armed or (command.expires_at and command.expires_at<=utcnow())
                    or (command.action!='suspend' and device.mode!=expected_mode)):
                    self.engine.network_stop_issued.discard(command.device_id)
                    self.engine.forget(command.device_id); continue
                window=max(device.confirmation_timeout_s,
                    2*current.ariston.poll_interval_s+30 if device.kind=='water_heater' else 90)
                if device.kind=='charger' and command.action=='set_power' and command.limit_w:
                    window=max(window,CHARGER_START_WAIT_S)
                result=await self.dispatcher.dispatch(command,self.adapters[command.device_id],window)
                if device.kind=='charger':self.engine.command_result(command,result.accepted,result.checked_at or utcnow())
                if device.kind=='charger' and result.accepted:
                    self.dispatcher.records[command.device_id]['profile_persistent']=True
                    self.dispatcher.save()
                source=self.adapters[command.device_id]
                if device.kind=='water_heater' and result.accepted and hasattr(source,'read_state'):
                    task=asyncio.create_task(self.refresh_after_command(command.device_id,source))
                    self.refresh_tasks.add(task);task.add_done_callback(self.refresh_tasks.discard)
        self.command_tasks[intent.device_id]=asyncio.create_task(send())
        return True

    def save_queue(self):
        self.store.set('queued_intents',{key:{'intent':asdict(intent)|{'expires_at':intent.expires_at.isoformat()
            if intent.expires_at else None},'mode':mode} for key,(intent,mode) in self.queued_intents.items()})

    async def refresh_after_command(self,device_id,source):
        try:
            state=await asyncio.wait_for(source.read_state(),25)
            if self.adapters.get(device_id) is source: self.cache[device_id]=state
        except asyncio.CancelledError: raise
        except Exception:
            if self.adapters.get(device_id) is source:
                self.errors[device_id]='Relecture après commande indisponible'

    def public_state(self):
        config=SettingsDocument.model_validate(self.store.load_settings())
        now=utcnow()
        def sample(value):
            if value is None:return None
            data=asdict(value)
            data['usable']=value.usable(now,config.sample_max_age_s)
            return data
        def device_state(device):
            value=self.snapshot.device_states.get(device.id,DeviceState(device.id))
            target=self.effective_targets.get(device.id,device.target)
            if device.kind=='water_heater' and value.temperature is not None and target is not None:
                value=replace(value,target_reached=value.temperature>=target)
            return asdict(value)|{'observed_power':sample(value.observed_power)}
        return {'simulation':False,'at':self.last_tick,'running':self.running,
            'grid':sample(self.snapshot.grid),'solar':sample(self.snapshot.solar),
            'house':sample(self.snapshot.house),'house_configured':bool(config.home_assistant.house_entity),
            'phase_control_enabled':config.phase_control_enabled,
            'phases':{p:{'current':sample(self.snapshot.phase_currents.get(p)),
                'voltage':sample(self.snapshot.phase_voltages.get(p)),
                'power':sample(self.snapshot.phase_powers.get(p)),
                'limit_a':c.max_current_a} for p,c in config.home_assistant.phases.items()},
            'price':sample(self.snapshot.price),'effective_price_per_kwh':self.charging.effective_price,
            'solar_budget_w':solar_budget_w(replace(self.snapshot,at=now)),
            'energy_prices':{'site':None if self.charging.effective_price is None else round(self.charging.effective_price,3),
                'devices':device_prices(replace(self.snapshot,at=now),config)},
            'off_peak':is_off_peak(now,config.off_peak,config.timezone),'errors':self.errors,
            'devices':[{'config':d.model_dump(mode='json'),
                'state':device_state(d),
                'reason':self.reasons.get(d.id,'En attente de mesures'),
                'effective_target':self.effective_targets.get(d.id,d.target),
                'target_source':self.target_sources.get(d.id,'grid'),
                'plan_warning':self.plan_warnings.get(d.id),
                'charging':self.charging.summary(d.id) if d.kind=='charger' else None,
                'command':self.dispatcher.records.get(d.id),
                'reservation_w':self.reservations[d.id].power_w if d.id in self.reservations else 0,
                'authorization':asdict(self.authorizations[d.id]) if d.id in self.authorizations else None}
                for d in config.devices],
            'vehicles':{key:asdict(value)|{'fresh':value.fresh(now,config.peugeot.max_age_s)}
                        for key,value in self.telemetry.items()}}
