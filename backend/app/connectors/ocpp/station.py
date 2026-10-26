from dataclasses import replace
from datetime import datetime
import math
from ocpp.routing import on
from ocpp.v16 import ChargePoint,call_result
from ocpp.v16.enums import Action
from app.domain.devices import DeviceState
from app.domain.measurements import Sample,Quality,utcnow


class Station(ChargePoint):
    def __init__(self,station_id,connection,registry):
        super().__init__(station_id,connection,response_timeout=15)
        self.registry=registry

    def config(self,connector_id):
        return next((d for d in self.registry.devices(self.id) if d.connector_id==connector_id),None)

    @on(Action.boot_notification)
    def boot(self,charge_point_vendor,charge_point_model,**kwargs):
        self.registry.metadata[self.id]={'vendor':charge_point_vendor,'model':charge_point_model,
            'firmware':kwargs.get('firmware_version')}
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
            power=old.observed_power
            if status=='Available':
                power=Sample(0,'W','OCPP état Available',utcnow(),utcnow(),Quality.ESTIMATED)
            self.registry.states[config.id]=replace(old,connected=True,observed_state=status,
                fault=None if error_code=='NoError' and status!='Faulted' else error_code,
                observed_power=power,vehicle_connected=status not in ('Available','Unavailable'),measured_at=utcnow())
        return call_result.StatusNotification()

    @on(Action.start_transaction)
    def start_transaction(self,connector_id,id_tag,meter_start,timestamp,**kwargs):
        config=self.config(connector_id)
        if not config:
            return call_result.StartTransaction(transaction_id=0,id_tag_info={'status':'Invalid'})
        transaction=self.registry.transaction(self.id,connector_id,{'timestamp':timestamp,'meter_start':meter_start})
        old=self.registry.states.get(config.id,DeviceState(config.id))
        self.registry.states[config.id]=replace(old,connected=True,vehicle_connected=True,observed_state='Charging')
        return call_result.StartTransaction(transaction_id=transaction,
            id_tag_info={'status':'Accepted' if self.registry.authorized(config) else 'Invalid'})

    @on(Action.stop_transaction)
    def stop_transaction(self,meter_stop,timestamp,transaction_id,**kwargs):
        for key,value in list(self.registry.active.items()):
            if key[0]==self.id and value['transaction_id']==transaction_id:
                config=self.config(key[1])
                if config:
                    old=self.registry.states.get(config.id,DeviceState(config.id))
                    self.registry.states[config.id]=replace(old,observed_state='Finishing',
                        observed_power=Sample(0,'W','OCPP fin de transaction',utcnow(),utcnow(),Quality.ESTIMATED))
                del self.registry.active[key]
        self.registry.save_transactions()
        return call_result.StopTransaction(id_tag_info={'status':'Accepted'})

    @on(Action.meter_values)
    def meter_values(self,connector_id,meter_value,**kwargs):
        config=self.config(connector_id)
        if config:
            old=self.registry.states.get(config.id,DeviceState(config.id))
            for meter in meter_value:
                try:
                    stamp=datetime.fromisoformat(meter['timestamp'].replace('Z','+00:00'))
                    if not stamp.tzinfo:
                        continue
                    values=meter.get('sampled_value',[])
                    power_values=[]
                    total=None
                    energy=old.energy_wh
                    for sample in values:
                        value=float(sample['value'])
                        if not math.isfinite(value) or value<0:
                            continue
                        measurand=sample.get('measurand','Energy.Active.Import.Register')
                        unit=sample.get('unit','Wh')
                        if measurand=='Power.Active.Import' and unit in ('W','kW'):
                            watts=value*(1000 if unit=='kW' else 1)
                            if sample.get('phase'):
                                power_values.append(watts)
                            else:
                                total=watts
                        if measurand=='Energy.Active.Import.Register' and unit in ('Wh','kWh'):
                            energy=value*(1000 if unit=='kWh' else 1)
                    if total is None and power_values:
                        total=sum(power_values)
                    if total is not None and (not old.observed_power or not old.observed_power.measured_at
                            or stamp>=old.observed_power.measured_at):
                        old=replace(old,observed_power=Sample(total,'W',f'OCPP {config.id}',stamp,utcnow()),
                            connected=True,energy_wh=energy,measured_at=stamp)
                except (ValueError,KeyError,TypeError):
                    continue
            self.registry.states[config.id]=old
        return call_result.MeterValues()
