"""Persistent plug-session counters and an explicitly estimated SOC/energy mix.

Meter deltas are measured. Their allocation between contexts is time-weighted,
assuming uniform delivery inside each meter interval; it is never a billing meter.
"""
import math
import uuid
from datetime import datetime, timezone
from app.domain.measurements import Quality


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
        self.peugeot_references=store.get('peugeot_soc_references',{})
        # Migrate references from older releases without reusing estimated gains.
        for session in self.sessions.values():
            anchor=session.get('anchor')
            if anchor and anchor.get('source','vehicle')=='vehicle':
                self.remember_peugeot(*session['vehicle'],anchor['soc'],anchor['at'])
        self.effective_price=None

    def remember_peugeot(self,vehicle_id,vin,soc,stamp):
        if not vehicle_id or not finite(soc) or not 0<=soc<=100 or not finite(stamp): return
        key=vehicle_id+'|'+vin
        previous=self.peugeot_references.get(key)
        if not previous or stamp>previous['at']:
            self.peugeot_references[key]={'soc':soc,'at':stamp}

    def update(self,snapshot,config):
        now=snapshot.at.timestamp(); vehicles={v.id:v for v in config.vehicles}
        # Keep the latest constructor reference even outside a plug session.
        for vehicle in config.vehicles:
            raw=snapshot.vehicle_telemetry.get(vehicle.id)
            if (raw and finite(raw.soc) and 0<=raw.soc<=100
                and raw.measured_at and raw.measured_at.tzinfo and raw.measured_at<=snapshot.at
                and raw.quality!=Quality.ESTIMATED):
                self.remember_peugeot(vehicle.id,vehicle.vin,raw.soc,raw.measured_at.timestamp())
        self.store.set('peugeot_soc_references',self.peugeot_references)
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
                    'meter_partial':False,'terminal_pending':False,'soc_gap_at':None,'soc':None,'soc_usable':False,
                    'soc_estimated':False,'reached_target':None,'reached_at':None}
                self.sessions[device.id]=session
            if not session: continue
            # Do not feed a completed session with a different vehicle's measurements.
            if tuple(session['vehicle'])!=identity: continue
            terminal=bool(not session['active'] and state.connected and state.vehicle_connected is False
                and state.energy_terminal and now-session['ended_at']<=90)
            if session['active'] or terminal:
                session['checked_at']=now
                contexts=session['contexts']; entry=[now,fraction,price,config.solar_price_per_kwh]
                if (not contexts or now-contexts[-1][0]>=10 or price!=contexts[-1][2]
                    or (fraction is None)!=(contexts[-1][1] is None)):
                    contexts.append(entry)
                session['contexts']=contexts[-8192:]
                raw,stamp=state.energy_wh,state.energy_measured_at
                when=stamp.timestamp() if stamp and stamp.tzinfo else None
                if finite(raw) and raw>=0 and when is not None and when<=now:
                    transaction=state.energy_transaction_id
                    if (transaction is not None and transaction!=session.get('meter_transaction_id')
                        and (session['last_at'] is None or when>=session['last_at'])):
                        # StartTransaction establishes its own meter basis. Never
                        # count an offset from an earlier periodic register as Wh.
                        base,base_at=raw,when
                        started=state.energy_transaction_started_at
                        start_at=started.timestamp() if started and started.tzinfo else None
                        start_wh=state.energy_transaction_start_wh
                        start_valid=finite(start_wh) and start_wh>=0
                        contradicted=bool(start_valid and raw<start_wh)
                        applicable=bool(start_valid and start_at is not None
                            and session['started_at']-2<=start_at<=when
                            and (session['last_at'] is None or start_at>=session['last_at']))
                        continuous=bool(session.get('meter_transaction_id') is None
                            and session['last_at'] is not None and start_valid
                            and start_wh<=session['last_meter']<=raw
                            and (start_at is None or start_at<=session['last_at']))
                        if applicable and not contradicted:
                            base,base_at=start_wh,start_at
                        elif continuous and not contradicted:
                            # Adopt metadata for a transaction already tracked by
                            # an older release without dropping its next interval.
                            base,base_at=session['last_meter'],session['last_at']
                        elif contradicted or session['last_at'] is not None:
                            session['meter_partial']=True;session['soc_gap_at']=when
                            session['soc_gap_transaction_id']=transaction
                        elif start_valid and raw>start_wh:
                            # The first observed point omits pre-history; do not
                            # claim that an untracked prefix is complete accounting.
                            session['meter_partial']=True
                        session['last_meter']=base;session['last_at']=base_at
                        session['meter_transaction_id']=transaction
                        session['points'].append([base_at,session['energy_wh']])
                        session['points']=session['points'][-4096:]
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
                            session['soc_gap_transaction_id']=session.get('meter_transaction_id')
                        else:
                            self.allocate(session,delta,session['last_at'],
                                min(when,session['ended_at']) if terminal else when,config.sample_max_age_s)
                            session['energy_wh']+=delta
                        session['last_meter']=raw;session['last_at']=when
                        session['points'].append([when,session['energy_wh']])
                        session['points']=session['points'][-4096:]
                power=state.observed_power
                if (session.get('soc_gap_at') is not None and session['energy_wh']==0
                    and session.get('soc_gap_transaction_id') is None
                    and state.connected and state.observed_state in
                    ('Preparing','SuspendedEV','SuspendedEVSE','Finishing','Available')
                    and power and power.quality==Quality.FRESH
                    and power.usable(snapshot.at,config.sample_max_age_s) and 0<=power.value<=20):
                    # Recover the pre-first-Wh fault persisted by 0.1.11 only at
                    # a measured stop. Accounting remains explicitly partial.
                    session['soc_gap_at']=None
                    session['soc_gap_transaction_id']=None
                self.soc(session,snapshot,config,device,state,vehicle)
                if state.energy_terminal:session['terminal_pending']=False
                if state.connected and state.vehicle_connected is False:
                    if session['active']:
                        session['active']=False;session['ended_at']=now
                        session['terminal_pending']=session['energy_wh']>0 and not state.energy_terminal
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
        # Upgrade 0.1.10 sessions: Peugeot is now the only source of reference.
        if session['anchor'] and session['anchor'].get('source')=='manual':
            session['anchor']=None
            session['reached_target']=None;session['reached_at']=None
        reference=self.peugeot_references.get(device.vehicle_id+'|'+vehicle.vin) if vehicle else None
        if reference and reference['at']<=now:
            stamp=reference['at']
            if not session['anchor'] or stamp>session['anchor']['at']:
                session['anchor']={'soc':reference['soc'],'at':stamp,'energy':None,'source':'vehicle'}
                # Real later measurements override the estimate, with 1% hysteresis.
                if (session['reached_target'] is not None and session.get('reached_at') is not None
                    and stamp>session['reached_at'] and reference['soc']<session['reached_target']-1):
                    session['reached_target']=None;session['reached_at']=None
        anchor=session['anchor']; session['soc_usable']=False
        session['soc']=anchor['soc'] if anchor else None
        session['soc_estimated']=bool(anchor and (not raw or not raw.fresh(snapshot.at,config.peugeot.max_age_s)))
        idle=state.observed_state in ('Available','Preparing','SuspendedEV','SuspendedEVSE','Finishing')
        if anchor and vehicle and vehicle.capacity_kwh and session['points']:
            base=anchor.get('energy')
            if base is None:
                # An older Peugeot reading starts from the first available index.
                # Only observed energy is added; nothing before that index is invented.
                base=energy_at(session['points'],anchor['at'])
                if anchor['at']<=session['points'][-1][0]: anchor['energy']=base
            gain=max(0,session['energy_wh']-base)
            session['soc']=min(100,max(0,anchor['soc']+100*gain*vehicle.efficiency/(vehicle.capacity_kwh*1000)))
            session['soc_estimated']=gain>0 or not raw or not raw.fresh(snapshot.at,config.peugeot.max_age_s)
            session['soc_usable']=bool(state.connected and (session.get('soc_gap_at') is None or
                anchor['at']>=session['soc_gap_at']) and
                (idle or (session['last_at'] is not None and now-session['last_at']<=max(90,config.sample_max_age_s))))
        elif (anchor and state.connected
              and (session.get('soc_gap_at') is None or anchor['at']>=session['soc_gap_at'])
              and (idle or now-session['started_at']<=90)):
            session['soc_usable']=True
        session['soc_reason']=None
        if not session['soc_usable']:
            session['soc_reason']=("Batterie Peugeot indisponible" if not anchor else
                "Borne hors connexion" if not state.connected else
                "Compteur d’énergie de la borne incohérent" if session.get('soc_gap_at') is not None and anchor['at']<session['soc_gap_at'] else
                "Capacité utile de la batterie à configurer" if not vehicle or not vehicle.capacity_kwh else
                "Index d’énergie de la borne absent" if session['last_at'] is None else
                "Index d’énergie de la borne trop ancien")

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
        partial=session['meter_partial'] or session.get('terminal_pending',False)
        return {'id':session['id'],'active':session['active'],
            'ended_at':datetime.fromtimestamp(session['ended_at'],timezone.utc).isoformat() if session['ended_at'] else None,
            'energy_kwh':energy/1000,'energy_partial':partial,
            'cost_eur':session['cost_eur'] if session['priced_wh']>0 or energy==0 else None,
            'cost_partial':partial or session['priced_wh']+1e-6<energy,
            'solar_percent':100*session['solar_wh']/energy if not partial and energy>0 and session['allocated_wh']+1e-6>=energy else None,
            'average_price_per_kwh':session['cost_eur']/(energy/1000) if not partial and energy>0 and session['priced_wh']+1e-6>=energy else None,
            'effective_price_per_kwh':self.effective_price,
            'soc':session['soc'],'soc_estimated':session['soc_estimated'],'soc_usable':session['soc_usable'],
            'soc_reason':session.get('soc_reason'),
            'soc_reference_missing':not session['anchor'],
            'soc_reference_source':session['anchor'].get('source','vehicle') if session['anchor'] else None,
            'soc_reference_at':datetime.fromtimestamp(session['anchor']['at'],timezone.utc).isoformat() if session['anchor'] else None}
