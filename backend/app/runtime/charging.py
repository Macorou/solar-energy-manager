"""Persistent plug-session counters and an explicitly estimated SOC/energy mix.

Meter deltas are measured. Their allocation between contexts is time-weighted,
assuming uniform delivery inside each meter interval; it is never a billing meter.
"""
import json
import math
import uuid
from datetime import datetime, timezone
from app.domain.measurements import Quality
from app.engine.evcc_soc import SocEstimator
from app.domain.commands import CHARGER_START_WAIT_S
from app.storage.charging_sessions import SessionHistory
from app.sessions.soc_capture import capture_start, recover_start


CHECKPOINT_INTERVAL_S=60
# Clock bookkeeping refreshed every tick. Alone, it is persisted at most once per
# CHECKPOINT_INTERVAL_S; a restart then reports the gap as a partial duration.
VOLATILE_FIELDS=('checked_at','duration_last_at','duration_valid_until','duration_charging','charge_duration_s')
# Meter points are not read back by the current code; keep only a recent tail.
MAX_POINTS=360


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
        for session in self.sessions.values():recover_start(session)
        self.history=SessionHistory(store)
        self.history.migrate(self.sessions)
        self.peugeot_references=store.get('peugeot_soc_references',{})
        # Migrate references from older releases without reusing estimated gains.
        for session in self.sessions.values():
            anchor=session.get('anchor')
            if (anchor and anchor.get('source','vehicle')=='vehicle'
                    and '|'.join(session['vehicle']) not in self.peugeot_references):
                self.remember_peugeot(*session['vehicle'],anchor['soc'],anchor['at'])
        self.effective_price=None
        self.persisted=None;self.persisted_at=None

    def remember_peugeot(self,vehicle_id,vin,soc,stamp):
        if not vehicle_id or not finite(soc) or not 0<=soc<=100: return
        key=vehicle_id+'|'+vin
        self.peugeot_references[key]={'soc':soc,'at':stamp}

    def update(self,snapshot,config):
        now=snapshot.at.timestamp(); vehicles={v.id:v for v in config.vehicles}
        # Keep the latest constructor reference even outside a plug session.
        for vehicle in config.vehicles:
            raw=snapshot.vehicle_telemetry.get(vehicle.id)
            if (raw and finite(raw.soc) and 0<=raw.soc<=100
                and raw.quality!=Quality.ESTIMATED):
                stamp=raw.measured_at.timestamp() if raw.measured_at and raw.measured_at.tzinfo else None
                self.remember_peugeot(vehicle.id,vehicle.vin,raw.soc,stamp)
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
                previous=session if session and session['active'] else None
                session={'id':str(uuid.uuid4()),'vehicle':list(identity),'active':True,'started_at':now,
                    'ended_at':None,'energy_wh':0.,'cost_eur':0.,'priced_wh':0.,'solar_wh':0.,'allocated_wh':0.,
                    'last_meter':None,'last_at':None,'points':[],'contexts':[],'anchor':None,
                    'meter_partial':False,'terminal_pending':False,'soc_gap_at':None,'soc':None,'soc_usable':False,
                    'soc_estimated':False,'reached_target':None,'reached_at':None,
                    'charge_duration_s':0.,'duration_partial':False,
                    'history_soc_start':None,'history_soc_start_source':'pending'}
                if previous:
                    # A configuration/SOC reference change is not an unplug.
                    # Runtime SOC rebases as before; historical counters stay in
                    # the original plug period, including its measured prefix.
                    session['history_id']=previous.get('history_id',previous['id'])
                    session['history_started_at']=previous.get('history_started_at',previous['started_at'])
                    session['history_soc_start']=previous.get('history_soc_start')
                    session['history_soc_start_source']=previous.get('history_soc_start_source','unavailable')
                    old_base=previous.get('history_base',{})
                    session['history_base']={k:previous.get(k,0)+old_base.get(k,0) for k in
                        ('energy_wh','cost_eur','priced_wh','solar_wh','allocated_wh')}
                    session['history_base'].update(measured=previous.get('last_at') is not None or old_base.get('measured',False),
                        meter_partial=previous.get('meter_partial',False) or previous.get('history_meter_partial',False) or old_base.get('meter_partial',False),
                        charge_duration_s=None,duration_partial=True)
                    for key in ('last_meter','last_at','meter_transaction_id','history_meter_partial'):
                        if key in previous:session[key]=previous[key]
                    session['contexts']=list(previous['contexts'])
                    if previous.get('last_at') is not None:session['points']=[[previous['last_at'],0.]]
                self.sessions[device.id]=session
            if not session: continue
            # Do not feed a completed session with a different vehicle's measurements.
            if tuple(session['vehicle'])!=identity: continue
            terminal=bool(not session['active'] and state.connected and state.vehicle_connected is False
                and state.energy_terminal and now-session['ended_at']<=90)
            if session['active'] or terminal:
                last_check=session.get('duration_last_at')
                if session.get('charge_duration_s') is not None and last_check is not None:
                    elapsed=max(0,now-last_check)
                    valid_until=session.get('duration_valid_until',last_check)
                    if session.get('duration_charging'):
                        session['charge_duration_s']+=max(0,min(now,valid_until)-last_check)
                    if elapsed>max(90,config.sample_max_age_s) or now>valid_until:
                        session['duration_partial']=True
                power=state.observed_power
                session['duration_last_at']=now
                power_valid=bool(state.connected and power and power.usable(snapshot.at,config.sample_max_age_s))
                status_at=state.status_received_at or state.status_measured_at
                status_valid=bool(state.connected and status_at and status_at.tzinfo
                    and 0<=now-status_at.timestamp()<=config.sample_max_age_s
                    and state.observed_state in ('Charging','Preparing','SuspendedEV','SuspendedEVSE','Finishing','Available'))
                session['duration_charging']=bool(power.value>20 if power_valid else
                    state.observed_state=='Charging' if status_valid else False)
                session['duration_valid_until']=(power.availability_at.timestamp()+config.sample_max_age_s if power_valid
                    else status_at.timestamp()+config.sample_max_age_s if status_valid else now)
                if not power_valid and not status_valid:session['duration_partial']=True
                session['checked_at']=now
                contexts=session['contexts']; entry=[now,fraction,price,config.solar_price_per_kwh]
                if (not contexts or now-contexts[-1][0]>=10 or price!=contexts[-1][2]
                    or (fraction is None)!=(contexts[-1][1] is None)):
                    contexts.append(entry)
                session['contexts']=contexts[-8192:]
                raw,stamp=state.energy_wh,state.energy_measured_at
                when=stamp.timestamp() if stamp and stamp.tzinfo else None
                first_valid=finite(raw) and raw>=0 and when is not None and 0<=now-when<=max(90,config.sample_max_age_s)
                if session['last_at'] is None and not first_valid and (
                    state.observed_state=='Charging' or power_valid and power.value>20):
                    session['history_meter_partial']=True
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
                            if start_at<=session.get('history_started_at',session['started_at'])+2:
                                session['history_meter_partial']=False
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
                        session['points']=session['points'][-MAX_POINTS:]
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
                        session['points']=session['points'][-MAX_POINTS:]
                if session['last_at'] is not None:
                    # Allocation of the next delta starts at last_at: it only reads the
                    # context in force at that time and later ones.
                    kept=session['contexts']
                    first=next((i for i in range(len(kept)-1,-1,-1) if kept[i][0]<=session['last_at']),0)
                    session['contexts']=kept[first:]
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
                capture_start(session)
                valid_terminal=bool(state.energy_terminal and when is not None and
                    session['started_at']-2<=when<=now)
                if valid_terminal:
                    session['terminal_pending']=False
                    session['history_terminal_confirmed']=True
                if state.connected and state.vehicle_connected is False:
                    if session['active']:
                        session['active']=False;session['ended_at']=now
                        session['terminal_pending']=session['energy_wh']>0 and not state.energy_terminal
                        session['history_terminal_confirmed']=valid_terminal
            # Disconnection of the controller never closes a plug session.
        self.checkpoint(now,config)

    def checkpoint(self,now,config):
        """Persist accounting changes at once, clock-only changes at a bounded rate."""
        complete=json.dumps(self.sessions,allow_nan=False,sort_keys=True)
        fingerprint=json.dumps({key:{k:v for k,v in session.items() if k not in VOLATILE_FIELDS}
            for key,session in self.sessions.items()},allow_nan=False,sort_keys=True)
        if self.persisted is not None and (complete==self.persisted[1] or fingerprint==self.persisted[0]
                and 0<=now-self.persisted_at<CHECKPOINT_INTERVAL_S):
            return
        self.history.checkpoint(self.sessions,config)
        self.persisted,self.persisted_at=(fingerprint,complete),now

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
        reference=self.peugeot_references.get(device.vehicle_id+'|'+vehicle.vin) if vehicle else None
        fetched=(raw.soc if raw and finite(raw.soc) and 0<=raw.soc<=100
                 and raw.quality not in (Quality.ESTIMATED,Quality.UNAVAILABLE) else None)
        # A percentage kept from before a Peugeot error never seeds a session: the car may
        # have been driven since. No Peugeot measurement time participates in the estimator.
        capacity=vehicle.capacity_kwh if vehicle else None
        estimator=SocEstimator.restore(capacity,session.get('evcc_soc')) if capacity else None
        legacy=session.get('anchor')
        if (estimator and not estimator.sampled and not session.get('evcc_soc') and legacy
            and legacy.get('source','vehicle')=='vehicle' and finite(legacy.get('soc'))
            and 0<=legacy['soc']<=100 and finite(legacy.get('energy'))
            and 0<=legacy['energy']<=session['energy_wh']):
            estimator.soc(legacy['soc'],legacy['energy'])
        if estimator:
            if estimator.sampled and fetched is not None and fetched!=estimator.prev_soc:
                session['evcc_gap_cleared']=session.get('soc_gap_at')
            session['soc']=estimator.soc(fetched,session['energy_wh'])
            session['evcc_soc']=estimator.dump()
            session['soc_usable']=estimator.sampled
            baseline=estimator.prev_soc if estimator.sampled else None
            if not estimator.sampled:session['soc']=None
        else:
            baseline=fetched if fetched is not None else reference['soc'] if reference else None
            session['soc']=baseline
            session['soc_usable']=fetched is not None
        # This session's own percentage, still the best guess when the energy checks below fail.
        session['soc_known']=session['soc_usable']
        # Energy-source integrity is separate from EVCC's percentage calculation.
        # These checks use electrical telemetry only, never a Peugeot timestamp.
        gap=session.get('soc_gap_at')
        valid_energy=gap is None or session.get('evcc_gap_cleared')==gap
        idle=state.observed_state in ('Available','Preparing','SuspendedEV','SuspendedEVSE','Finishing')
        recent=(session['last_at'] is not None and
                snapshot.at.timestamp()-session['last_at']<=max(90,config.sample_max_age_s))
        starting=session['last_at'] is None and snapshot.at.timestamp()-session['started_at']<=CHARGER_START_WAIT_S
        if session['soc_usable'] and not (state.connected and valid_energy and (idle or recent or starting)):
            session['soc_usable']=False
            session['soc_reason']=('Borne hors connexion' if not state.connected else
                'Compteur d’énergie de la borne incohérent' if not valid_energy else
                'Index d’énergie de la borne absent' if session['last_at'] is None else
                'Index d’énergie de la borne trop ancien')
        else:
            session['soc_reason']=None if session['soc_usable'] else (
                'Renseigner la capacité utile de la batterie pour estimer pendant une indisponibilité Peugeot'
                if baseline is not None and not capacity else 'Batterie Peugeot indisponible')
        session['soc_estimated']=bool(session['soc_usable'] and
            (fetched is None or session['soc']!=fetched))
        session['anchor']=({'soc':baseline,'at':reference.get('at') if reference else None,
                            'source':'vehicle'} if baseline is not None else None)

    def target_reached(self,device_id,target):
        session=self.sessions.get(device_id)
        return bool(session and session['active'] and session['soc_usable']
                    and session['soc'] is not None and 0<target<100 and session['soc']>=target)

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
            'soc_reason':session.get('soc_reason'),'soc_known':session.get('soc_known',session['soc_usable']),
            'soc_reference_missing':not session['anchor'],
            'soc_reference_source':session['anchor'].get('source','vehicle') if session['anchor'] else None,
            'soc_reference_at':datetime.fromtimestamp(session['anchor']['at'],timezone.utc).isoformat() if session['anchor'] and session['anchor'].get('at') is not None else None}
