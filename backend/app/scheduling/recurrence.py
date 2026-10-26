from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from app.domain.schedules import ChargeOccurrence


def resolve_local(day, clock_time, zone):
    naive = datetime.combine(day,clock_time)
    for _ in range(181):
        candidate = naive.replace(tzinfo=zone,fold=0)
        utc = candidate.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None)==naive:
            return utc
        naive += timedelta(minutes=1)
    raise ValueError('Heure locale non résolue')


def occurrences_for(program, start, end, timezone_name):
    if not program.enabled:
        return []
    if not start.tzinfo or not end.tzinfo:
        raise ValueError('Les dates doivent inclure un fuseau')
    zone = ZoneInfo(timezone_name)
    day, last = start.astimezone(zone).date(), end.astimezone(zone).date()
    result = []
    earliest, deadline = time.fromisoformat(program.earliest_start),time.fromisoformat(program.deadline)
    while day<=last:
        if day.weekday() in program.weekdays:
            due = resolve_local(day,deadline,zone)
            if start<=due<end:
                network = resolve_local(day-timedelta(days=earliest>=deadline),earliest,zone)
                solar = min(network,due-timedelta(hours=program.solar_horizon_hours)) if program.solar_early else network
                result.append(ChargeOccurrence(f'{program.id}:{due.isoformat()}',program.id,program.vehicle_id,
                    network,solar,due,program.target_soc))
        day += timedelta(days=1)
    return result

