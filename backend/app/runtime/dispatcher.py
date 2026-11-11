import asyncio
from dataclasses import asdict
from datetime import datetime, timezone,timedelta
from app.domain.commands import CommandResult
from app.domain.measurements import Quality


class Dispatcher:
    def __init__(self,store,timeout_s=25):
        self.store,self.timeout_s=store,timeout_s
        self.records=store.get('runtime_commands',{})
        kinds={item['id']:item['kind'] for item in (store.load_settings() or {}).get('devices',[])}
        for key,record in self.records.items():
            if record['status']=='sending' or record['status']=='accepted' and kinds.get(key)!='charger':
                record['status']='unknown'
        self.locks={}

    def save(self): self.store.set('runtime_commands',self.records)

    async def dispatch(self,intent,adapter,confirmation_timeout_s=90,power_before_w=None):
        async with self.locks.setdefault(intent.device_id,asyncio.Lock()):
            prior=self.records.get(intent.device_id)
            if prior and prior['id']==intent.id:
                return CommandResult(intent.id,prior['status'] in ('accepted','observed'),
                                     prior['status']=='observed',error='already_dispatched')
            now=datetime.now(timezone.utc)
            record={'id':intent.id,'device_id':intent.device_id,'action':intent.action,
                'power_w':intent.limit_w or 0,'sent_at':now.isoformat(),
                'expires_at':intent.expires_at.isoformat() if intent.expires_at else None,
                'confirm_by':(now+timedelta(seconds=confirmation_timeout_s)).isoformat(),
                'reason':intent.reason,'status':'sending','target_temperature':intent.target_temperature,
                'power_before_w':power_before_w}
            renewal=bool(prior and prior['status'] in ('accepted','observed')
                and intent.reason in ('Renouvellement du profil autorisé','Migration du profil EVCC')
                and intent.action==prior['action']=='set_power' and intent.limit_w
                and intent.limit_w==prior['power_w'])
            if renewal:
                record['effect_since']=prior.get('effect_since',prior['sent_at'])
                if prior['status']=='accepted':
                    record['confirm_by']=prior.get('confirm_by') or (
                        datetime.fromisoformat(record['effect_since'])+timedelta(seconds=confirmation_timeout_s)).isoformat()
            if (prior and prior['status']=='accepted' and prior['action']==intent.action=='suspend'):
                record['effect_since']=prior.get('effect_since',prior['sent_at'])
                record['confirm_by']=prior.get('confirm_by',record['confirm_by'])
            self.records[intent.device_id]=record
            self.save()  # Durable before the network side effect.
            try:
                result=await asyncio.wait_for(adapter.execute(intent),self.timeout_s)
                record['status']='accepted' if result.accepted else 'unknown'
                record['error']=result.error
            except asyncio.CancelledError:
                record['status']='unknown'; self.save(); raise
            except Exception:
                record['status']='unknown'
                result=CommandResult(intent.id,False,error='command_result_unknown')
            self.save()
            self.store.append_event({'kind':'command_'+record['status'],'device_id':intent.device_id,
                'details':{'action':intent.action,'power_w':intent.limit_w,'reason':intent.reason,
                           'target_temperature':intent.target_temperature,'error':result.error}})
            return result

    @staticmethod
    def station_confirms_offer(snapshot,state,power,config,desired,sent):
        offered=state.offered_current
        limit=desired/(config.voltage*config.phases)
        verified=bool(offered and offered.usable(snapshot.at,snapshot.sample_max_age_s)
            and offered.availability_at>sent and config.min_current_a<=offered.value<=limit+.23)
        waiting=bool(state.observed_state=='SuspendedEV' and state.status_measured_at
            and sent<state.status_measured_at<=snapshot.at and state.connected and not state.fault)
        drawing=bool(power.source.startswith('OCPP') and power.measured_at>sent
            and 20<power.value<=desired+max(100,desired*.1))
        return verified or waiting or drawing

    def reconcile(self,snapshot,configs):
        observed=[]
        for key,record in self.records.items():
            if record['status'] in ('observed','sending'): continue
            state=snapshot.device_states.get(key)
            power=state.observed_power if state else None
            if not power or not power.usable(snapshot.at,snapshot.sample_max_age_s): continue
            sent=datetime.fromisoformat(record.get('effect_since',record['sent_at']))
            desired=record['power_w']
            config=configs.get(key)
            heater_stop=bool(config and config.kind=='water_heater' and not desired
                and record['action']=='suspend')
            native_stop=bool(heater_stop and state.connected and not state.fault
                and state.observed_state=='off' and state.measured_at
                and sent<state.measured_at<=snapshot.at
                and (snapshot.at-state.measured_at).total_seconds()<=snapshot.sample_max_age_s
                and power.checked_at and power.checked_at>sent and 0<=power.value<=20)
            # The dedicated meter shows the effect long before the cloud read: a drop to
            # zero of a heater that was heating when the stop was sent, or a draw appearing
            # on an idle one. An unchanged zero still needs the native OFF read.
            before=record.get('power_before_w')
            meter_ok=bool(state.connected and not state.fault and power.measured_at>sent
                and power.checked_at and power.checked_at>sent)
            meter_stop=bool(heater_stop and meter_ok and before is not None and before>20 and 0<=power.value<=20)
            meter_start=bool(config and config.kind=='water_heater' and desired and record['action']=='set_power'
                and meter_ok and before is not None and before<=20)
            charger_stop=bool(config and config.kind=='charger' and not desired and record['action']=='suspend')
            status_seen=state.status_received_at or state.status_measured_at
            native_charger_stop=bool(charger_stop and state.connected and not state.fault
                and (state.observed_state=='SuspendedEVSE' or state.transaction_active is False)
                and state.start_pending is False
                and state.observed_state in ('Available','Preparing','SuspendedEV','SuspendedEVSE','Finishing')
                and state.status_measured_at and state.status_measured_at<=snapshot.at
                and status_seen and sent<status_seen<=snapshot.at
                and (snapshot.at-status_seen).total_seconds()<=snapshot.sample_max_age_s
                and (power.quality==Quality.FRESH or power.source.startswith('OCPP')) and power.checked_at
                and status_seen<=power.checked_at and power.checked_at>sent and 0<=power.value<=20)
            if native_charger_stop:
                # A fresh native idle state and checked zero prove a stop without
                # requiring the separate house/grid meter to be available.
                record['status']='observed';observed.append(key)
                self.store.append_event({'kind':'command_observed','device_id':key,
                    'details':{'power_w':power.value,'action':record['action']}})
                continue
            grid=snapshot.grid
            if not grid or not grid.usable(snapshot.at,snapshot.sample_max_age_s):
                # Without the site meter (fallback current), the station's own evidence
                # still confirms an offer: reported offer, declining car or OCPP power.
                if (config and config.kind=='charger' and desired and record['action']=='set_power'
                        and self.station_confirms_offer(snapshot,state,power,config,desired,sent)):
                    record['status']='observed';observed.append(key)
                    self.store.append_event({'kind':'command_observed','device_id':key,
                        'details':{'action':record['action'],'effect':'station_evidence'}})
                continue
            checked=bool(grid.checked_at and power.checked_at)
            if config and config.kind=='water_heater':
                if (grid.availability_at<power.availability_at or grid.availability_at<power.measured_at
                    or (grid.availability_at-power.availability_at).total_seconds()>2):continue
            elif not checked and abs((grid.availability_at-power.availability_at).total_seconds())>2:continue
            if heater_stop:
                # A fresh native OFF read plus checked idle HA power can confirm
                # an unchanged zero; this never confirms the effect of a start.
                if not (native_stop or meter_stop): continue
            elif charger_stop:
                if not native_charger_stop:continue
            elif config and config.kind=='charger' and desired:
                offered=state.offered_current
                limit=desired/(config.voltage*config.phases)
                verified=bool(offered and offered.usable(snapshot.at,snapshot.sample_max_age_s)
                    and offered.availability_at>sent and config.min_current_a<=offered.value<=limit+.23)
                waiting=bool(state.observed_state=='SuspendedEV' and state.status_measured_at
                    and sent<state.status_measured_at<=snapshot.at and state.connected and not state.fault)
                if verified or waiting:
                    record['status']='observed';observed.append(key)
                    self.store.append_event({'kind':'command_observed','device_id':key,
                        'details':{'action':record['action'],'effect':'authorization_verified'}})
                    continue
                if power.measured_at<=sent:continue
            elif config and config.kind=='water_heater' and record['action']=='set_temperature':
                if not (state.connected and not state.fault and state.measured_at
                    and sent<state.measured_at<=snapshot.at
                    and (snapshot.at-state.measured_at).total_seconds()<=snapshot.sample_max_age_s
                    and power.checked_at and power.checked_at>sent): continue
            elif power.measured_at<=sent: continue
            matched=(power.value<=20 if not desired else 20<power.value<=desired+max(100,desired*.1))
            target=record.get('target_temperature')
            if target is None and config: target=config.target
            if desired and config and config.kind=='water_heater' and target is not None:
                matched=matched and state.target_temperature==target and (state.observed_state=='on' or meter_start)
            if matched:
                record['status']='observed'; observed.append(key)
                details={'power_w':power.value,'action':record['action']}
                if (meter_stop and not native_stop) or (meter_start and state.observed_state!='on'):
                    record['effect']=details['effect']='power';record['observed_at']=snapshot.at.isoformat()
                self.store.append_event({'kind':'command_observed','device_id':key,'details':details})
        if observed: self.save()
        return observed

    def redrawn_heaters(self,snapshot,configs):
        """Heaters drawing again after a stop confirmed by the meter alone.

        Such a drop can coincide with the thermostat while the heater stays on: its
        stop must then be sent again.
        """
        keys=[]
        for key,record in self.records.items():
            config=configs.get(key)
            if not (config and config.kind=='water_heater' and record['action']=='suspend'
                    and record['status']=='observed' and record.get('effect')=='power'
                    and record.get('observed_at') and not record.get('redrawn')):continue
            state=snapshot.device_states.get(key)
            power=state.observed_power if state else None
            if (power and power.usable(snapshot.at,snapshot.sample_max_age_s) and power.value>20
                    and power.measured_at>datetime.fromisoformat(record['observed_at'])):
                record['redrawn']=True;keys.append(key)
        if keys:self.save()
        return keys
