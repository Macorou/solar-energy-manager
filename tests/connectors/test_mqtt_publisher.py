import json
from app import VERSION
from app.connectors.mqtt.entities import Entity
from app.connectors.mqtt.publisher import Publisher
from app.storage.database import SQLiteStore


class FakeClient:
    def __init__(self): self.sent = []
    async def publish(self, topic, payload, retain): self.sent.append((topic, payload, retain))
    def on(self, topic): return [(p, r) for t, p, r in self.sent if t == topic]


def sensor(group='site', key='price', value='0.110', **kw):
    base = dict(group=group, key=key, component='sensor', name='Prix', device_name='SEM – Installation',
                value=value, unit='EUR/kWh', state_class='measurement', precision=3)
    return Entity(**(base | kw))


def make(tmp_path, store=None):
    client = FakeClient()
    return client, Publisher(client, 'sem', 'homeassistant', store or SQLiteStore(tmp_path / 'db'))


async def test_discovery_payload_shape(tmp_path):
    client, publisher = make(tmp_path)
    await publisher.announce([sensor()])
    topic, payload, retain = client.sent[0]
    assert topic == 'homeassistant/sensor/sem_site/price/config' and retain is True
    data = json.loads(payload)
    assert data['unique_id'] == 'sem_site_price' and 'object_id' not in data
    assert data['unit_of_measurement'] == 'EUR/kWh' and data['suggested_display_precision'] == 3
    assert data['state_topic'] == 'sem/site/price/state'
    assert data['availability'] == [{'topic': 'sem/status'}, {'topic': 'sem/site/price/available'}]
    assert data['availability_mode'] == 'all'
    assert data['device'] == {'identifiers': ['sem_site'], 'name': 'SEM – Installation',
                              'manufacturer': 'Solar Energy Manager', 'model': 'SEM', 'sw_version': VERSION}
    assert 'json_attributes_topic' not in data
    await publisher.announce([sensor(attributes={'source': 'relevée'})])
    assert json.loads(client.sent[-1][1])['json_attributes_topic'] == 'sem/site/price/attributes'


async def test_publish_state_attributes_and_status(tmp_path):
    client, publisher = make(tmp_path)
    entity = sensor(attributes={'source': 'estimée'})
    await publisher.publish([entity], 0.0)
    assert client.on('sem/status') == [('online', True)]
    assert client.on('sem/site/price/state') == [('0.110', True)]
    assert client.on('sem/site/price/available') == [('online', True)]
    assert [json.loads(p) for p, r in client.on('sem/site/price/attributes')] == [{'source': 'estimée'}]
    assert client.on('sem/site/price/attributes')[0][1] is True
    count = len(client.sent)
    await publisher.publish([entity], 1.0)
    assert len(client.sent) == count


async def test_unavailable_value_publishes_offline_availability_not_zero(tmp_path):
    client, publisher = make(tmp_path)
    await publisher.publish([sensor(value=None)], 0.0)
    assert client.on('sem/site/price/state') == []
    assert client.on('sem/site/price/available') == [('offline', True)]
    await publisher.publish([sensor(value=None)], 1.0)
    assert client.on('sem/site/price/available') == [('offline', True)]
    await publisher.publish([sensor(value='0.200')], 2.0)
    assert client.on('sem/site/price/available')[-1] == ('online', True)
    assert client.on('sem/site/price/state') == [('0.200', True)]


async def test_throttled_entity_waits_ten_seconds(tmp_path):
    client, publisher = make(tmp_path)
    def power(v): return sensor(key='power', value=v, throttled=True)
    def text(v): return sensor(key='mode', value=v)
    await publisher.publish([power('1000'), text('Manuel')], 0.0)
    await publisher.publish([power('1200'), text('Pause')], 5.0)
    assert client.on('sem/site/power/state') == [('1000', True)]
    assert client.on('sem/site/mode/state') == [('Manuel', True), ('Pause', True)]
    await publisher.publish([power('1200'), text('Pause')], 10.0)
    assert client.on('sem/site/power/state') == [('1000', True), ('1200', True)]


async def test_removed_device_is_cleared_even_after_restart(tmp_path):
    store = SQLiteStore(tmp_path / 'db')
    await make(tmp_path, store)[1].announce([sensor(), sensor('ev', 'power'), sensor('ev', 'state')])
    assert store.get('mqtt_announced', []) == [['sensor', 'site', 'price'], ['sensor', 'ev', 'power'],
                                               ['sensor', 'ev', 'state']]
    client, publisher = make(tmp_path, store)
    await publisher.announce([sensor()])
    cleared = {t for t, p, r in client.sent if p == '' and r is True}
    assert cleared == {'homeassistant/sensor/sem_ev/power/config', 'homeassistant/sensor/sem_ev/state/config'}
    assert store.get('mqtt_announced', []) == [['sensor', 'site', 'price']]


async def test_renamed_device_updates_discovery_name(tmp_path):
    client, publisher = make(tmp_path)
    await publisher.announce([sensor('ev', 'power', device_name='SEM – Wallbox')])
    await publisher.announce([sensor('ev', 'power', device_name='SEM – Garage')])
    names = [json.loads(p)['device']['name'] for t, p, r in client.sent if p]
    assert names == ['SEM – Wallbox', 'SEM – Garage']
    assert [p for t, p, r in client.sent if p == ''] == []


async def test_clear_removes_everything(tmp_path):
    store = SQLiteStore(tmp_path / 'db')
    client, publisher = make(tmp_path, store)
    await publisher.announce([sensor(), sensor('ev', 'power')])
    client.sent.clear()
    await publisher.clear()
    assert {t for t, p, r in client.sent if p == '' and r} == {
        'homeassistant/sensor/sem_site/price/config', 'homeassistant/sensor/sem_ev/power/config'}
    assert store.get('mqtt_announced', None) == []


async def test_empty_text_never_deletes_the_retained_state(tmp_path):
    client, publisher = make(tmp_path)
    await publisher.publish([sensor(key='problem', value='', unit=None), sensor(key='reason', value='Pause')], 0.0)
    assert client.on('sem/site/problem/state') == [('Aucun', True)]
    assert client.on('sem/site/problem/available') == [('online', True)]
    await publisher.publish([sensor(key='problem', value='', unit=None)], 1.0)
    assert len(client.on('sem/site/problem/state')) == 1
    await publisher.publish([sensor(key='problem', value='Service indisponible', unit=None)], 2.0)
    await publisher.publish([sensor(key='problem', value='', unit=None)], 3.0)
    assert [p for p, r in client.on('sem/site/problem/state')] == ['Aucun', 'Service indisponible', 'Aucun']
    assert not [t for t, p, r in client.sent if t.endswith('/state') and p == '']


async def test_announce_records_configs_before_sending_them(tmp_path):
    store = SQLiteStore(tmp_path / 'db')
    await make(tmp_path, store)[1].announce([sensor('old', 'power')])
    class Failing(FakeClient):
        async def publish(self, topic, payload, retain):
            if 'sem_ev' in topic: raise ConnectionError('broker down')
            await super().publish(topic, payload, retain)
    publisher = Publisher(Failing(), 'sem', 'homeassistant', store)
    try: await publisher.announce([sensor(), sensor('ev', 'power')])
    except ConnectionError: pass
    assert store.get('mqtt_announced', []) == [['sensor', 'old', 'power'], ['sensor', 'site', 'price'],
                                               ['sensor', 'ev', 'power']]


async def test_discovery_of_command_entities(tmp_path):
    client, publisher = make(tmp_path)
    select = Entity('ev', 'car_mode', 'select', 'Mode de la voiture', 'SEM – Wallbox', 'Auto', command=True,
                    options=('Auto', 'Manuel', 'Pause'))
    number = Entity('ev', 'program_week_target', 'number', 'Objectif – Semaine', 'SEM – Wallbox', '80', unit='%',
                    command=True, minimum=1, maximum=100, step=1)
    await publisher.announce([select, number, sensor()])
    config = {t: json.loads(p) for t, p, r in client.sent}
    data = config['homeassistant/select/sem_ev/car_mode/config']
    assert data['command_topic'] == 'sem/ev/car_mode/set' and data['options'] == ['Auto', 'Manuel', 'Pause']
    assert 'min' not in data
    data = config['homeassistant/number/sem_ev/program_week_target/config']
    assert data['command_topic'] == 'sem/ev/program_week_target/set'
    assert (data['min'], data['max'], data['step'], data['unit_of_measurement']) == (1, 100, 1, '%')
    assert 'options' not in data
    assert 'command_topic' not in config['homeassistant/sensor/sem_site/price/config']


async def test_select_unknown_state_is_published_as_None(tmp_path):
    client, publisher = make(tmp_path)
    select = Entity('ev', 'car_mode', 'select', 'Mode de la voiture', 'SEM – Wallbox', 'None', command=True,
                    options=('Auto', 'Manuel', 'Pause'))
    await publisher.publish([select], 0.0)
    assert client.on('sem/ev/car_mode/available') == [('online', True)]
    assert client.on('sem/ev/car_mode/state') == [('None', True)]
