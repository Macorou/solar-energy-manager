from datetime import datetime
from zoneinfo import ZoneInfo
from app.settings import OffPeakWindow


def test_multiple_windows_and_previous_day_membership_without_ha():
    from app.scheduling.tariff_windows import is_off_peak
    zone=ZoneInfo('Europe/Paris')
    windows=[OffPeakWindow(start='22:00',end='06:00',weekdays=[0]),OffPeakWindow(start='12:00',end='14:00')]
    assert is_off_peak(datetime(2026,10,27,1,tzinfo=zone),windows,'Europe/Paris')
    assert not is_off_peak(datetime(2026,10,27,6,tzinfo=zone),windows,'Europe/Paris')
    assert is_off_peak(datetime(2026,10,27,13,tzinfo=zone),windows,'Europe/Paris')
    assert not is_off_peak(datetime(2026,10,27,22,tzinfo=zone),windows,'Europe/Paris')
