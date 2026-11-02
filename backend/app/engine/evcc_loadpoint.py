"""Fixed-phase PV controller ported from EVCC core/loadpoint.go (9404d825).

Copyright (c) evcc.io (andig, naltatis, premultiply), MIT.
See docs/third-party/evcc-MIT.txt. Policy eligibility and circuit caps are callers.
"""


class PvController:
    def __init__(self):
        self.timer = None
        self.timer_kind = None
        self.reason = 'Surplus insuffisant'

    def reset(self):
        self.timer = self.timer_kind = None

    def current(self, *, now, site_power_w, voltage, phases, charging, enabled,
                actual_a, offered_a, minimum_a, maximum_a, enable_delay_s,
                disable_delay_s, enable_threshold_w=0, disable_threshold_w=0,
                hold_minimum=False):
        effective = 0 if not charging else offered_a if actual_a is None else min(actual_a+2,offered_a)
        target = max(0,effective-site_power_w/(voltage*phases))
        if enabled and target<minimum_a:
            if site_power_w>=disable_threshold_w:
                if self.timer_kind!='disable':
                    self.timer,self.timer_kind=now,'disable'
                if now-self.timer>=disable_delay_s and not hold_minimum:
                    self.reset()
                    self.reason='Surplus insuffisant : suspension'
                    return 0
                self.reason='Passage de nuage : temporisation'
            else:
                self.reset()
                self.reason='Surplus solaire'
            return minimum_a
        if not enabled:
            threshold=(enable_threshold_w if enable_threshold_w else
                       (effective-minimum_a)*voltage*phases)
            if site_power_w<=threshold:
                if self.timer_kind!='enable':
                    self.timer,self.timer_kind=now,'enable'
                if now-self.timer>=enable_delay_s:
                    self.reset()
                    self.reason='Surplus solaire'
                    return minimum_a
                self.reason=f'Attente de surplus stable ({max(0,enable_delay_s-(now-self.timer)):.0f} s)'
            else:
                self.reset()
                self.reason='Surplus insuffisant'
            return 0
        self.reset()
        self.reason='Surplus solaire'
        return min(target,maximum_a)
