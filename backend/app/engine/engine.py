from dataclasses import dataclass,replace
from datetime import timedelta
import math
import uuid
from app.domain.commands import CommandIntent
from app.domain.devices import Reservation
from app.engine.budget import solar_budget_w
from app.engine.hysteresis import Timers
from app.simulation.clock import Clock


@dataclass(frozen=True)
class DecisionBatch:
    commands: tuple
    reservations: tuple
    reasons: dict


class EnergyEngine:
    def __init__(self, clock=None):
        self.clock = clock or Clock()
        self.timers = Timers()
        self.requested = {}
        self.running_since = {}
        self.stopped_at = {}

    def forget(self, device_id):
        self.requested.pop(device_id,None)

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
        pending = {r.device_id:r.power_w for r in snapshot.reservations}

        def active(spec):
            return measured.get(spec.id,0)>20 or self.requested.get(spec.id,0)>0 or pending.get(spec.id,0)>0

        def order(spec):
            protected = spec.kind=='water_heater' and active(spec)
            auth = authorizations.get(spec.id)
            deadline = auth.expires_at.timestamp() if auth and auth.expires_at else math.inf
            return (not protected,spec.priority,deadline,spec.id)

        for spec in sorted(specs,key=order):
            if spec.kind=='water_heater': spec=replace(spec,min_power_w=spec.max_power_w)
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
            network = False
            if not eligible:
                reason = 'Appareil non activé ou indisponible'
            elif policy.mode=='off':
                eligible, reason = False, 'Arrêt demandé'
            elif state.target_reached:
                eligible, reason = False, 'Objectif atteint'
            elif spec.kind=='charger' and state.vehicle_connected is False:
                eligible, reason = False, 'Véhicule non branché'
            elif spec.kind=='charger' and policy.vehicle_id and policy.mode!='manual':
                telemetry = snapshot.vehicle_telemetry.get(policy.vehicle_id)
                if not telemetry or not telemetry.fresh(now,policy.soc_max_age_s):
                    eligible, reason = False, 'Batterie indisponible ou trop ancienne'
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
                    reason = 'Chauffe heures creuses' if network else 'Surplus solaire'
                else:
                    reason = 'Surplus solaire'
            hard_valid = grid_valid and snapshot.site_limit_w is not None and global_remaining>=spec.min_power_w>0
            if eligible and hard_valid and (network or solar is not None):
                if network:
                    desired = min(spec.max_power_w,global_remaining)
                    self.timers.reached(spec.id+':stop',False,0,mono)
                elif running:
                    tolerance = max(0,min(policy.import_tolerance_w,shared_tolerance-tolerance_spent))
                    deficient = solar_remaining+tolerance < spec.min_power_w
                    stopped = self.timers.reached(spec.id+':stop',deficient,policy.stop_delay_s,mono)
                    minimum_run = mono-self.running_since.get(spec.id,mono)<policy.min_run_s
                    if deficient and stopped and not minimum_run:
                        reason = 'Surplus insuffisant : suspension'
                    else:
                        desired = min(spec.max_power_w,global_remaining,
                            max(spec.min_power_w,solar_remaining))
                        reason = 'Passage de nuage : temporisation' if deficient else 'Surplus solaire'
                else:
                    enough = solar_remaining>=max(spec.min_power_w,policy.start_surplus_w)
                    ready = self.timers.reached(spec.id+':start',enough,policy.start_delay_s,mono)
                    cooldown = mono-self.stopped_at.get(spec.id,-math.inf)>=policy.restart_delay_s
                    if ready and cooldown:
                        desired = min(spec.max_power_w,global_remaining,solar_remaining)
                    else:
                        remaining = self.timers.remaining(spec.id+':start',policy.start_delay_s,mono)
                        reason = f'Attente de surplus stable ({remaining:.0f} s)' if enough else 'Surplus insuffisant'
            elif eligible:
                reason = 'Mesure réseau indisponible ou limite de puissance'
            if desired and spec.kind=='water_heater':
                desired = spec.max_power_w if global_remaining>=spec.max_power_w else 0
            if desired < spec.min_power_w:
                desired = 0
            occupied = max(desired,measured.get(spec.id,0),pending.get(spec.id,0))
            if not network:
                tolerance_spent += max(0,desired-max(0,solar_remaining))
            global_remaining = max(0,global_remaining-occupied)
            solar_remaining = max(0,solar_remaining-occupied)
            reasons[spec.id] = reason
            if not policy or not policy.armed:
                continue
            must_change = (desired>0 and (previous is None or abs(desired-previous)>=50)) \
                or (desired==0 and (previous is None and running or previous is not None and previous>0))
            if must_change:
                command = CommandIntent(str(uuid.uuid4()),spec.id,'set_power' if desired else 'suspend',
                    desired,now+timedelta(seconds=90),reason)
                commands.append(command)
                self.requested[spec.id] = desired
                if desired:
                    reservations.append(Reservation(spec.id,max(desired,measured.get(spec.id,0)),command.id,
                        now+timedelta(seconds=90)))
                else:
                    self.stopped_at[spec.id]=mono
                    if measured.get(spec.id,0)>0:
                        reservations.append(Reservation(spec.id,measured[spec.id],command.id,
                            now+timedelta(seconds=90)))
        return DecisionBatch(tuple(commands),tuple(reservations),reasons)
