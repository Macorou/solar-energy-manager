"""Physical enforcement check, independent of the OCPP pilot acknowledgment."""
import math


def unapplied_overload(snapshot,spec,commanded_w):
    state=snapshot.device_states.get(spec.id)
    if not commanded_w or not state or not state.connected or state.observed_state!='Charging':return False
    fresh=lambda sample:bool(sample and sample.usable(snapshot.at,snapshot.sample_max_age_s))
    phases=len(spec.grid_phases) or 1
    current=[state.currents.get('L'+str(i+1)) for i in range(phases)]
    exceeded=(max(sample.value for sample in current)>commanded_w/(spec.voltage*phases)+.5
        if all(fresh(sample) for sample in current) else
        fresh(state.observed_power) and state.observed_power.value>commanded_w+max(100,commanded_w*.1))
    if not exceeded:return False
    if (snapshot.site_limit_w is not None and fresh(snapshot.grid)
        and snapshot.grid.value>snapshot.site_limit_w):return True
    if snapshot.phase_control_enabled:
        for phase in spec.grid_phases:
            sample=snapshot.phase_currents.get(phase)
            if not fresh(sample):continue
            value=sample.value;power=snapshot.phase_powers.get(phase)
            if fresh(power) and power.value:value=math.copysign(abs(value),power.value)
            if value>snapshot.phase_limits_a.get(phase,0)-snapshot.phase_margin_a+.05:return True
    return False
