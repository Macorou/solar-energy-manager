from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.settings import ChargeProgram


def test_weekday_goal_starts_previous_evening_and_closes_network_at_deadline():
    from app.scheduling.recurrence import occurrences_for
    from app.scheduling.authorization import select_authorization
    zone=ZoneInfo('Europe/Paris')
    program=ChargeProgram(id='work',vehicle_id='car')
    jobs=occurrences_for(program,datetime(2026,10,26,tzinfo=zone),datetime(2026,11,2,tzinfo=zone),'Europe/Paris')
    assert len(jobs)==5
    monday=jobs[0]
    assert monday.network_start_at.astimezone(zone).isoformat()=='2026-10-25T22:00:00+01:00'
    before=select_authorization('car',datetime(2026,10,25,21,59,tzinfo=zone),jobs,80)
    assert not before.allow_grid and before.allow_solar
    opening=select_authorization('car',datetime(2026,10,25,22,tzinfo=zone),jobs,80)
    assert opening.allow_grid and opening.target_soc==80
    assert not select_authorization('car',monday.deadline_at,jobs[:1],80).allow_grid


def test_future_higher_goal_does_not_apply_before_solar_horizon():
    from app.scheduling.recurrence import occurrences_for
    from app.scheduling.authorization import select_authorization
    zone=ZoneInfo('Europe/Paris')
    program=ChargeProgram(id='trip',vehicle_id='car',weekdays=[4],target_soc=100)
    jobs=occurrences_for(program,datetime(2026,10,26,tzinfo=zone),datetime(2026,10,31,tzinfo=zone),'Europe/Paris')
    assert select_authorization('car',datetime(2026,10,26,12,tzinfo=zone),jobs,80).target_soc==80
    early=select_authorization('car',datetime(2026,10,29,12,tzinfo=zone),jobs,80)
    assert early.target_soc==100 and early.allow_solar and not early.allow_grid


def test_equal_deadline_uses_larger_goal():
    from app.scheduling.recurrence import occurrences_for
    from app.scheduling.authorization import select_authorization
    from dataclasses import replace
    now=datetime(2026,10,26,tzinfo=timezone.utc)
    one=occurrences_for(ChargeProgram(id='work',vehicle_id='car'),now,datetime(2026,10,27,tzinfo=timezone.utc),'Europe/Paris')[0]
    two=replace(one,id='second',target_soc=90)
    assert select_authorization('car',one.network_start_at,[one,two],80).target_soc==90
