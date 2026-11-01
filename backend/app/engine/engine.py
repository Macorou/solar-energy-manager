from dataclasses import dataclass,replace,field
from datetime import timedelta
import math
import uuid
from app.domain.commands import CommandIntent,CHARGER_START_WAIT_S,RESERVATION_S
from app.domain.devices import Reservation
from app.domain.measurements import late
from app.engine.budget import solar_budget_w,power_coherent,measurements_coherent
from app.engine.hysteresis import Timers
from app.engine.heater_targets import HeaterTargets
from app.engine.phase_limits import phase_power_limit,current_credit
from app.engine.evcc_loadpoint import PvController
from app.engine.charger_feedback import unapplied_overload
from app.simulation.clock import Clock

# Charger adjustments that no site or phase limit requires: smaller changes and
# faster repetitions only make the car and the station chase measurement noise.
CHARGER_DEADBAND_A = 0.5
CHARGER_ADJUST_INTERVAL_S = 15
# A car in SuspendedEV with a usable offer for this long is declining the charge.
CHARGER_DECLINED_S = 120
# A charger that ignored its cap under a measured overload is stopped, then retried after
# a doubling pause (5, 10, 20, 30 min...): a night charge must not stay blocked.
LIMIT_FAULT_RETRY_S = 300
LIMIT_FAULT_RETRY_MAX_S = 1800
LIMIT_FAULT_RESET_S = 7200


@dataclass(frozen=True)
class DecisionBatch:
    commands: tuple
    reservations: tuple
    reasons: dict
    effective_targets: dict = field(default_factory=dict)
    target_sources: dict = field(default_factory=dict)


class EnergyEngine:
    def __init__(self, clock=None):
        self.clock = clock or Clock()
        self.timers = Timers()
        self.requested = {}
        self.running_since = {}
        self.stopped_at = {}
        self.network_allowed = {}
        self.network_stop_pending = set()
        self.network_stop_issued = set()
        self.requested_targets = {}
        self.heater_targets = HeaterTargets()
        self.phase_current_seen = set()
        self.charger_pv = {}
        self.charger_last_control = {}
        self.charger_offered = {}
        self.charger_start_credit = {}
        self.charger_pv_frame = {}
        self.charger_ack_at = {}
        self.charger_commanded = {}
        self.charger_limit_faults = set()
        self.charger_fault_retry = {}

    def forget(self, device_id):
        self.requested.pop(device_id,None)
        self.requested_targets.pop(device_id,None)
        self.charger_last_control.pop(device_id,None)
        self.charger_pv.pop(device_id,None)
        self.charger_pv_frame.pop(device_id,None)

    def command_result(self, intent, accepted, at=None):
        if accepted:
            self.charger_offered[intent.device_id]=intent.limit_w or 0
            self.charger_commanded[intent.device_id]=intent.limit_w or 0
            self.charger_ack_at[intent.device_id]=at or self.clock.now()
            # The PV reference must follow the accepted offer: the grid already
            # reflects it, and an older frame would undo the change step by step.
            self.charger_pv_frame.pop(intent.device_id,None)
        else:
            self.forget(intent.device_id)

    def limit_fault_retry(self, spec, state, now, mono):
        """Lift an expired limit fault so the charge restarts; unplugging forgets the history."""
        retry=self.charger_fault_retry.get(spec.id)
        if spec.id in self.charger_limit_faults and (retry is None or now>=retry['until']):
            # A fault persisted by an older release has no pause: retry it now.
            self.charger_limit_faults.discard(spec.id)
            self.timers.reached(spec.id+':cap_unapplied',False,0,mono)
            if retry is None:
                self.charger_fault_retry[spec.id]={'until':now,'attempt':0}
        if state and state.connected and state.vehicle_connected is False and spec.id not in self.charger_limit_faults:
            self.charger_fault_retry.pop(spec.id,None)

    def declined_chargers(self, snapshot, specs, mono):
        """Chargers whose car has refused a usable offer, measured idle, for CHARGER_DECLINED_S."""
        declined=set()
        for spec in specs:
            if spec.kind!='charger': continue
            state=snapshot.device_states.get(spec.id)
            power=state.observed_power if state else None
            idle=bool(state and state.connected and not state.fault and state.observed_state=='SuspendedEV'
                and self.requested.get(spec.id,0)>=spec.min_power_w>0
                and power and power.usable(snapshot.at,snapshot.sample_max_age_s) and power.value<=20)
            if self.timers.reached(spec.id+':declined',idle,CHARGER_DECLINED_S,mono):
                declined.add(spec.id)
        return declined

    def evaluate(self, snapshot, specs, policies, authorizations):
        now, mono = snapshot.at, self.clock.monotonic()
        for spec in specs:
            state=snapshot.device_states.get(spec.id)
            if spec.kind=='charger':
                self.limit_fault_retry(spec,state,now,mono)
            if (spec.kind=='charger' and spec.id not in self.charger_limit_faults
                    and self.timers.reached(spec.id+':cap_unapplied',
                        unapplied_overload(snapshot,spec,self.charger_commanded.get(spec.id,0)),60,mono)):
                self.charger_limit_faults.add(spec.id)
                last=self.charger_fault_retry.get(spec.id)
                attempt=1 if not last or (now-last['until']).total_seconds()>LIMIT_FAULT_RESET_S else last['attempt']+1
                pause=min(LIMIT_FAULT_RETRY_S*2**(attempt-1),LIMIT_FAULT_RETRY_MAX_S)
                self.charger_fault_retry[spec.id]={'until':now+timedelta(seconds=pause),'attempt':attempt}
            offered=state.offered_current if state else None
            sent=self.charger_ack_at.get(spec.id)
            if (spec.kind=='charger' and self.requested.get(spec.id,0)>0 and state
                    and state.observed_state in ('Charging','SuspendedEV') and offered
                    and offered.usable(now,snapshot.sample_max_age_s)
                    and (sent is None or offered.availability_at>sent)):
                unit=spec.voltage*(len(spec.grid_phases) or 1)
                if abs(offered.value-self.requested[spec.id]/unit)>.23:
                    self.requested[spec.id]=offered.value*unit
                    self.charger_offered[spec.id]=offered.value*unit
                    self.charger_pv_frame.pop(spec.id,None)
        declined = self.declined_chargers(snapshot,specs,mono)
        solar = solar_budget_w(snapshot)
        measured = {key: max(0,state.observed_power.value or 0) if state.observed_power else 0
                    for key,state in snapshot.device_states.items()}
        grid_valid = bool(snapshot.grid and snapshot.grid.usable(now,snapshot.sample_max_age_s))
        unusable={key:state.observed_power for key,state in snapshot.device_states.items()
                  if not (state.observed_power and state.observed_power.usable(now,snapshot.sample_max_age_s))}
        all_power_valid=not unusable
        # Degraded: some device readings are only late. Running devices may keep (never
        # raise) their power; a late device counts at its maximum against the site limit.
        degraded=bool(unusable) and all(late(sample,now,snapshot.sample_max_age_s) for sample in unusable.values())
        known_draw=sum(value for key,value in measured.items() if key not in unusable)
        global_remaining = max(0,snapshot.site_limit_w-(snapshot.grid.value-known_draw)) \
            if grid_valid and (all_power_valid or degraded) and snapshot.site_limit_w is not None else 0
        solar_remaining = solar or 0
        shared_tolerance = max((p.import_tolerance_w for p in policies.values()),default=0)
        tolerance_spent = 0
        reasons, commands, reservations = {}, [], []
        effective_targets, target_sources = {}, {}
        phase_extra={}
        pending = {r.device_id:r.power_w for r in snapshot.reservations}
        committed={s.id:max(measured.get(s.id,0),pending.get(s.id,0),self.requested.get(s.id,0),
                            s.max_power_w if s.id in unusable else 0) for s in specs}
        # A declining car keeps its offer against the site and phase limits (it may
        # resume at any time), but only its measured draw is taken from the solar surplus.
        solar_committed={key:measured.get(key,0) if key in declined else value for key,value in committed.items()}
        phase_reserves={}
        for s in specs:
            if s.kind!='charger' or not s.grid_phases: continue
            state=snapshot.device_states.get(s.id)
            offered=max(pending.get(s.id,0),self.requested.get(s.id,0))/(s.voltage*len(s.grid_phases))
            holds={}
            for i,p in enumerate(s.grid_phases):
                actual,_=current_credit(snapshot,s,i)
                holds[p]=max(0,offered-actual)
                phase_extra[p]=phase_extra.get(p,0)+holds[p]
            phase_reserves[s.id]=holds
        coherent=power_coherent(snapshot)
        if not coherent and grid_valid and all_power_valid and snapshot.site_limit_w is not None:
            # Mixed frames can maintain or reduce an existing authorization, never increase it.
            global_remaining=max(0,sum(committed.values())+min(0,snapshot.site_limit_w-snapshot.grid.value))
            solar_remaining=max(0,sum(measured.values())-snapshot.grid.value-snapshot.export_margin_w)
        global_remaining-=sum(committed.values())
        solar_remaining-=sum(solar_committed.values())

        def active(spec):
            return measured.get(spec.id,0)>20 or self.requested.get(spec.id,0)>0 or pending.get(spec.id,0)>0

        def order(spec):
            protected = spec.kind=='water_heater' and active(spec)
            auth = authorizations.get(spec.id)
            deadline = auth.expires_at.timestamp() if auth and auth.expires_at else math.inf
            return (not protected,spec.priority,deadline,spec.id)

        for spec in sorted(specs,key=order):
            if spec.kind=='water_heater': spec=replace(spec,min_power_w=spec.max_power_w)
            site_available=global_remaining+committed.get(spec.id,0)
            solar_available=solar_remaining+solar_committed.get(spec.id,0)
            policy = policies.get(spec.id)
            state = snapshot.device_states.get(spec.id)
            previous = self.requested.get(spec.id)
            running = active(spec)
            if (spec.kind=='charger' and previous and previous>=spec.min_power_w
                and state and state.observed_state.lower()=='charging'
                and grid_valid and snapshot.site_limit_w is not None and snapshot.grid.value<=snapshot.site_limit_w
                and site_available>=measured.get(spec.id,0)>0):
                site_available=max(site_available,spec.min_power_w)
            if running:
                self.running_since.setdefault(spec.id,mono)
            else:
                self.running_since.pop(spec.id,None)
                self.phase_current_seen.discard(spec.id)
            desired, reason = 0.0, 'En attente'
            battery_unknown, last_soc = False, None
            eligible = bool(policy and policy.armed and state and state.connected and not state.fault)
            auth = authorizations.get(spec.id)
            manual_active = bool(policy and policy.mode=='manual' and (spec.kind=='charger'
                or policy.manual_until and now<policy.manual_until))
            network = bool(policy and (
                manual_active
                or policy.mode=='off_peak_solar' and policy.off_peak
                or policy.mode=='planned' and auth and auth.allow_grid))
            network_closed = (self.network_allowed.get(spec.id,False) and not network
                              and policy and policy.mode in ('solar','planned','off_peak_solar'))
            self.network_allowed[spec.id] = network
            if network_closed:
                self.network_stop_pending.add(spec.id)
                self.network_stop_issued.discard(spec.id)
            target = policy.target if policy else None
            if spec.kind=='water_heater' and policy:
                tolerance=max(0,min(policy.import_tolerance_w,shared_tolerance-tolerance_spent))
                target,source=self.heater_targets.select(spec.id,policy,network,solar_available,
                    coherent,spec.max_power_w,tolerance,mono)
                effective_targets[spec.id]=target
                target_sources[spec.id]=source
            if not eligible:
                reason = 'Appareil non activé ou indisponible'
            elif policy.mode=='off':
                eligible, reason = False, 'Arrêt demandé'
            elif spec.id in self.charger_limit_faults:
                retry=self.charger_fault_retry[spec.id]['until']
                minutes=max(1,math.ceil((retry-now).total_seconds()/60))
                eligible, reason = False, f'Limite de recharge non appliquée : nouvelle tentative dans {minutes} min'
            elif (state.temperature>=target if spec.kind=='water_heater' and state.temperature is not None
                  and target is not None else state.target_reached):
                eligible, reason = False, 'Objectif atteint'
            elif spec.kind=='charger' and state.vehicle_connected is False:
                eligible, reason = False, 'Véhicule non branché'
            elif spec.kind=='charger' and policy.vehicle_id:
                telemetry = snapshot.vehicle_telemetry.get(policy.vehicle_id)
                goal = auth.target_soc if auth and policy.mode!='manual' else policy.target or 80
                if not telemetry or not telemetry.usable(now,policy.soc_max_age_s):
                    # A percentage left here is this session's estimate (the coordinator drops a
                    # Peugeot value read through an API error): unverifiable, it still ends the charge.
                    last_soc = (telemetry.soc if telemetry and telemetry.soc is not None
                                and math.isfinite(telemetry.soc) and 0<=telemetry.soc<=100 else None)
                    if network and last_soc is not None and goal<100 and last_soc>=goal:
                        eligible, reason = False, 'Objectif atteint (dernière estimation)'
                    elif network:
                        # In a grid window (planned or manual) the charge goes on: without any
                        # percentage the car itself stops when full.
                        battery_unknown = True
                    else:
                        eligible, reason = False, (telemetry.unavailable_reason if telemetry else None) or 'Batterie indisponible'
                elif goal<100 and telemetry.soc >= goal:
                    eligible, reason = False, 'Objectif atteint'
            if eligible:
                if policy.mode=='manual':
                    eligible = manual_active
                    network, reason = eligible, 'Commande manuelle' if eligible else 'Commande manuelle terminée'
                elif policy.mode=='planned':
                    eligible = bool(auth and (auth.allow_grid or auth.allow_solar))
                    network = bool(auth and auth.allow_grid)
                    reason = auth.reason if auth else 'Aucun programme applicable'
                elif policy.mode=='off_peak_solar':
                    network = policy.off_peak
                    reason = ('Chauffe heures creuses' if network and target_sources.get(spec.id)!='solar'
                              else 'Surplus solaire')
                else:
                    reason = 'Surplus solaire'
            hard_valid = (grid_valid and (all_power_valid or degraded) and snapshot.site_limit_w is not None
                          and site_available>=spec.min_power_w>0)
            site_capped = False
            phase_missing = bool(snapshot.phase_control_enabled and spec.grid_phases and not all(
                snapshot.phase_currents.get(p) and snapshot.phase_currents[p].usable(now,snapshot.sample_max_age_s)
                for p in spec.grid_phases))
            # Opt-in: during a grid window, a fixed current when the site or phase meter is
            # missing. Nothing then protects the main breaker; 0 keeps the stop.
            fallback = bool(spec.kind=='charger' and eligible and network and snapshot.grid_fallback_current_a
                            and (not grid_valid or phase_missing))
            if fallback:
                amps = min(snapshot.grid_fallback_current_a,spec.max_current_a)
                desired = min(spec.max_power_w,amps*spec.voltage*(len(spec.grid_phases) or 1)) \
                    if amps>=spec.min_current_a else 0
                reason = f'Mesure réseau indisponible : courant de secours {amps:g} A'
            elif eligible and hard_valid and (network or solar is not None or (running and not coherent)):
                if degraded:
                    # Keep what runs, start nothing: the site and phase limits below still reduce it.
                    desired = min(previous or 0,site_available)
                    site_capped = site_available<(previous or 0)
                    reason = ('Mesure électrique en retard : puissance maintenue' if desired
                              else 'Mesure électrique en retard : démarrage différé')
                elif network:
                    desired = min(spec.max_power_w,site_available)
                    site_capped = site_available<spec.max_power_w
                    self.timers.reached(spec.id+':stop',False,0,mono)
                    if spec.kind=='charger':self.charger_pv_frame.pop(spec.id,None)
                elif spec.kind=='charger':
                    phases=len(spec.grid_phases) or 1
                    unit=spec.voltage*phases
                    actuals=[sample.value for sample in state.currents.values()
                             if sample.usable(now,snapshot.sample_max_age_s)]
                    charging=state.observed_state.lower()=='charging'
                    actual=max(actuals) if actuals else measured.get(spec.id,0)/unit if charging else None
                    offered=(self.charger_offered.get(spec.id,previous) if previous is not None
                             else measured.get(spec.id,0)) or 0
                    frame=self.charger_pv_frame.get(spec.id)
                    if not frame or mono-frame[0]>=30:
                        frame=(mono,offered)
                        self.charger_pv_frame[spec.id]=frame
                    offered=frame[1]
                    pv=self.charger_pv.setdefault(spec.id,PvController())
                    current=pv.current(now=mono,site_power_w=measured.get(spec.id,0)-solar_available,
                        voltage=spec.voltage,phases=phases,charging=charging,enabled=running,
                        actual_a=actual,offered_a=offered/unit,minimum_a=spec.min_power_w/unit,
                        maximum_a=min(spec.max_current_a,spec.max_power_w/unit),
                        enable_delay_s=policy.start_delay_s,disable_delay_s=policy.stop_delay_s,
                        enable_threshold_w=-max(spec.min_power_w,policy.start_surplus_w) if policy.start_surplus_w else 0,
                        disable_threshold_w=max(0,min(policy.import_tolerance_w,shared_tolerance-tolerance_spent)),
                        hold_minimum=mono-self.running_since.get(spec.id,mono)<policy.min_run_s)
                    desired=min(site_available,current*unit)
                    site_capped=site_available<current*unit
                    reason=pv.reason
                    if not running and mono-self.stopped_at.get(spec.id,-math.inf)<policy.restart_delay_s:
                        desired=0
                elif running:
                    tolerance = max(0,min(policy.import_tolerance_w,shared_tolerance-tolerance_spent))
                    deficient = solar_available+tolerance < spec.min_power_w
                    stopped = self.timers.reached(spec.id+':stop',deficient,policy.stop_delay_s,mono)
                    minimum_run = mono-self.running_since.get(spec.id,mono)<policy.min_run_s
                    if deficient and stopped and not minimum_run:
                        reason = 'Surplus insuffisant : suspension'
                    else:
                        desired = min(spec.max_power_w,site_available,
                            max(spec.min_power_w,solar_available))
                        reason = 'Passage de nuage : temporisation' if deficient else 'Surplus solaire'
                else:
                    enough = coherent and solar_available>=max(spec.min_power_w,policy.start_surplus_w)
                    ready = self.timers.reached(spec.id+':start',enough,policy.start_delay_s,mono)
                    cooldown = mono-self.stopped_at.get(spec.id,-math.inf)>=policy.restart_delay_s
                    if ready and cooldown:
                        desired = min(spec.max_power_w,site_available,solar_available)
                    else:
                        remaining = self.timers.remaining(spec.id+':start',policy.start_delay_s,mono)
                        reason = f'Attente de surplus stable ({remaining:.0f} s)' if enough else 'Surplus insuffisant'
            elif eligible:
                reason = 'Mesure réseau indisponible ou limite de puissance'
            if desired and spec.kind=='water_heater':
                desired = spec.max_power_w if site_available>=spec.max_power_w else 0
            if not coherent and desired and not degraded and not fallback:
                desired=min(desired,previous or 0)
                reason=('Commande en attente de confirmation : aucune augmentation'
                        if snapshot.transition_blocked and measurements_coherent(snapshot)
                        else 'Attente de mesures électriques cohérentes : aucune augmentation')
            if desired and not running and policy.start_not_before and now<policy.start_not_before:
                desired=0
                remaining=(policy.start_not_before-now).total_seconds()
                reason=f'Temporisation native avant démarrage ({remaining:.0f} s)'
            if spec.id in self.network_stop_pending:
                desired=0
                reason='Fin des heures creuses' if spec.kind=='water_heater' else 'Fin du créneau réseau'
                self.timers.reached(spec.id+':start',False,0,mono)
            if battery_unknown and desired:
                reason=(f'Batterie non vérifiable : charge poursuivie jusqu’à l’objectif (dernière estimation {last_soc:.0f} %)'
                        if last_soc is not None else 'Batterie inconnue : charge poursuivie jusqu’à l’arrêt par la voiture')
            if (spec.kind=='charger' and desired and previous and not site_capped
                    and (spec.id in declined
                         or abs(desired-previous)<CHARGER_DEADBAND_A*spec.voltage*(len(spec.grid_phases) or 1)
                         or mono-self.charger_last_control.get(spec.id,-math.inf)<CHARGER_ADJUST_INTERVAL_S)):
                # Keep the current offer; the phase limit below still reduces it at once.
                desired=previous
                if spec.id in declined:
                    reason='La voiture ne demande pas de charge : offre maintenue'
            if desired < spec.min_power_w:
                desired = 0
            if desired and not fallback:
                if state and spec.grid_phases and all(state.currents.get('L'+str(i+1))
                    and state.currents['L'+str(i+1)].usable(now,snapshot.sample_max_age_s)
                    for i in range(len(spec.grid_phases))):self.phase_current_seen.add(spec.id)
                waiting_current=(spec.id not in self.phase_current_seen and previous is not None and previous>0
                    and mono-self.running_since.get(spec.id,-math.inf)<CHARGER_START_WAIT_S)
                other={p:max(0,value-phase_reserves.get(spec.id,{}).get(p,0)) for p,value in phase_extra.items()}
                desired,phase_reason=phase_power_limit(snapshot,spec,desired,other,previous or 0,waiting_current,
                    self.charger_start_credit.get(spec.id))
                for p,value in other.items(): phase_extra[p]=max(phase_extra.get(p,0),value)
                if phase_reason: reason=phase_reason
            if desired and spec.kind=='charger':
                unit=spec.voltage*(len(spec.grid_phases) or 1)
                desired=math.floor(min(desired/unit,spec.max_current_a)*10+1e-9)/10*unit
                # An increase never protects anything: also skip the small ones
                # left after a phase limit, which follows household noise.
                if previous and desired>previous and (mono-self.charger_last_control.get(spec.id,-math.inf)<30
                        or desired-previous<CHARGER_DEADBAND_A*unit):
                    desired=previous
            occupied = max(desired,committed.get(spec.id,0))
            if not network:
                tolerance_spent += max(0,desired-max(0,solar_available))
            global_remaining-=occupied-committed.get(spec.id,0)
            solar_remaining-=occupied-committed.get(spec.id,0)
            reasons[spec.id] = reason
            if not policy or not policy.armed:
                continue
            step=spec.voltage*(len(spec.grid_phases) or 1)*.099 if spec.kind=='charger' else 50
            must_change = (desired>0 and (previous is None or abs(desired-previous)>=step)) \
                or (desired==0 and (previous is None and running or previous is not None and previous>0)) \
                or (spec.id in self.network_stop_pending and spec.id not in self.network_stop_issued)
            if (spec.kind=='charger' and desired==0 and previous==0 and state
                and state.observed_state=='Charging' and state.observed_power
                and state.observed_power.usable(now,snapshot.sample_max_age_s) and state.observed_power.value>20
                and mono-self.charger_last_control.get(spec.id,-math.inf)>=60):
                must_change=True
            target_changed=bool(desired and spec.kind=='water_heater' and target is not None
                and target!=self.requested_targets.get(spec.id,state.target_temperature if state else None))
            if target_changed and not must_change:
                if not coherent: continue
                if policy.start_not_before and now<policy.start_not_before:
                    reasons[spec.id]='Temporisation native avant changement de consigne'
                    continue
            if must_change or target_changed:
                action=('set_power' if desired else 'suspend') if must_change else 'set_temperature'
                command = CommandIntent(str(uuid.uuid4()),spec.id,action,
                    desired,now+timedelta(seconds=90),reason,
                    target_temperature=target if desired and spec.kind=='water_heater' else None)
                commands.append(command)
                if action=='suspend' and spec.id in self.network_stop_pending:
                    self.network_stop_issued.add(spec.id)
                self.requested[spec.id] = desired
                if spec.kind=='charger':
                    self.charger_last_control[spec.id]=mono
                    if previous is None or previous==0:
                        self.charger_start_credit[spec.id]=desired
                if spec.kind=='water_heater': self.requested_targets[spec.id]=target if desired else None
                if desired:
                    self.running_since.setdefault(spec.id,mono)
                    reservations.append(Reservation(spec.id,max(desired,measured.get(spec.id,0)),command.id,
                        now+timedelta(seconds=RESERVATION_S)))
                else:
                    self.stopped_at[spec.id]=mono
                    if measured.get(spec.id,0)>0:
                        reservations.append(Reservation(spec.id,measured[spec.id],command.id,
                            now+timedelta(seconds=RESERVATION_S)))
        return DecisionBatch(tuple(commands),tuple(reservations),reasons,effective_targets,target_sources)
