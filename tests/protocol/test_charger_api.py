from fastapi.testclient import TestClient


def test_registering_charger_does_not_arm_it_and_arm_requires_verified_connection(tmp_path):
    from app.main import create_app
    from app.settings import RuntimeSettings
    client=TestClient(create_app(RuntimeSettings(data_dir=tmp_path)))
    client.post('/api/v1/setup',json={'token':(tmp_path/'bootstrap-token').read_text(),
        'username':'admin','password':'a-secure-test-password'})
    response=client.post('/api/v1/chargers',json={'id':'ev','name':'Garage','kind':'charger',
        'charge_point_id':'pulsar','armed':True})
    assert response.status_code==201
    assert not response.json()['armed']
    assert client.post('/api/v1/chargers/ev/arm',json={'confirm_control':True,
        'offline_behavior_verified':True,'capabilities_verified':True}).status_code==409
