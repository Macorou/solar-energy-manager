from datetime import time, timedelta
from zoneinfo import ZoneInfo


def is_off_peak(now, windows, timezone_name):
    local = now.astimezone(ZoneInfo(timezone_name))
    current = local.time().replace(tzinfo=None)
    for window in windows:
        start,end=time.fromisoformat(window.start),time.fromisoformat(window.end)
        if start<end:
            if local.weekday() in window.weekdays and start<=current<end:
                return True
        else:
            anchor = local.date() if current>=start else local.date()-timedelta(days=1)
            if anchor.weekday() in window.weekdays and (current>=start or current<end or start==end):
                return True
    return False

