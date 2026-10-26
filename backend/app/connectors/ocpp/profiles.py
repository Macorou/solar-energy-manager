import math
import zlib
from datetime import timedelta
from app.domain.measurements import utcnow


def build_profile(config, power_w, transaction_id, expires_at):
    amps=math.floor(power_w/(config.voltage*config.phases))
    if amps<config.min_current_a:
        raise ValueError('Puissance sous le minimum de recharge')
    amps=min(amps,config.max_current_a)
    now=utcnow()
    profile={'charging_profile_id':zlib.crc32(config.id.encode())&0x7fffffff,'stack_level':0,
        'charging_profile_purpose':'TxProfile' if transaction_id is not None else 'TxDefaultProfile',
        'charging_profile_kind':'Absolute','valid_from':now.isoformat(),
        'valid_to':(expires_at or now+timedelta(seconds=90)).isoformat(),
        'charging_schedule':{'start_schedule':now.isoformat(),'duration':90,'charging_rate_unit':'A',
            'charging_schedule_period':[{'start_period':0,'limit':amps,'number_phases':config.phases}]}}
    if transaction_id is not None:
        profile['transaction_id']=transaction_id
    return profile
