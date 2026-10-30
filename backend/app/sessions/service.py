"""Selection and weighted aggregates, independent of HTTP and chart rendering."""
import calendar
from datetime import datetime
from zoneinfo import ZoneInfo
from app.storage.charging_sessions import SessionHistory
from .models import SessionQuery


def totals(rows):
    energy = sum(r['energy_kwh'] or 0 for r in rows)
    solar = sum(r['solar_kwh'] or 0 for r in rows)
    grid = sum(r['grid_kwh'] or 0 for r in rows)
    unknown = max(0, energy - solar - grid)
    partial = any(r['energy_partial'] or r['energy_kwh'] is None for r in rows)
    def is_priced(row): return row['cost_eur'] is not None and not row['cost_partial'] and not row['energy_partial']
    priced = [r for r in rows if is_priced(r)]
    incomplete = [r for r in rows if not is_priced(r)]
    priced_energy = sum(r['energy_kwh'] or 0 for r in priced)
    cost = sum(r['cost_eur'] for r in priced) if priced else None
    partial_costs = [r['cost_eur'] for r in incomplete if r['cost_eur'] is not None]
    durations = [r['charge_duration_s'] for r in rows if r['charge_duration_s'] is not None]
    return dict(count=len(rows), energy_kwh=energy, energy_partial=partial,
        missing_energy_count=sum(r['energy_kwh'] is None for r in rows),
        solar_kwh=solar, grid_kwh=grid, unknown_kwh=unknown,
        solar_percent=100*solar/energy if energy > 0 and not partial and unknown < 1e-8 else None,
        cost_eur=cost, partial_cost_eur=sum(partial_costs) if partial_costs else None,
        priced_energy_kwh=priced_energy, priced_count=len(priced), cost_missing_count=len(incomplete),
        average_price_per_kwh=cost/priced_energy if cost is not None and priced_energy > 0 else None,
        charge_duration_s=sum(durations) if durations else None,
        duration_partial=any(r['duration_partial'] or r['charge_duration_s'] is None for r in rows))


class SessionService:
    def __init__(self, store, query: SessionQuery):
        self.store, self.query = store, query
        self.config = store.load_settings()
        self.zone = ZoneInfo(self.config.get('timezone', 'Europe/Paris'))
        now = datetime.now(self.zone)
        self.year, self.month = query.year or now.year, query.month or now.month

    def selection(self):
        query = self.query
        clauses, args = ['deleted=0'], []
        if query.period != 'total':
            start = datetime(self.year, self.month if query.period == 'month' else 1, 1, tzinfo=self.zone)
            if query.period == 'year': end = datetime(self.year+1, 1, 1, tzinfo=self.zone)
            else: end = datetime(self.year + (self.month == 12), self.month % 12 + 1, 1, tzinfo=self.zone)
            clauses.append('started>=? AND started<?'); args += [start.timestamp(), end.timestamp()]
        if query.device_id is not None:
            clauses.append('device_id=?'); args.append(query.device_id)
        if query.vehicle_id is not None:
            clauses.append('COALESCE(vehicle_override,vehicle_id)=?'); args.append(query.vehicle_id)
        if not query.include_empty:
            clauses.append("(active=1 OR json_extract(data,'$.energy_kwh') IS NULL OR json_extract(data,'$.energy_partial')=1 OR json_extract(data,'$.energy_kwh')>0)")
        fields = {'date':'started', 'charger':"json_extract(data,'$.device_name')",
            'vehicle':"COALESCE(vehicle_override,json_extract(data,'$.vehicle_name'))",
            'energy':"json_extract(data,'$.energy_kwh')", 'duration':"json_extract(data,'$.charge_duration_s')",
            'solar':"json_extract(data,'$.solar_percent')", 'cost':"json_extract(data,'$.cost_eur')"}
        field = fields[query.sort]
        sql = 'SELECT * FROM charging_history WHERE '+' AND '.join(clauses)+f' ORDER BY ({field} IS NULL), {field} {query.direction},id'
        names = {v['id']:v['name'] for v in self.config.get('vehicles', [])}
        with self.store.connection() as db:
            rows = [SessionHistory.decode(row, names) for row in db.execute(sql, args)]
        if query.sort=='vehicle':
            rows.sort(key=lambda row:row['vehicle_name'].casefold(), reverse=query.direction=='desc')
        return rows

    def options(self):
        with self.store.connection() as db:
            rows = db.execute('SELECT data,vehicle_override FROM charging_history WHERE deleted=0').fetchall()
        vehicles = {v['id']:v['name'] for v in self.config.get('vehicles', [])}
        chargers = {d['id']:d['name'] for d in self.config.get('devices', []) if d['kind']=='charger'}
        names = dict(vehicles)
        for raw in rows:
            row = SessionHistory.decode(raw, names)
            vehicles.setdefault(row['vehicle_id'], row['vehicle_name'])
            chargers.setdefault(row['device_id'], row['device_name'])
        return ([dict(id=k,name=v) for k,v in sorted(vehicles.items(),key=lambda x:x[1].casefold())],
            [dict(id=k,name=v) for k,v in sorted(chargers.items(),key=lambda x:x[1].casefold())])

    @staticmethod
    def grouped(rows, group):
        key, label = ('vehicle_id','vehicle_name') if group == 'vehicle' else ('device_id','device_name')
        grouped = {}
        for row in rows: grouped.setdefault(row[key], []).append(row)
        return [dict(id=k,name=v[0][label],totals=totals(v)) for k,v in sorted(grouped.items())]

    def result(self):
        rows = self.selection(); q = self.query
        groups = self.grouped(rows, q.group) if q.group != 'solar' else []
        def bucket_key(row):
            local = datetime.fromisoformat(row['started_at']).astimezone(self.zone)
            return str(local.day if q.period == 'month' else local.month if q.period == 'year' else local.year)
        grouped = {}
        for row in rows: grouped.setdefault(bucket_key(row), []).append(row)
        if q.period == 'month': keys = range(1, calendar.monthrange(self.year, self.month)[1]+1)
        elif q.period == 'year': keys = range(1, 13)
        else:
            years = [int(k) for k in grouped]
            keys = range(min(years), max(years)+1) if years else []
        buckets = []
        for key in keys:
            entries = grouped.get(str(key), []); total = totals(entries)
            if q.group == 'solar':
                energy = {'grid':total['grid_kwh'], 'solar':total['solar_kwh'], 'unknown':total['unknown_kwh']}
                cost = {'cost':total['cost_eur'] if entries else 0}
            else:
                grouped_entries = self.grouped(entries, q.group)
                energy = {g['id']:g['totals']['energy_kwh'] for g in grouped_entries}
                cost = {g['id']:g['totals']['cost_eur'] for g in grouped_entries}
            buckets.append(dict(key=str(key), energy=energy, cost=cost, totals=total))
        summary = totals(rows); vehicles, chargers = self.options()
        years = {}
        for row in rows:
            local=datetime.fromisoformat(row['started_at']).astimezone(self.zone)
            years.setdefault(local.year,{}).setdefault(local.month,[]).append(row)
        solar_years=[dict(year=year,months=[totals(months.get(m,[])) for m in range(1,13)],
            totals=totals([r for month in months.values() for r in month])) for year,months in sorted(years.items())]
        start = (q.page-1)*q.page_size
        return dict(items=rows[start:start+q.page_size], total=len(rows), page=q.page, page_size=q.page_size,
            totals=summary, buckets=buckets, groups=groups,
            by_vehicle=self.grouped(rows,'vehicle'), by_charger=self.grouped(rows,'charger'),
            solar_years=solar_years,
            vehicles=vehicles, chargers=chargers, available={'cost':summary['priced_count']>0,'co2':False},
            timezone=str(self.zone))
