"""Protocol summaries. Deliberately never record raw OCPP frames/payloads."""
import json
import math
from ocpp.v16.enums import Action, ChargePointStatus, ChargePointErrorCode, Measurand, Phase, UnitOfMeasure, RegistrationStatus


def number(value):
    try:
        result=float(value)
        return result if not isinstance(value,bool) and math.isfinite(result) else None
    except (TypeError,ValueError,OverflowError):
        return None


class OcppDiagnostics:
    def __init__(self, journal, station_id):
        self.journal, self.area = journal, 'ocpp:'+station_id
        self.pending = {}

    def record(self, raw, direction):
        if not self.journal:
            return
        try:
            frame = json.loads(raw)
            kind, key = frame[:2]
            if kind == 2:
                action, payload = frame[2:4]
                action=Action(action).value
                self.pending[(direction, key)] = action
                if len(self.pending) > 500:
                    self.pending.pop(next(iter(self.pending)))
            else:
                action = self.pending.pop(('TX' if direction == 'RX' else 'RX', key), 'Réponse')
                payload = frame[2] if kind == 3 else {}
            level = 'TRACE' if action in ('MeterValues', 'Heartbeat') else 'DEBUG'
            details = []
            if kind == 4:
                level = 'ERROR'
                details.append('réponse OCPP en erreur (contenu omis)')
            if isinstance(payload, dict):
                for name in ('connectorId', 'transactionId', 'meterStart', 'meterStop'):
                    value=number(payload.get(name))
                    if value is not None:details.append(f'{name}={value:g}')
                statuses={v.value for v in ChargePointStatus}|{v.value for v in RegistrationStatus}|{'Rejected','NotSupported','Unknown'}
                if payload.get('status') in statuses:details.append('status='+payload['status'])
                if payload.get('errorCode') in {v.value for v in ChargePointErrorCode}:
                    details.append('errorCode='+payload['errorCode'])
                    if payload['errorCode']!='NoError':level='ERROR'
                if action == 'MeterValues':
                    for meter in payload.get('meterValue', [])[:2]:
                        for sample in meter.get('sampledValue', [])[:12]:
                            value=number(sample.get('value'))
                            if value is None:continue
                            measure=Measurand(sample.get('measurand','Energy.Active.Import.Register')).value
                            unit=UnitOfMeasure(sample.get('unit','Wh')).value
                            phase=Phase(sample['phase']).value if sample.get('phase') else ''
                            details.append(f'{measure} {phase}={value:g} {unit}')
                profile = payload.get('csChargingProfiles', {}).get('chargingSchedule', {})
                if profile:
                    unit=profile.get('chargingRateUnit')
                    if unit in ('A','W'):
                        for period in profile.get('chargingSchedulePeriod',[])[:16]:
                            value=number(period.get('limit'))
                            if value is not None:details.append(f'limite={value:g} {unit}')
            self.journal.write(level, self.area, f'{direction} {action} '+('; '.join(details) or ('OK' if kind == 3 else 'requête')))
        except Exception:
            self.journal.write('WARN', self.area, f'{direction} trame OCPP illisible (contenu omis)')
