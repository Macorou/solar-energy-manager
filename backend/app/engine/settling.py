"""Frames mixed for a few seconds after the measured power of a device steps.

A station announces a pause at once and a dedicated meter is read on its own schedule,
while the site and phase meters keep their last reading: until they are read again they
still contain the old draw (or not yet the new one). Counting the device at its new
power against such a reading counts it twice, or not at all.
"""
POWER_STEP_W = 300
# Bound for a meter that is never read again (it reports on change only and did not change).
SETTLING_MAX_S = 30


class PowerSteps:
    def __init__(self):
        self.seen = {}   # device -> last usable measured power
        self.steps = {}  # device -> when its step was seen, and the date of each meter reading behind it

    @staticmethod
    def stamps(snapshot):
        meters = {'grid': snapshot.grid} | dict(snapshot.phase_currents)
        return {name: sample.measured_at for name, sample in meters.items() if sample and sample.measured_at}

    def update(self, snapshot, mono):
        stamps = self.stamps(snapshot)
        for key, state in snapshot.device_states.items():
            power = state.observed_power
            if not (power and power.usable(snapshot.at, snapshot.sample_max_age_s)):
                continue
            last, self.seen[key] = self.seen.get(key), power.value
            if last is not None and abs(power.value-last) >= POWER_STEP_W and key not in self.steps:
                # Home Assistant dates all its measures on one clock: a site reading not older than
                # the device's own is already up to date. A station's clock cannot be compared.
                same_clock = not power.source.startswith('OCPP')
                behind = {name: stamp for name, stamp in stamps.items()
                          if not (same_clock and stamp >= power.measured_at)}
                if behind:
                    self.steps[key] = {'at': mono, 'stamps': behind}
        for key, step in list(self.steps.items()):
            read_again = all(stamps.get(name) != stamp for name, stamp in step['stamps'].items())
            if read_again or mono-step['at'] >= SETTLING_MAX_S:
                del self.steps[key]

    def stale(self, snapshot, meter, device_id=None) -> bool:
        """True while `meter` has not been read again since a step of `device_id` (or of any device)."""
        stamp = self.stamps(snapshot).get(meter)
        return stamp is not None and any(step['stamps'].get(meter) == stamp
            for key, step in self.steps.items() if device_id in (None, key))
