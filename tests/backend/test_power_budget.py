from datetime import datetime, timezone, timedelta
from app.domain.measurements import Sample
from app.domain.devices import DeviceState


def test_budget_includes_managed_load_once_and_export_margin():
    from app.domain.site import SiteSnapshot
    from app.engine.budget import solar_budget_w
    now = datetime.now(timezone.utc)
    sample = lambda value: Sample(value, 'W', 'test', now, now)
    site = SiteSnapshot(at=now, grid=sample(-500),
        device_states={'ev': DeviceState('ev', sample(3000), 'charging', True)}, export_margin_w=100)
    assert solar_budget_w(site) == 3400


def test_unknown_or_stale_measurement_is_not_zero():
    from app.domain.site import SiteSnapshot
    from app.engine.budget import solar_budget_w
    now = datetime.now(timezone.utc)
    assert solar_budget_w(SiteSnapshot(at=now, grid=Sample(None,'W','grid',now,now))) is None
    assert solar_budget_w(SiteSnapshot(at=now, grid=Sample(-2000,'W','grid',now-timedelta(seconds=90),now))) is None
