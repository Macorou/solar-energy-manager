from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.scheduling.tempo import TempoTracker, next_tempo_day_start, parse_color, red_peak
from app.settings import OffPeakWindow

TZ = 'Europe/Paris'
PARIS = ZoneInfo(TZ)


def paris(*a):
    return datetime(*a, tzinfo=PARIS).astimezone(timezone.utc)


@pytest.mark.parametrize('raw,exp', [
    ('Rouge', 'rouge'), ('ROUGE', 'rouge'), ('rouge', 'rouge'), ('Red', 'rouge'),
    ('Blanc', 'blanc'), ('White', 'blanc'), ('Bleu', 'bleu'), ('Blue', 'bleu'),
    ('unavailable', None), ('unknown', None), ('', None), (None, None), ('Inconnu', None),
])
def test_parse_color_variants(raw, exp):
    assert parse_color(raw) == exp


def test_next_tempo_day_start():
    assert next_tempo_day_start(paris(2026, 11, 6, 5, 59), TZ) == paris(2026, 11, 6, 6)
    assert next_tempo_day_start(paris(2026, 11, 6, 6, 0), TZ) == paris(2026, 11, 7, 6)
    assert next_tempo_day_start(paris(2026, 10, 25, 4, 0), TZ) == paris(2026, 10, 25, 6)


def test_last_color_kept_until_next_6am():
    t = TempoTracker()
    assert t.configured is False
    t.update('Rouge', paris(2026, 11, 6, 10), TZ)
    t.update(None, paris(2026, 11, 6, 15), TZ)
    assert t.color(paris(2026, 11, 6, 15)) == 'rouge'
    assert t.color(paris(2026, 11, 7, 6)) is None


def test_red_peak_follows_off_peak_windows():
    w = [OffPeakWindow(start='22:00', end='06:00', weekdays=[0, 1, 2, 3, 4, 5, 6])]
    d = lambda h, m=0: paris(2026, 11, 6, h, m)
    assert red_peak('rouge', d(6), w, TZ)
    assert red_peak('rouge', d(21, 59), w, TZ)
    assert not red_peak('rouge', d(22), w, TZ)
    assert not red_peak('rouge', d(3), w, TZ)
    assert not red_peak('blanc', d(10), w, TZ)
    assert all(red_peak('rouge', d(h), [], TZ) for h in range(24))


def test_stale_reading_ignored_for_two_minutes_after_6am():
    yesterday = paris(2026, 11, 6, 6, 0, 19)
    # Red then blue: yesterday's « Rouge » at 06:00:05 is not today's colour.
    t = TempoTracker()
    t.update('Rouge', paris(2026, 11, 6, 21), TZ, yesterday)
    assert t.update('Rouge', paris(2026, 11, 7, 6, 0, 5), TZ, yesterday) is False
    assert t.color(paris(2026, 11, 7, 6, 0, 5)) is None
    assert t.update('Bleu', paris(2026, 11, 7, 6, 0, 19), TZ, paris(2026, 11, 7, 6, 0, 19))
    assert t.color(paris(2026, 11, 7, 6, 0, 20)) == 'bleu'
    # Red then red: last_changed does not move, the reading counts from 06:02.
    t = TempoTracker()
    assert not t.update('Rouge', paris(2026, 11, 7, 6, 1, 59), TZ, yesterday)
    assert t.update('Rouge', paris(2026, 11, 7, 6, 2), TZ, yesterday)
    assert t.color(paris(2026, 11, 7, 6, 2)) == 'rouge'
    # Without last_changed, or later in the day, a reading is always accepted.
    assert TempoTracker().update('Rouge', paris(2026, 11, 7, 6, 0, 5), TZ)
    assert TempoTracker().update('Rouge', paris(2026, 11, 7, 10), TZ, yesterday)
    assert TempoTracker().update('Rouge', paris(2026, 11, 7, 5, 59), TZ, paris(2026, 11, 5, 6))
