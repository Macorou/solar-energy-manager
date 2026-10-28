import asyncio
from dataclasses import asdict
from datetime import datetime, timezone,timedelta
from app.domain.commands import CommandResult
from app.domain.measurements import Quality


class Dispatcher:
    def __init__(self,store,timeout_s=25):
        self.store,self.timeout_s=store,timeout_s
        self.records=store.get('runtime_commands',{})
        for record in self.records.values():
            if record['status'] in ('sending','accepted'): record['status']='unknown'
        self.locks={}

    def save(self): self.store.set('runtime_commands',self.records)

    async def dispatch(self,intent,adapter,confirmation_timeout_s=90):
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
                'reason':intent.reason,'status':'sending','target_temperature':intent.target_temperature}
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
                           'target_temperature':intent.target_temperature}})
            return result

    def reconcile(self,snapshot,configs):
        observed=[]
        for key,record in self.records.items():
            if record['status'] in ('observed','sending'): continue
            state=snapshot.device_states.get(key)
            power=state.observed_power if state else None
            if not power or not power.usable(snapshot.at,snapshot.sample_max_age_s): continue
            sent=datetime.fromisoformat(record['sent_at'])
            desired=record['power_w']
            config=configs.get(key)
            heater_stop=bool(config and config.kind=='water_heater' and not desired
                and record['action']=='suspend')
            native_stop=bool(heater_stop and state.connected and not state.fault
                and state.observed_state=='off' and state.measured_at
                and sent<state.measured_at<=snapshot.at
                and (snapshot.at-state.measured_at).total_seconds()<=snapshot.sample_max_age_s
                and power.checked_at and power.checked_at>sent and 0<=power.value<=20)
            charger_stop=bool(config and config.kind=='charger' and not desired and record['action']=='suspend')
            native_charger_stop=bool(charger_stop and state.connected and not state.fault
                and state.transaction_active is False and state.start_pending is False
                and state.observed_state in ('Available','Preparing','SuspendedEV','SuspendedEVSE','Finishing')
                and state.status_measured_at and sent<state.status_measured_at<=snapshot.at
                and (snapshot.at-state.status_measured_at).total_seconds()<=snapshot.sample_max_age_s
                and power.quality==Quality.FRESH and power.checked_at
                and state.status_measured_at<=power.checked_at and power.checked_at>sent and 0<=power.value<=20)
            grid=snapshot.grid
            if not grid or not grid.usable(snapshot.at,snapshot.sample_max_age_s): continue
            if (grid.availability_at<power.availability_at or grid.availability_at<power.measured_at
                or (grid.availability_at-power.availability_at).total_seconds()>2): continue
            if heater_stop:
                # A fresh native OFF read plus checked idle HA power can confirm
                # an unchanged zero; this never confirms the effect of a start.
                if not native_stop: continue
            elif charger_stop and power.measured_at<=sent:
                if not native_charger_stop:continue
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
                matched=matched and state.target_temperature==target and state.observed_state=='on'
            if matched:
                record['status']='observed'; observed.append(key)
                self.store.append_event({'kind':'command_observed','device_id':key,
                    'details':{'power_w':power.value,'action':record['action']}})
        if observed: self.save()
        return observed
