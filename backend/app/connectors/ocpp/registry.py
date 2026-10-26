from dataclasses import replace
from datetime import datetime,timedelta
from ocpp.v16 import call
from app.settings import DeviceConfig
from app.domain.devices import DeviceState,CapabilityReport
from app.domain.commands import CommandResult
from app.domain.measurements import Quality,utcnow
from .profiles import build_profile


class OcppRegistry:
    def __init__(self,store,configs,secret_getter):
        self.store,self.configs,self.secret_getter=store,configs,secret_getter
        self.stations,self.states,self.probes,self.metadata={}, {}, {}, {}
        self.active={}
        self.allowed_until={}
        for key,value in store.get('ocpp_active',{}).items():
            station,connector=key.rsplit(':',1)
            self.active[(station,int(connector))]=value

    def devices(self,station_id=None):
        configs=[d if isinstance(d,DeviceConfig) else DeviceConfig.model_validate(d) for d in self.configs()]
        return [d for d in configs if d.kind=='charger' and (station_id is None or d.charge_point_id==station_id)]

    def config(self,device_id):
        return next((d for d in self.devices() if d.id==device_id),None)

    def state(self,device_id):
        state=self.states.get(device_id,DeviceState(device_id))
        config=self.config(device_id)
        if not config or config.charge_point_id not in self.stations:
            power=replace(state.observed_power,quality=Quality.UNAVAILABLE) if state.observed_power else None
            return replace(state,connected=False,observed_power=power)
        return state

    def authorized(self,config):
        until=self.allowed_until.get(config.id)
        return bool(config.armed and until and until>utcnow())

    def save_transactions(self):
        self.store.set('ocpp_active',{f'{cp}:{connector}':value for (cp,connector),value in self.active.items()})

    def transaction(self,cp,connector,payload):
        key=f'{cp}:{connector}:{payload["timestamp"]}:{payload["meter_start"]}'
        with self.store.lock:
            history=self.store.get('ocpp_transaction_ids',{})
            if key not in history:
                value=self.store.get('ocpp_counter',0)+1
                self.store.set('ocpp_counter',value)
                history[key]=value
                self.store.set('ocpp_transaction_ids',dict(list(history.items())[-2000:]))
            value=history[key]
            self.active[(cp,connector)]={'transaction_id':value,'meter_start':payload['meter_start']}
            self.save_transactions()
        return value


class ChargerAdapter:
    def __init__(self,registry,config):
        self.registry,self.config=registry,config

    async def read_state(self):
        return self.registry.state(self.config.id)

    async def probe_capabilities(self):
        station=self.registry.stations.get(self.config.charge_point_id)
        if not station:
            return CapabilityReport(unsupported=('offline',))
        try:
            result=await station.call(call.GetConfiguration(key=['SupportedFeatureProfiles','MeterValueSampleInterval']))
            settings={row['key']:row.get('value','') for row in result.configuration_key or []}
            smart='SmartCharging' in settings.get('SupportedFeatureProfiles','')
            report=CapabilityReport(('read','start','stop')+(('limit_current',) if smart else ()),
                () if smart else ('limit_current_unverified',),utcnow(),False)
            self.registry.probes[self.config.id]=report
            return report
        except Exception:
            return CapabilityReport(unsupported=('probe_failed',),verified_at=utcnow())

    async def execute(self,intent):
        station=self.registry.stations.get(self.config.charge_point_id)
        if not station:
            return CommandResult(intent.id,False,error='Borne déconnectée',checked_at=utcnow())
        transaction=self.registry.active.get((self.config.charge_point_id,self.config.connector_id))
        try:
            if intent.action=='suspend':
                self.registry.allowed_until.pop(self.config.id,None)
                if not transaction:
                    state=await self.read_state()
                    zero=bool(state.observed_power and state.observed_power.value==0)
                    return CommandResult(intent.id,zero,zero,error=None if zero else 'Transaction inconnue',checked_at=utcnow())
                result=await station.call(call.RemoteStopTransaction(transaction_id=transaction['transaction_id']))
                return CommandResult(intent.id,result.status=='Accepted',False,checked_at=utcnow())
            profile=build_profile(self.config,intent.limit_w,transaction['transaction_id'] if transaction else None,intent.expires_at)
            result=await station.call(call.SetChargingProfile(connector_id=self.config.connector_id,cs_charging_profiles=profile))
            if result.status!='Accepted':
                return CommandResult(intent.id,False,error='Limite de courant refusée',checked_at=utcnow())
            self.registry.allowed_until[self.config.id]=intent.expires_at or utcnow()+timedelta(seconds=90)
            if not transaction:
                result=await station.call(call.RemoteStartTransaction(id_tag='SEM',connector_id=self.config.connector_id))
                if result.status!='Accepted':
                    self.registry.allowed_until.pop(self.config.id,None)
                    return CommandResult(intent.id,False,error='Démarrage refusé',checked_at=utcnow())
            return CommandResult(intent.id,True,False,checked_at=utcnow())
        except Exception:
            return CommandResult(intent.id,False,error='Échange OCPP non confirmé',checked_at=utcnow())
