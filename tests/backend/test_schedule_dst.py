from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.settings import ChargeProgram


def test_spring_gap_moves_to_first_valid_local_time():
    from app.scheduling.recurrence import occurrences_for
    zone=ZoneInfo('Europe/Paris')
    program=ChargeProgram(id='dst',vehicle_id='car',weekdays=[6],deadline='02:30')
    jobs=occurrences_for(program,datetime(2026,3,29,tzinfo=zone),datetime(2026,3,30,tzinfo=zone),'Europe/Paris')
    assert len(jobs)==1
    assert jobs[0].deadline_at.astimezone(zone).strftime('%H:%M')=='03:00'


def test_autumn_repetition_runs_only_first_occurrence():
    from app.scheduling.recurrence import occurrences_for
    zone=ZoneInfo('Europe/Paris')
    program=ChargeProgram(id='dst',vehicle_id='car',weekdays=[6],deadline='02:30')
    jobs=occurrences_for(program,datetime(2026,10,25,tzinfo=zone),datetime(2026,10,26,tzinfo=zone),'Europe/Paris')
    assert len(jobs)==1
    assert jobs[0].deadline_at.isoformat()=='2026-10-25T00:30:00+00:00'
