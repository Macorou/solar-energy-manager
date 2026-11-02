"""EVCC OCPP profile behavior, adapted from charger/ocpp.go (9404d825, MIT).

Copyright (c) evcc.io (andig, naltatis, premultiply).
See docs/third-party/evcc-MIT.txt for the full notice.
"""
import math
import zlib
from datetime import timedelta
from app.domain.measurements import utcnow


PROFILE_KEYS=['ChargeProfileMaxStackLevel','MaxChargingProfilesInstalled',
              'ChargingScheduleAllowedChargingRateUnit']


def profile_options(config, metadata, values):
    variant=config.ocpp_profile
    if variant=='auto':
        wallbox='wallbox' in str(metadata.get('vendor') or '').lower()
        firmware=str(metadata.get('firmware') or '')
        variant=('wallbox_fw5' if firmware.lstrip('vV').startswith('5.') else 'wallbox') if wallbox else 'standard'
    def integer(key,default):
        try:return max(0,int(values.get(key,default)))
        except (ValueError,TypeError):return default
    return {'kind':'Relative' if variant=='wallbox' else 'Absolute',
        'stack_level':0 if variant=='wallbox_fw5' else integer('ChargeProfileMaxStackLevel',0),
        'profile_id':integer('MaxChargingProfilesInstalled',zlib.crc32(config.id.encode())&0x7fffffff),
        'unit':'W' if values.get('ChargingScheduleAllowedChargingRateUnit') in ('W','Power') else 'A'}


def build_profile(config, power_w, transaction_id, expires_at, options=None):
    # expires_at bounds the queued command, not the lifetime of a charger cap.
    # An expiring positive profile can fall back to an unrestricted hardware limit.
    options=options or profile_options(config,{}, {})
    amps=math.floor(power_w/(config.voltage*config.phases)*10+1e-9)/10
    if power_w<0 or (power_w>0 and amps<config.min_current_a):
        raise ValueError('Puissance sous le minimum de recharge')
    amps=min(amps,config.max_current_a)
    period={'start_period':0,'limit':math.trunc(amps*config.voltage*config.phases) if options['unit']=='W' else amps}
    schedule={'charging_rate_unit':options['unit'],'charging_schedule_period':[period]}
    if options['kind']=='Absolute':
        schedule['start_schedule']=(utcnow()-timedelta(minutes=1)).isoformat()
    return {'charging_profile_id':options['profile_id'],'stack_level':options['stack_level'],
        'charging_profile_purpose':'TxDefaultProfile','charging_profile_kind':options['kind'],
        'charging_schedule':schedule}
