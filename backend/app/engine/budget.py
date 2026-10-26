from app.domain.site import SiteSnapshot


def solar_budget_w(snapshot: SiteSnapshot) -> float | None:
    if not snapshot.grid or not snapshot.grid.usable(snapshot.at, snapshot.sample_max_age_s):
        return None
    managed = 0.0
    for state in snapshot.device_states.values():
        if not state.observed_power or not state.observed_power.usable(snapshot.at, snapshot.sample_max_age_s):
            return None
        managed += max(0, state.observed_power.value)
    return max(0, managed - snapshot.grid.value - snapshot.export_margin_w)

