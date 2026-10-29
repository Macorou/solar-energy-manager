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
        and grid.usable(snapshot.at,snapshot.sample_max_age_s))
    return (max(0,own.value) if coherent else 0),coherent


def phase_power_limit(snapshot,spec,desired_w,extra,previous_w=0,waiting_current=False,waiting_baseline_w=None):
    if not snapshot.phase_control_enabled or spec.kind!='charger': return desired_w,None
    state=snapshot.device_states.get(spec.id)
    if not spec.grid_phases: return 0,'Configurer la phase réseau de la borne'
    count=len(spec.grid_phases)
    requested=min(spec.max_current_a,desired_w/(spec.voltage*count))
    if waiting_current:requested=min(requested,max(0,previous_w/(spec.voltage*count)))
    idle=bool(state and state.connected and state.observed_state in
              ('Available','Preparing','SuspendedEV','SuspendedEVSE','Finishing'))
    for index,phase in enumerate(spec.grid_phases):
        grid=snapshot.phase_currents.get(phase)
        if not grid or not grid.usable(snapshot.at,snapshot.sample_max_age_s):
            return 0,'Courant réseau indisponible : '+phase
        old,coherent=current_credit(snapshot,spec,index)
        own=state.currents.get('L'+str(index+1)) if state else None
        missing=not own or not own.usable(snapshot.at,snapshot.sample_max_age_s)
        if missing and (not idle or previous_w>0) and not (waiting_current and previous_w>0):
            return 0,'Courant réel de recharge indisponible'
        measured=grid.value
        power=snapshot.phase_powers.get(phase)
        if power and power.usable(snapshot.at,snapshot.sample_max_age_s):
            measured=math.copysign(abs(measured),power.value) if power.value else measured
        limit=snapshot.phase_limits_a.get(phase,0)-snapshot.phase_margin_a
        if not coherent:
            # During initial telemetry grace use a fixed startup credit, never
            # the repeatedly reduced command. Actual current replaces it ASAP.
            old=max(0,(waiting_baseline_w if waiting_baseline_w is not None else previous_w)/(spec.voltage*count))
        requested=min(requested,validate_current(old,requested,measured+extra.get(phase,0),
            snapshot.phase_limits_a.get(phase,0),snapshot.phase_margin_a))
    if requested<spec.min_current_a and desired_w>=spec.min_current_a*spec.voltage*count:
        # EVCC's nominal-minimum exception: 5.9A measured for a 6A offer on a
        # full (not overloaded) circuit must not disable a running car.
        if (state and state.observed_state.lower()=='charging'
            and previous_w>=spec.min_current_a*spec.voltage*count
            and all(snapshot.phase_currents[p].value+extra.get(p,0)<=
                    snapshot.phase_limits_a.get(p,0)-snapshot.phase_margin_a for p in spec.grid_phases)):
            requested=spec.min_current_a
    amps=math.floor(max(0,requested)*10+1e-9)/10
    limited=amps*spec.voltage*count if amps>=spec.min_current_a else 0
    if not limited: return 0,'Limite de courant sur la phase réseau'
    # Reserve only additional current, measured current is already in the grid meter.
    for index,phase in enumerate(spec.grid_phases):
        old,_=current_credit(snapshot,spec,index)
        extra[phase]=extra.get(phase,0)+max(0,amps-old)
    return limited,('Attente du premier courant de recharge (5 min maximum)'
        if waiting_current and not idle and limited>=previous_w else
        'Limite de courant sur la phase réseau' if limited<desired_w else None)
