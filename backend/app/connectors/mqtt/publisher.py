import json
from app.connectors.mqtt.entities import Entity

THROTTLE_S = 10
ANNOUNCED_KEY = 'mqtt_announced'
EMPTY_TEXT = 'Aucun'


class Publisher:
    """Turns entities into retained MQTT messages; the client only needs `publish(topic, payload, retain)`."""

    def __init__(self, client, prefix: str, discovery_prefix: str, store):
        self.client, self.prefix, self.discovery_prefix, self.store = client, prefix, discovery_prefix, store
        self.status_sent = False
        self.last = {}  # (group, key) -> {'value', 'available', 'attributes', 'mono'}

    def topic(self, entity, leaf): return f'{self.prefix}/{entity.group}/{entity.key}/{leaf}'

    def config_topic(self, component, group, key):
        return f'{self.discovery_prefix}/{component}/sem_{group}/{key}/config'

    def discovery(self, entity: Entity):
        uid = f'sem_{entity.group}_{entity.key}'
        data = {'name': entity.name, 'unique_id': uid, 'state_topic': self.topic(entity, 'state'),
            'availability': [{'topic': f'{self.prefix}/status'}, {'topic': self.topic(entity, 'available')}],
            'availability_mode': 'all',
            'device': {'identifiers': [f'sem_{entity.group}'], 'name': entity.device_name,
                'manufacturer': 'Solar Energy Manager', 'model': 'SEM'}}
        optional = {'unit_of_measurement': entity.unit, 'device_class': entity.device_class,
            'state_class': entity.state_class, 'suggested_display_precision': entity.precision}
        data |= {key: value for key, value in optional.items() if value is not None}
        if entity.attributes is not None: data['json_attributes_topic'] = self.topic(entity, 'attributes')
        if entity.command:
            data['command_topic'] = self.topic(entity, 'set')
            if entity.component == 'select': data['options'] = list(entity.options or ())
            if entity.component == 'number':
                data |= {'min': entity.minimum, 'max': entity.maximum, 'step': entity.step}
        return data

    async def announce(self, entities: list[Entity]) -> None:
        current = [[entity.component, entity.group, entity.key] for entity in entities]
        previous = self.store.get(ANNOUNCED_KEY, [])
        # Record the new configs before sending them so a failure mid-loop cannot orphan any.
        self.store.set(ANNOUNCED_KEY, previous + [item for item in current if item not in previous])
        for entity in entities:
            await self.client.publish(self.config_topic(entity.component, entity.group, entity.key),
                json.dumps(self.discovery(entity), ensure_ascii=False), True)
        for item in previous:
            if item not in current: await self.client.publish(self.config_topic(*item), '', True)
        self.store.set(ANNOUNCED_KEY, current)

    async def publish(self, entities: list[Entity], mono: float) -> None:
        if not self.status_sent:
            await self.client.publish(f'{self.prefix}/status', 'online', True)
            self.status_sent = True
        for entity in entities:
            last = self.last.setdefault((entity.group, entity.key), {})
            available = entity.value is not None
            attributes = None if entity.attributes is None else json.dumps(entity.attributes, ensure_ascii=False)
            if attributes is not None and attributes != last.get('attributes'):
                await self.client.publish(self.topic(entity, 'attributes'), attributes, True)
                last['attributes'] = attributes
            # An empty retained payload would delete the retained state, so empty text becomes 'Aucun'.
            payload = (entity.value or EMPTY_TEXT) if available else None
            if available and payload != last.get('value') and not (
                    entity.throttled and 'mono' in last and mono - last['mono'] < THROTTLE_S):
                await self.client.publish(self.topic(entity, 'state'), payload, True)
                last['value'], last['mono'] = payload, mono
            if available != last.get('available'):
                await self.client.publish(self.topic(entity, 'available'), 'online' if available else 'offline', True)
                last['available'] = available

    def invalidate(self, group: str, key: str) -> None:
        """Forget what was sent for this entity, so the next `publish` sends its state again."""
        self.last.pop((group, key), None)

    async def clear(self) -> None:
        for item in self.store.get(ANNOUNCED_KEY, []):
            await self.client.publish(self.config_topic(*item), '', True)
        self.store.set(ANNOUNCED_KEY, [])
        self.status_sent = False
        self.last.clear()
