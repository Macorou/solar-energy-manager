from datetime import datetime
import math
from app.domain.measurements import Sample, Quality


def normalize_power(state: dict, received_at: datetime, invert=False) -> Sample:
    entity_id = state.get('entity_id', '')
    attributes = state.get('attributes', {})
    if entity_id.startswith('sensor.solar_energy_manager_') or attributes.get('source') == 'solar_energy_manager':
        raise ValueError('Source refusée : boucle de mesures')
    try:
        value = float(state['state'])
        unit = attributes.get('unit_of_measurement')
        if unit not in ('W', 'kW') or not math.isfinite(value):
            raise ValueError('Invalid power')
        value *= 1000 if unit == 'kW' else 1
        if invert:
            value *= -1
        raw_time = attributes.get('measurement_timestamp') or state.get('last_reported') or state.get('last_updated')
        measured_at = datetime.fromisoformat(raw_time.replace('Z','+00:00')) if raw_time else None
        if measured_at is not None and measured_at.tzinfo is None:
            measured_at = None
        quality = Quality.FRESH if measured_at else Quality.UNAVAILABLE
    except (ValueError, KeyError, TypeError):
        value, measured_at, quality = None, None, Quality.UNAVAILABLE
    return Sample(value, 'W', entity_id, measured_at, received_at, quality)

