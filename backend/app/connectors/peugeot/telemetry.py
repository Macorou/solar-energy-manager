from datetime import datetime, timezone
import math
from app.domain.vehicles import VehicleTelemetry
from app.domain.measurements import Quality


def parse_telemetry(payload):
    now = datetime.now(timezone.utc)
    energy = next((e for e in payload.get('energy',[]) if e.get('type','').lower() == 'electric'),{})
    def number(key):
        try:
            value = float(energy[key])
            return value if math.isfinite(value) else None
        except (ValueError, TypeError, KeyError): return None
    try:
        measured = datetime.fromisoformat(energy['updatedAt'].replace('Z','+00:00'))
        if measured.tzinfo is None: measured = None
    except (KeyError,ValueError,TypeError): measured = None
    soc = number('level')
    valid = soc is not None and 0 <= soc <= 100 and measured is not None
    return VehicleTelemetry(soc if valid else None, number('autonomy'),
        energy.get('charging',{}).get('status','unknown').lower(), measured, now,
        Quality.FRESH if valid else Quality.UNAVAILABLE)
