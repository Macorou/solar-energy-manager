from app.domain.site import SiteSnapshot


def measurements_coherent(snapshot: SiteSnapshot) -> bool:
    samples=[snapshot.grid]+[state.observed_power for state in snapshot.device_states.values()]
    if not all(sample and sample.usable(snapshot.at,snapshot.sample_max_age_s) for sample in samples):
        return False
    stamps=[sample.availability_at for sample in samples]
    # Independent successful source reads need not land in the same 2s window.
    # Unchecked historical frames remain conservative about causal ordering.
    return all(sample.checked_at is not None for sample in samples) or (max(stamps)-min(stamps)).total_seconds()<=2


def power_coherent(snapshot: SiteSnapshot) -> bool:
    return measurements_coherent(snapshot) and not snapshot.transition_blocked


def solar_budget_w(snapshot: SiteSnapshot) -> float | None:
    if not power_coherent(snapshot): return None
    if not snapshot.grid or not snapshot.grid.usable(snapshot.at, snapshot.sample_max_age_s):
        return None
    managed = 0.0
    for state in snapshot.device_states.values():
        if not state.observed_power or not state.observed_power.usable(snapshot.at, snapshot.sample_max_age_s):
            return None
        managed += max(0, state.observed_power.value)
    return max(0, managed - snapshot.grid.value - snapshot.export_margin_w)

