"""Port of EVCC core/soc/estimator.go (9404d825, MIT).

Copyright (c) evcc.io (andig, naltatis, premultiply).
Full license and source reference: docs/third-party/evcc-MIT.txt.
The calculation deliberately has no Peugeot timestamp input.
"""
import math


class SocEstimator:
    def __init__(self, capacity_kwh):
        self.capacity = capacity_kwh * 1000
        self.energy_per_soc_step = self.capacity / .85 / 100
        self.vehicle_soc = 0.
        self.initial_soc = 0.
        self.initial_energy = 0.
        self.prev_soc = 0.
        self.prev_charged_energy = 0.
        self.sampled = False

    @property
    def virtual_capacity(self):
        return max(self.capacity, self.energy_per_soc_step * 100)

    def soc(self, fetched_soc, charged_energy_wh):
        if fetched_soc is None:
            delta = max(charged_energy_wh, 0) - self.prev_charged_energy
            if self.sampled and delta >= 0:
                self.vehicle_soc = min(max(self.vehicle_soc,
                    self.prev_soc + delta / self.energy_per_soc_step), 100)
            return self.vehicle_soc

        charged_energy_wh = max(charged_energy_wh, 0)
        soc_delta = fetched_soc - self.prev_soc
        energy_delta = charged_energy_wh - self.prev_charged_energy
        if self.sampled and soc_delta == 0 and energy_delta >= 0:
            self.vehicle_soc = min(fetched_soc + energy_delta / self.energy_per_soc_step, 100)
            return self.vehicle_soc

        self.sampled = True
        self.vehicle_soc = fetched_soc
        if self.initial_soc == 0:
            self.initial_soc = self.vehicle_soc
            self.initial_energy = charged_energy_wh
        soc_diff = self.vehicle_soc - self.initial_soc
        energy_diff = charged_energy_wh - self.initial_energy
        if soc_diff > 10 and energy_diff > 0:
            self.energy_per_soc_step = energy_diff / soc_diff
        self.prev_soc = self.vehicle_soc
        self.prev_charged_energy = charged_energy_wh
        return self.vehicle_soc

    def dump(self):
        return dict(vars(self), version=1)

    @classmethod
    def restore(cls, capacity_kwh, state):
        result = cls(capacity_kwh)
        if not isinstance(state, dict) or state.get('version') != 1 or state.get('capacity') != result.capacity:
            return result
        fields = [key for key in vars(result) if key != 'sampled']
        if not all(isinstance(state.get(key), (int, float)) and math.isfinite(state[key])
                   and state[key] >= 0 for key in fields):
            return result
        if state['energy_per_soc_step'] <= 0 or any(state[key] > 100
                for key in ('vehicle_soc','initial_soc','prev_soc')):
            return result
        for key in fields:
            setattr(result, key, state[key])
        result.sampled = state.get('sampled') is True
        return result
