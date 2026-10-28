"""Per-phase adaptation of EVCC's MIT-licensed ValidateCurrent delta limiter.

Source/ref and full notice: docs/third-party/evcc-MIT.txt (also in Docker).
Unlike EVCC's scalar circuit maximum, each mapped supply phase is independent.
"""
import math


def validate_current(old, requested, measured, limit, margin=0):
    return min(requested,max(0,old+limit-margin-measured))


def current_credit(snapshot,spec,index):
    state=snapshot.device_states.get(spec.id)
    if not state or not state.connected:return 0,False
    own=state.currents.get('L'+str(index+1))
    idle=state.observed_state in ('Available','Preparing','SuspendedEV','SuspendedEVSE','Finishing')
    status_at=state.status_measured_at or state.measured_at
    if idle and (not own or status_at and own.measured_at<=status_at):return 0,True
    grid=snapshot.phase_currents.get(spec.grid_phases[index])
    coherent=bool(own and own.usable(snapshot.at,snapshot.sample_max_age_s) and grid
        and grid.usable(snapshot.at,snapshot.sample_max_age_s)
        and abs((grid.availability_at-own.availability_at).total_seconds())<=2)
    return (max(0,own.value) if coherent else 0),coherent


def phase_power_limit(snapshot,spec,desired_w,extra,previous_w=0):
    if not snapshot.phase_control_enabled or spec.kind!='charger': return desired_w,None
    state=snapshot.device_states.get(spec.id)
    if not spec.grid_phases: return 0,'Configurer la phase réseau de la borne'
    count=len(spec.grid_phases)
    requested=min(spec.max_current_a,desired_w/(spec.voltage*count))
    idle=bool(state and state.connected and state.observed_state in
              ('Available','Preparing','SuspendedEV','SuspendedEVSE','Finishing'))
    for index,phase in enumerate(spec.grid_phases):
        grid=snapshot.phase_currents.get(phase)
        if not grid or not grid.usable(snapshot.at,snapshot.sample_max_age_s):
            return 0,'Courant réseau indisponible : '+phase
        old,coherent=current_credit(snapshot,spec,index)
        own=state.currents.get('L'+str(index+1)) if state else None
        if not coherent and not idle and (not own or not own.usable(snapshot.at,snapshot.sample_max_age_s)):
            return 0,'Courant réel de recharge indisponible'
        measured=grid.value
        power=snapshot.phase_powers.get(phase)
        if power and power.usable(snapshot.at,snapshot.sample_max_age_s):
            measured=math.copysign(abs(measured),power.value) if power.value else measured
        limit=snapshot.phase_limits_a.get(phase,0)-snapshot.phase_margin_a
        if not coherent:
            # Mixed frames can maintain or reduce an existing authorization, never increase it.
            maintained=max(0,previous_w/(spec.voltage*count)-max(0,measured+extra.get(phase,0)-limit))
            requested=min(requested,maintained)
        else:
            requested=min(requested,validate_current(old,requested,measured+extra.get(phase,0),
                snapshot.phase_limits_a.get(phase,0),snapshot.phase_margin_a))
    amps=math.floor(max(0,requested)+1e-9)
    limited=amps*spec.voltage*count if amps>=spec.min_current_a else 0
    if not limited: return 0,'Limite de courant sur la phase réseau'
    # Reserve only additional current, measured current is already in the grid meter.
    for index,phase in enumerate(spec.grid_phases):
        old,_=current_credit(snapshot,spec,index)
        extra[phase]=extra.get(phase,0)+max(0,amps-old)
    return limited,('Limite de courant sur la phase réseau' if limited<desired_w else None)
