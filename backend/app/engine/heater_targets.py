from app.engine.hysteresis import Timers


class HeaterTargets:
    """Choose a setpoint without changing the electrical budget or device settings."""

    def __init__(self):
        self.solar_active=set()
        self.timers=Timers()

    def select(self, key, policy, network, solar_available, coherent, minimum_w, tolerance_w, mono):
        solar_target=policy.solar_target if policy.solar_target is not None else policy.target
        if policy.mode in ('off','manual'):
            self.solar_active.discard(key)
            self.timers.reached(key+':start',False,0,mono)
            self.timers.reached(key+':stop',False,0,mono)
            return policy.target,'grid'
        if not network:
            return solar_target,'solar'
        if coherent:
            enough=solar_available>=max(minimum_w,policy.start_surplus_w)
            if self.timers.reached(key+':start',enough,policy.start_delay_s,mono):
                self.solar_active.add(key)
            deficient=solar_available+tolerance_w<minimum_w
            if self.timers.reached(key+':stop',deficient,policy.stop_delay_s,mono):
                self.solar_active.discard(key)
        # Mixed or pending frames can preserve a selection, never raise it.
        return (solar_target,'solar') if key in self.solar_active else (policy.target,'grid')
