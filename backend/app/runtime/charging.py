"""Persistent plug-session counters and an explicitly estimated SOC/energy mix.

Meter deltas are measured. Their allocation between contexts is time-weighted,
assuming uniform delivery inside each meter interval; it is never a billing meter.
"""
import math
import uuid
from datetime import datetime, timezone


def finite(value):
    return isinstance(value,(int,float)) and math.isfinite(value)


def energy_at(points,stamp):
    if not points: return None
    if stamp<=points[0][0]: return points[0][1]
    for (a,ea),(b,eb) in zip(points,points[1:]):
        if a<=stamp<=b: return ea+(eb-ea)*(stamp-a)/(b-a) if b>a else eb
    return points[-1][1]


def mix_context(snapshot,solar_price):
    def value(sample):
        return sample.value if sample and sample.usable(snapshot.at,snapshot.sample_max_age_s) else None
    grid,solar,price=value(snapshot.grid),value(snapshot.solar),value(snapshot.price)
    fraction=None
    if grid is not None and solar is not None and solar>=0:
        used=max(0,solar-max(0,-grid)); imported=max(0,grid)
        scale=max(used,imported)
        if scale>0: fraction=(imported/scale)/(used/scale+imported/scale)
    effective=(fraction*(price or 0)+(1-fraction)*solar_price
               if fraction is not None and (price is not None or fraction==0) else None)
    return fraction,price,effective if finite(effective) else None


class ChargingTracker:
    def __init__(self,store):
        self.store=store
        self.sessions=store.get('charging_sessions',{})
        self.effective_price=None

    def update(self,snapshot,config):
        now=snapshot.at.timestamp(); vehicles={v.id:v for v in config.vehicles}
        fraction,price,self.effective_price=mix_context(snapshot,config.solar_price_per_kwh)
        for device in config.devices:
            if device.kind!='charger': continue
            state=snapshot.device_states.get(device.id)
            if not state: continue
            vehicle=vehicles.get(device.vehicle_id)
            identity=(device.vehicle_id,vehicle.vin if vehicle else '')
            session=self.sessions.get(device.id)
            attached=state.connected and state.vehicle_connected is True
            if attached and (not session or not session['active'] or tuple(session['vehicle'])!=identity):
                session={'id':str(uuid.uuid4()),'vehicle':list(identity),'active':True,'started_at':now,
                    'ended_at':None,'energy_wh':0.,'cost_eur':0.,'priced_wh':0.,'solar_wh':0.,'allocated_wh':0.,
                    'last_meter':None,'last_at':None,'points':[],'contexts':[],'anchor':None,
                    'meter_partial':False,'soc_gap_at':None,'soc':None,'soc_usable':False,
                    'soc_estimated':False,'reached_target':None,'reached_at':None}
                self.sessions[device.id]=session
            if not session: continue
            # Do not feed a completed session with a different vehicle's measurements.
            if tuple(session['vehicle'])!=identity: continue
            if session['active']:
                session['checked_at']=now
                contexts=session['contexts']; entry=[now,fraction,price,config.solar_price_per_kwh]
                if not contexts or now-contexts[-1][0]>=10 or price!=contexts[-1][2]:
                    contexts.append(entry)
                session['contexts']=contexts[-8192:]
                raw,stamp=state.energy_wh,state.energy_measured_at
                when=stamp.timestamp() if stamp and stamp.tzinfo else None
                if finite(raw) and raw>=0 and when is not None and when<=now:
                    if session['last_at'] is None:
                        if now-when<=max(90,config.sample_max_age_s):
                            session['last_meter']=raw;session['last_at']=when
                            session['points']=[[when,0.]]
                    elif when>session['last_at']:
                        delta=raw-session['last_meter']
                        plausible=(not device.max_power_w or
                            delta<=device.max_power_w*(when-session['last_at'])/3600*1.5+50)
                        if delta<0 or not plausible or not finite(session['energy_wh']+delta):
                            session['meter_partial']=True
                            session['soc_gap_at']=when
                        else:
                            self.allocate(session,delta,session['last_at'],when,config.sample_max_age_s)
                            session['energy_wh']+=delta
                        session['last_meter']=raw;session['last_at']=when
                        session['points'].append([when,session['energy_wh']])
                        session['points']=session['points'][-4096:]
                self.soc(session,snapshot,config,device,state,vehicle)
                if state.connected and state.vehicle_connected is False:
                    session['active']=False;session['ended_at']=now
            # Disconnection of the controller never closes a plug session.
        self.store.set('charging_sessions',self.sessions)

    def allocate(self,session,delta,start,end,max_age):
        if delta<=0 or end<=start: return
        contexts=session['contexts']
        edges=sorted({start,end}|{v[0] for v in contexts if start<v[0]<end})
        for a,b in zip(edges,edges[1:]):
            eligible=[v for v in contexts if v[0]<=a]
            context=eligible[-1] if eligible else None
            if not context or b-context[0]>max(90,max_age): continue
            _,fraction,price,solar_price=context
            energy=delta*(b-a)/(end-start)
            if fraction is not None:
                session['allocated_wh']+=energy
                session['solar_wh']+=energy*(1-fraction)
                if price is not None or fraction==0:
                    cost=energy/1000*(fraction*(price or 0)+(1-fraction)*solar_price)
                    if finite(cost) and finite(session['cost_eur']+cost):
                        session['cost_eur']+=cost
                        session['priced_wh']+=energy

    def soc(self,session,snapshot,config,device,state,vehicle):
        raw=snapshot.vehicle_telemetry.get(device.vehicle_id)
        now=snapshot.at.timestamp()
        if raw and raw.usable(snapshot.at,config.peugeot.max_age_s):
            stamp=raw.measured_at.timestamp()
            if not session['anchor'] or stamp>session['anchor']['at']:
                session['anchor']={'soc':raw.soc,'at':stamp,'energy':None}
                # Real later measurements override the estimate, with 1% hysteresis.
                if (session['reached_target'] is not None and session.get('reached_at') is not None
                    and stamp>session['reached_at'] and raw.soc<session['reached_target']-1):
                    session['reached_target']=None;session['reached_at']=None
        anchor=session['anchor']; session['soc_usable']=False
        idle=state.observed_state in ('Available','Preparing','SuspendedEV','SuspendedEVSE','Finishing')
        if anchor and vehicle and vehicle.capacity_kwh and session['points']:
            base=anchor.get('energy')
            if base is None:
                base=energy_at(session['points'],anchor['at'])
                if anchor['at']<=session['points'][-1][0]: anchor['energy']=base
            gain=max(0,session['energy_wh']-base)
            session['soc']=min(100,max(0,anchor['soc']+100*gain*vehicle.efficiency/(vehicle.capacity_kwh*1000)))
            session['soc_estimated']=gain>0 or not raw or not raw.fresh(snapshot.at,config.peugeot.max_age_s)
            session['soc_usable']=bool(state.connected and (session.get('soc_gap_at') is None or
                anchor['at']>=session['soc_gap_at']) and
                (idle or (session['last_at'] is not None and now-session['last_at']<=max(90,config.sample_max_age_s))))
        elif (raw and raw.fresh(snapshot.at,config.peugeot.max_age_s)
              and (idle or now-session['started_at']<=90)):
            session['soc']=raw.soc;session['soc_estimated']=False;session['soc_usable']=True

    def target_reached(self,device_id,target):
        session=self.sessions.get(device_id)
        if not session or not session['active']: return False
        reached=session['reached_target']
        if reached is not None and target>reached:
            session['reached_target']=None;reached=None
        if session['soc_usable'] and session['soc'] is not None and session['soc']>=target:
            session['reached_target']=target;reached=target
            session['reached_at']=session.get('reached_at') or session['checked_at']
        self.store.set('charging_sessions',self.sessions)
        return reached is not None and target<=reached

    def summary(self,device_id):
        session=self.sessions.get(device_id)
        if not session:return None
        energy=session['energy_wh']
        return {'id':session['id'],'active':session['active'],
            'ended_at':datetime.fromtimestamp(session['ended_at'],timezone.utc).isoformat() if session['ended_at'] else None,
            'energy_kwh':energy/1000,'energy_partial':session['meter_partial'],
            'cost_eur':session['cost_eur'] if session['priced_wh']>0 or energy==0 else None,
            'cost_partial':session['priced_wh']+1e-6<energy,
            'solar_percent':100*session['solar_wh']/energy if energy>0 and session['allocated_wh']+1e-6>=energy else None,
            'average_price_per_kwh':session['cost_eur']/(energy/1000) if energy>0 and session['priced_wh']+1e-6>=energy else None,
            'effective_price_per_kwh':self.effective_price,
            'soc':session['soc'],'soc_estimated':session['soc_estimated'],'soc_usable':session['soc_usable'],
            'soc_reference_at':datetime.fromtimestamp(session['anchor']['at'],timezone.utc).isoformat() if session['anchor'] else None}
