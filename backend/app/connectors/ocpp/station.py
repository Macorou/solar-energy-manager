from dataclasses import replace
from datetime import datetime
import math
from ocpp.routing import on
from ocpp.v16 import ChargePoint,call_result
from ocpp.v16.enums import Action
from app.domain.devices import DeviceState
from app.domain.measurements import Sample,Quality,utcnow
from .readings import apply_readings


class Station(ChargePoint):
    def __init__(self,station_id,connection,registry):
        super().__init__(station_id,connection,response_timeout=15)
        self.registry=registry

    def config(self,connector_id):
        return next((d for d in self.registry.devices(self.id) if d.connector_id==connector_id),None)

    def meter_identity(self,state,transaction):
        if not transaction or state.energy_transaction_id==transaction['transaction_id']: return state
        try:
            stamp=datetime.fromisoformat(transaction.get('timestamp','').replace('Z','+00:00'))
            if not stamp.tzinfo:stamp=None
        except (ValueError,TypeError,AttributeError):stamp=None
        return replace(state,energy_transaction_id=transaction['transaction_id'],
            energy_transaction_start_wh=transaction.get('meter_start'),energy_transaction_started_at=stamp)

    @on(Action.boot_notification)
    def boot(self,charge_point_vendor,charge_point_model,**kwargs):
        previous=self.registry.metadata.get(self.id,{})
        firmware=kwargs.get('firmware_version')
        if not firmware and (previous.get('vendor'),previous.get('model'))==(charge_point_vendor,charge_point_model):
            firmware=previous.get('firmware')
        self.registry.metadata[self.id]={'vendor':charge_point_vendor,'model':charge_point_model,
            'firmware':firmware}
        self.registry.store.set('ocpp_metadata',self.registry.metadata)
        if hasattr(self,'sem_profile_values'):del self.sem_profile_values
        self.registry.rebooted.update(config.id for config in self.registry.devices(self.id))
        return call_result.BootNotification(current_time=utcnow().isoformat(),interval=30,status='Accepted')

    @on(Action.heartbeat)
    def heartbeat(self):
        return call_result.Heartbeat(current_time=utcnow().isoformat())

    @on(Action.authorize)
    def authorize(self,id_tag):
        accepted=any(self.registry.authorized(d) for d in self.registry.devices(self.id))
        return call_result.Authorize(id_tag_info={'status':'Accepted' if accepted else 'Blocked'})

    @on(Action.status_notification)
    def status(self,connector_id,error_code,status,**kwargs):
        config=self.config(connector_id)
        if config:
            old=self.registry.states.get(config.id,DeviceState(config.id))
            received=utcnow();stamp=received
            if kwargs.get('timestamp'):
                try:
                    stamp=datetime.fromisoformat(kwargs['timestamp'].replace('Z','+00:00'))
                    if not stamp.tzinfo or stamp>utcnow():return call_result.StatusNotification()
                    if old.status_measured_at and stamp<old.status_measured_at:return call_result.StatusNotification()
                except (ValueError,TypeError,AttributeError):return call_result.StatusNotification()
            if status=='Available' or config.id in self.registry.rebooted and status=='Preparing':
                self.registry.active.pop((self.id,connector_id),None)
                self.registry.save_transactions()
            if status in ('Available','Preparing','Charging','SuspendedEV','SuspendedEVSE','Finishing'):
                self.registry.rebooted.discard(config.id)
            power=old.observed_power
            if status in ('Available','SuspendedEV','SuspendedEVSE','Finishing'):
                power=Sample(0,'W','OCPP état '+status,stamp,received,Quality.ESTIMATED,checked_at=received)
            if status=='Available':
                if not self.registry.authorized(config) and (self.id,connector_id) not in self.registry.active:
                    self.registry.pending_start.pop(config.id,None);self.registry.save_pending()
            self.registry.states[config.id]=replace(old,connected=True,observed_state=status,
                fault=None if error_code=='NoError' and status!='Faulted' else error_code,
                observed_power=power,vehicle_connected=False if status=='Available' else
                    True if status in ('Preparing','Charging','SuspendedEV','SuspendedEVSE','Finishing') else None,
                measured_at=stamp,status_measured_at=stamp,status_received_at=received)
        return call_result.StatusNotification()

    @on(Action.start_transaction)
    def start_transaction(self,connector_id,id_tag,meter_start,timestamp,**kwargs):
        config=self.config(connector_id)
        if not config:
            return call_result.StartTransaction(transaction_id=0,id_tag_info={'status':'Invalid'})
        transaction=self.registry.transaction(self.id,connector_id,{'timestamp':timestamp,'meter_start':meter_start})
        self.registry.rebooted.discard(config.id)
        pending=self.registry.pending_start.pop(config.id,None);self.registry.save_pending()
        cancelled=bool(pending and pending['state']=='cancel_requested') or not self.registry.authorized(config)
        if cancelled and self.registry.on_transaction: self.registry.on_transaction(config.id)
        old=self.registry.states.get(config.id,DeviceState(config.id))
        try:
            stamp=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
            if stamp.tzinfo and math.isfinite(meter_start) and meter_start>=0 and (not old.energy_measured_at or stamp>=old.energy_measured_at):
                old=replace(old,energy_wh=float(meter_start),energy_measured_at=stamp,energy_terminal=False,
                    energy_transaction_id=transaction,energy_transaction_start_wh=float(meter_start),
                    energy_transaction_started_at=stamp)
        except (ValueError,TypeError,AttributeError): pass
        self.registry.states[config.id]=replace(old,connected=True,vehicle_connected=True,observed_state='Preparing',status_measured_at=utcnow())
        return call_result.StartTransaction(transaction_id=transaction,
            id_tag_info={'status':'Accepted' if self.registry.authorized(config) else 'Invalid'})

    @on(Action.stop_transaction)
    def stop_transaction(self,meter_stop,timestamp,transaction_id,**kwargs):
        # Some stations announce Available before sending their final counter.
        # That removes the active transaction for control purposes, but the
        # matching, still unplugged meter identity can accept a terminal value.
        # Never apply it to a new plug/transaction or regress Available to Finishing.
        for config in self.registry.devices(self.id):
            old=self.registry.states.get(config.id)
            if (old and old.vehicle_connected is False and old.energy_transaction_id==transaction_id
                and (self.id,config.connector_id) not in self.registry.active):
                try:
                    stamp=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
                    if (stamp.tzinfo and stamp<=utcnow() and math.isfinite(meter_stop) and meter_stop>=0
                        and (not old.energy_measured_at or stamp>=old.energy_measured_at)):
                        self.registry.states[config.id]=replace(old,energy_wh=float(meter_stop),
                            energy_measured_at=stamp,energy_terminal=True)
                except (ValueError,TypeError,AttributeError):pass
        for key,value in list(self.registry.active.items()):
            if key[0]==self.id and value['transaction_id']==transaction_id:
                config=self.config(key[1])
                if config:
                    self.registry.pending_start.pop(config.id,None);self.registry.save_pending()
                    old=self.registry.states.get(config.id,DeviceState(config.id))
                    old=self.meter_identity(old,value)
                    try:
                        stamp=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
                        if stamp.tzinfo and math.isfinite(meter_stop) and meter_stop>=0 and (not old.energy_measured_at or stamp>=old.energy_measured_at):
                            old=replace(old,energy_wh=float(meter_stop),energy_measured_at=stamp,energy_terminal=True)
                    except (ValueError,TypeError,AttributeError): pass
                    received=utcnow()
                    self.registry.states[config.id]=replace(old,observed_state='Finishing',status_measured_at=received,
                        status_received_at=received,
                        observed_power=Sample(0,'W','OCPP fin de transaction',received,received,Quality.ESTIMATED,checked_at=received))
                del self.registry.active[key]
        self.registry.save_transactions()
        return call_result.StopTransaction(id_tag_info={'status':'Accepted'})

    @on(Action.meter_values)
    def meter_values(self,connector_id,meter_value,**kwargs):
        config=self.config(connector_id)
        if config:
            active=self.registry.active.get((self.id,connector_id))
            reported=kwargs.get('transaction_id')
            if active and reported is not None and reported!=active['transaction_id']:
                return call_result.MeterValues()
            old=self.registry.states.get(config.id,DeviceState(config.id))
            if (not active and isinstance(reported,int) and reported>0
                and old.observed_state in ('Charging','SuspendedEV','SuspendedEVSE')):
                active={'transaction_id':reported,'meter_start':None,'timestamp':None}
                self.registry.active[(self.id,connector_id)]=active
                self.registry.store.set('ocpp_counter',max(reported,self.registry.store.get('ocpp_counter',0)))
                self.registry.save_transactions()
            old=self.meter_identity(old,active)
            self.registry.states[config.id]=apply_readings(self.registry,config,old,meter_value)
        return call_result.MeterValues()
