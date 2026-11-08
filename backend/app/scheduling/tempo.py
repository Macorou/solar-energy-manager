import unicodedata
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.scheduling.tariff_windows import is_off_peak

COLORS = {'bleu': 'bleu', 'blue': 'bleu', 'blanc': 'blanc', 'white': 'blanc', 'rouge': 'rouge', 'red': 'rouge'}


def parse_color(raw):
    if not raw:
        return None
    text = unicodedata.normalize('NFKD', str(raw)).encode('ascii', 'ignore').decode().strip().lower()
    return COLORS.get(text)


# Home Assistant's RTE sensor changes about 20 s after 06:00; until then it shows yesterday's colour.
STALE_GRACE_S = 120


def tempo_day_start(now, timezone_name):
    zone = ZoneInfo(timezone_name)
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), time(6), tzinfo=zone)
    if start > local:
        start = datetime.combine(local.date() - timedelta(days=1), time(6), tzinfo=zone)
    return start.astimezone(timezone.utc)


def next_tempo_day_start(now, timezone_name):
    zone = ZoneInfo(timezone_name)
    local = now.astimezone(zone)
    day = local.date()
    start = datetime.combine(day, time(6), tzinfo=zone)
    if start <= local:
        start = datetime.combine(day + timedelta(days=1), time(6), tzinfo=zone)
    return start.astimezone(timezone.utc)


class TempoTracker:
    def __init__(self):
        self.configured = False
        self._color = None
        self._valid_until = None

    def update(self, raw, now, timezone_name, changed_at=None):
        """Keep a valid reading for the current Tempo day; True when it was accepted.

        Just after 06:00, a reading last changed before 06:00 may still be yesterday's colour: it is
        ignored for STALE_GRACE_S. After that it is today's (the same colour two days running does
        not change last_changed)."""
        color = parse_color(raw)
        if color is None or self.stale(now, timezone_name, changed_at):
            return False
        self._color = color
        self._valid_until = next_tempo_day_start(now, timezone_name)
        return True

    @staticmethod
    def stale(now, timezone_name, changed_at):
        start = tempo_day_start(now, timezone_name)
        return bool(changed_at and changed_at < start and (now - start).total_seconds() < STALE_GRACE_S)

    def color(self, now):
        if self._color is not None and self._valid_until is not None and now < self._valid_until:
            return self._color
        return None


def red_peak(color, now, windows, timezone_name):
    return color == 'rouge' and not is_off_peak(now, windows, timezone_name)
