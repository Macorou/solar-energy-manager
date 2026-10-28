from dataclasses import dataclass,replace,field
from datetime import timedelta
import math
import uuid
from app.domain.commands import CommandIntent
from app.domain.devices import Reservation
from app.engine.budget import solar_budget_w,power_coherent,measurements_coherent
from app.engine.hysteresis import Timers
from app.engine.heater_targets import HeaterTargets
from app.engine.phase_limits import phase_power_limit
from app.simulation.clock import Clock


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

    def forget(self, device_id):
        self.requested.pop(device_id,None)
        self.requested_targets.pop(device_id,None)

    def evaluate(self, snapshot, specs, policies, authorizations):
        now, mono = snapshot.at, self.clock.monotonic()
        solar = solar_budget_w(snapshot)
        measured = {key: max(0,state.observed_power.value or 0) if state.observed_power else 0
                    for key,state in snapshot.device_states.items()}
        grid_valid = bool(snapshot.grid and snapshot.grid.usable(now,snapshot.sample_max_age_s))
        all_power_valid=all(state.observed_power and state.observed_power.usable(now,snapshot.sample_max_age_s)
                            for state in snapshot.device_states.values())
        global_remaining = max(0,snapshot.site_limit_w-(snapshot.grid.value-sum(measured.values()))) \
            if grid_valid and all_power_valid and snapshot.site_limit_w is not None else 0
        solar_remaining = solar or 0
        shared_tolerance = max((p.import_tolerance_w for p in policies.values()),default=0)
        tolerance_spent = 0
        reasons, commands, reservations = {}, [], []
        effective_targets, target_sources = {}, {}
        phase_extra={}
        pending = {r.device_id:r.power_w for r in snapshot.reservations}
        committed={s.id:max(measured.get(s.id,0),pending.get(s.id,0),self.requested.get(s.id,0)) for s in specs}
        phase_reserves={}
        for s in specs:
            if s.kind!='charger' or not s.grid_phases: continue
            state=snapshot.device_states.get(s.id)
            offered=max(pending.get(s.id,0),self.requested.get(s.id,0))/(s.voltage*len(s.grid_phases))
            holds={}
            for i,p in enumerate(s.grid_phases):
                current=state.currents.get('L'+str(i+1)) if state else None
                actual=max(0,current.value) if current and current.usable(now,snapshot.sample_max_age_s) else 0
                holds[p]=max(0,offered-actual)
                phase_extra[p]=phase_extra.get(p,0)+holds[p]
            phase_reserves[s.id]=holds
        coherent=power_coherent(snapshot)
        if not coherent and grid_valid and all_power_valid and snapshot.site_limit_w is not None:
            # Mixed frames can maintain or reduce an existing authorization, never increase it.
            global_remaining=max(0,sum(committed.values())+min(0,snapshot.site_limit_w-snapshot.grid.value))
            solar_remaining=max(0,sum(measured.values())-snapshot.grid.value-snapshot.export_margin_w)
        global_remaining-=sum(committed.values())
        solar_remaining-=sum(committed.values())

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
            solar_available=solar_remaining+committed.get(spec.id,0)
            policy = policies.get(spec.id)
            state = snapshot.device_states.get(spec.id)
            previous = self.requested.get(spec.id)
            running = active(spec)
            if running:
                self.running_since.setdefault(spec.id,mono)
            else:
                self.running_since.pop(spec.id,None)
            desired, reason = 0.0, 'En attente'
            eligible = bool(policy and policy.armed and state and state.connected and not state.fault)
            auth = authorizations.get(spec.id)
            network = bool(policy and (
                policy.mode=='manual' and policy.manual_until and now<policy.manual_until
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
            elif (state.temperature>=target if spec.kind=='water_heater' and state.temperature is not None
                  and target is not None else state.target_reached):
                eligible, reason = False, 'Objectif atteint'
            elif spec.kind=='charger' and state.vehicle_connected is False:
                eligible, reason = False, 'Véhicule non branché'
            elif spec.kind=='charger' and policy.vehicle_id and policy.mode!='manual':
                telemetry = snapshot.vehicle_telemetry.get(policy.vehicle_id)
                if not telemetry or not telemetry.usable(now,policy.soc_max_age_s):
                    eligible, reason = False, 'Batterie indisponible'
                elif telemetry.soc >= (auth.target_soc if auth else policy.target or 80):
                    eligible, reason = False, 'Objectif atteint'
            if eligible:
                if policy.mode=='manual':
                    eligible = bool(policy.manual_until and now<policy.manual_until)
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
            hard_valid = grid_valid and all_power_valid and snapshot.site_limit_w is not None and site_available>=spec.min_power_w>0
            if eligible and hard_valid and (network or solar is not None or (running and not coherent)):
                if network:
                    desired = min(spec.max_power_w,site_available)
                    self.timers.reached(spec.id+':stop',False,0,mono)
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
            if not coherent and desired:
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
            if desired < spec.min_power_w:
                desired = 0
            if desired:
                other={p:max(0,value-phase_reserves.get(spec.id,{}).get(p,0)) for p,value in phase_extra.items()}
                desired,phase_reason=phase_power_limit(snapshot,spec,desired,other)
                for p,value in other.items(): phase_extra[p]=max(phase_extra.get(p,0),value)
                if phase_reason: reason=phase_reason
            occupied = max(desired,committed.get(spec.id,0))
            if not network:
                tolerance_spent += max(0,desired-max(0,solar_available))
            global_remaining-=occupied-committed.get(spec.id,0)
            solar_remaining-=occupied-committed.get(spec.id,0)
            reasons[spec.id] = reason
            if not policy or not policy.armed:
                continue
            must_change = (desired>0 and (previous is None or abs(desired-previous)>=50)) \
                or (desired==0 and (previous is None and running or previous is not None and previous>0)) \
                or (spec.id in self.network_stop_pending and spec.id not in self.network_stop_issued)
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
                if spec.kind=='water_heater': self.requested_targets[spec.id]=target if desired else None
                if desired:
                    reservations.append(Reservation(spec.id,max(desired,measured.get(spec.id,0)),command.id,
                        now+timedelta(seconds=90)))
                else:
                    self.stopped_at[spec.id]=mono
                    if measured.get(spec.id,0)>0:
                        reservations.append(Reservation(spec.id,measured[spec.id],command.id,
                            now+timedelta(seconds=90)))
        return DecisionBatch(tuple(commands),tuple(reservations),reasons,effective_targets,target_sources)
