"""Select the actual OCPP meter before a potentially delayed HA cloud sensor."""
from app.domain.measurements import Sample,Quality


def select_power(state,ha_power,config,now,max_age):
    native=state.observed_power
    if native and native.usable(now,max_age):
        return native
    currents=[state.currents.get('L'+str(i+1)) for i in range(config.phases)]
    if state.connected and all(sample and sample.usable(now,max_age) for sample in currents):
        received=min(sample.availability_at for sample in currents)
        measured=min(sample.measured_at for sample in currents)
        return Sample(sum(sample.value for sample in currents)*config.voltage,'W',
            'OCPP puissance calculée depuis le courant',measured,received,Quality.ESTIMATED,checked_at=received)
    return ha_power or native
