from datetime import datetime, timezone
import io
import json
import zipfile
from fastapi.testclient import TestClient
import pytest
from app.main import create_app
from app.settings import RuntimeSettings


@pytest.fixture
def service(tmp_path):
    app=create_app(RuntimeSettings(data_dir=tmp_path,start_runtime=False))
    client=TestClient(app)
    client.post('/api/v1/setup',json={'token':(tmp_path/'bootstrap-token').read_text(),
        'username':'admin','password':'a-secure-test-password'})
    config=app.state.store.load_settings()
    config['vehicles']=[{'id':'car','name':'Peugeot'},{'id':'other','name':'Autre'}]
    app.state.store.save_settings(config)
    return app,client


def insert(app,id,start,energy=10,solar=2,cost=2,**changes):
    from app.storage.charging_sessions import SessionHistory
    row={'id':id,'source':'local','started_at':start,'ended_at':start,'active':False,
        'device_id':'wallbox','device_name':'Wallbox','vehicle_id':'car','vehicle_name':'Peugeot',
        'energy_kwh':energy,'energy_partial':False,'solar_kwh':solar,'grid_kwh':energy-solar if solar is not None else None,
        'unknown_kwh':0 if solar is not None else energy,'solar_percent':100*solar/energy if solar is not None and energy else None,
        'cost_eur':cost,'cost_partial':cost is None,'average_price_per_kwh':cost/energy if cost is not None and energy else None,
        'charge_duration_s':3600,'duration_partial':False,'soc_start':40,'soc_end':60,'soc_end_estimated':True,'updated_at':start}
    row.update(changes)
    with app.state.store.connection() as db:SessionHistory._write(db,row)


def test_weighted_solar_and_cost_are_not_averages_of_percentages(service):
    app,client=service
    insert(app,'a','2026-10-01T10:00:00+00:00',10,10,0)
    insert(app,'b','2026-10-02T10:00:00+00:00',30,0,6)
    response=client.get('/api/v1/charging-sessions?period=month&year=2026&month=10')
    assert response.status_code==200
    data=response.json();total=data['totals']
    assert total['energy_kwh']==40
    assert total['solar_percent']==25
    assert total['grid_kwh']==30
    assert total['cost_eur']==6
    assert total['average_price_per_kwh']==.15
    assert len(data['buckets'])==31
    assert data['buckets'][0]['energy']['solar']==10
    assert data['solar_years'][0]['months'][9]['solar_percent']==25
    assert data['solar_years'][0]['months'][0]['solar_percent'] is None


def test_missing_provenance_partial_meter_and_prices_never_become_fictitious_zero(service):
    app,client=service
    insert(app,'a','2026-10-01T10:00:00+00:00',10,None,None)
    insert(app,'b','2026-10-02T10:00:00+00:00',20,10,1,cost_partial=True,energy_partial=True)
    data=client.get('/api/v1/charging-sessions?period=total').json()
    total=data['totals']
    assert total['solar_percent'] is None
    assert total['unknown_kwh']==10
    assert total['energy_partial'] is True
    assert total['cost_eur'] is None
    assert total['partial_cost_eur']==1
    assert total['average_price_per_kwh'] is None
    assert data['available']['co2'] is False
    assert data['buckets'][0]['cost']['cost'] is None


def test_local_period_boundaries_dst_midnight_and_total_years(service):
    app,client=service
    insert(app,'march','2026-03-31T22:30:00+00:00') # April 1 Paris
    insert(app,'oct','2026-10-31T23:30:00+00:00') # November 1 Paris
    insert(app,'dec','2026-12-31T23:30:00+00:00') # January 1 2027 Paris
    april=client.get('/api/v1/charging-sessions?period=month&year=2026&month=4').json()
    assert [r['id'] for r in april['items']]==['march']
    assert april['buckets'][0]['totals']['energy_kwh']==10
    october=client.get('/api/v1/charging-sessions?period=month&year=2026&month=10').json()
    assert october['total']==0
    year=client.get('/api/v1/charging-sessions?period=year&year=2026').json()
    assert year['total']==2
    assert len(year['buckets'])==12
    total=client.get('/api/v1/charging-sessions?period=total').json()
    assert [b['key'] for b in total['buckets']]==['2026','2027']


def test_filters_sort_paging_totals_and_empty_rule(service):
    app,client=service
    for i in range(55):
        insert(app,str(i),f'2026-10-{i%28+1:02}T10:00:00+00:00',energy=i+1,solar=0,cost=0,
            vehicle_id='car' if i%2 else 'other',device_id='wallbox' if i%3 else 'garage')
    insert(app,'zero','2026-10-01T00:00:00+00:00',0,0,0)
    insert(app,'missing','2026-10-01T00:00:00+00:00',0,0,None,energy_kwh=None,energy_partial=True)
    data=client.get('/api/v1/charging-sessions?period=total&vehicle_id=car&device_id=wallbox&sort=energy&direction=asc&page_size=5').json()
    assert data['total']==19 # 18 matching + missing
    assert len(data['items'])==5
    assert data['totals']['count']==19
    assert data['items'][0]['energy_kwh']==2
    assert client.get('/api/v1/charging-sessions?period=total&include_empty=true').json()['total']==57
    assert client.get('/api/v1/charging-sessions?sort=energy;DROP').status_code==422


def test_edits_deletion_auth_tombstones_and_external_guard(service):
    app,client=service
    insert(app,'a','2026-10-01T10:00:00+00:00')
    assert client.patch('/api/v1/charging-sessions/a',json={'vehicle_id':'other'}).status_code==422
    assert client.patch('/api/v1/charging-sessions/a',json={'vehicle_id':'other','confirm':True}).status_code==200
    assert client.get('/api/v1/charging-sessions/a').json()['vehicle_id']=='other'
    insert(app,'a','2026-10-01T10:00:00+00:00') # checkpoint must retain override
    assert client.get('/api/v1/charging-sessions?vehicle_id=other&period=total').json()['total']==1
    assert client.request('DELETE','/api/v1/charging-sessions/a',json={'confirm':True}).status_code==200
    insert(app,'a','2026-10-01T10:00:00+00:00') # cannot resurrect
    assert client.get('/api/v1/charging-sessions/a').status_code==404
    insert(app,'active','2026-10-01T10:00:00+00:00',active=True)
    assert client.request('DELETE','/api/v1/charging-sessions/active',json={'confirm':True}).status_code==409
    insert(app,'foreign','2026-10-01T10:00:00+00:00',source='evcc')
    assert client.request('DELETE','/api/v1/charging-sessions/foreign',json={'confirm':True}).status_code==409
    client.post('/api/v1/auth/logout')
    assert client.get('/api/v1/charging-sessions').status_code==401
    assert client.get('/api/v1/charging-sessions/export?format=csv').status_code==401


def test_csv_xlsx_exports_match_filters_and_protect_formula_text(service):
    app,client=service
    insert(app,'a','2026-10-01T10:00:00+00:00',device_name='=HYPERLINK("bad")')
    insert(app,'b','2025-10-01T10:00:00+00:00')
    query='period=month&year=2026&month=10'
    csv=client.get('/api/v1/charging-sessions/export?format=csv&'+query)
    assert csv.status_code==200 and 'text/csv' in csv.headers['content-type']
    assert "'=HYPERLINK" in csv.text
    assert '2025-' not in csv.text
    xlsx=client.get('/api/v1/charging-sessions/export?format=xlsx&'+query)
    assert xlsx.status_code==200
    with zipfile.ZipFile(io.BytesIO(xlsx.content)) as doc:
        sheet=doc.read('xl/worksheets/sheet1.xml').decode()
        assert '<f>' not in sheet
        assert 'HYPERLINK' in sheet
        assert '2025-' not in sheet


def test_vehicle_sort_uses_display_name_after_assignment(service):
    app,client=service
    config=app.state.store.load_settings()
    config['vehicles'] += [{'id':'zzz','name':'Alpha'}]
    app.state.store.save_settings(config)
    insert(app,'a','2026-10-01T00:00:00+00:00',vehicle_name='Beta')
    insert(app,'b','2026-10-02T00:00:00+00:00',vehicle_name='Gamma')
    client.patch('/api/v1/charging-sessions/b',json={'vehicle_id':'zzz','confirm':True})
    data=client.get('/api/v1/charging-sessions?period=total&sort=vehicle&direction=asc').json()
    assert [s['vehicle_name'] for s in data['items']]==['Alpha','Beta']
