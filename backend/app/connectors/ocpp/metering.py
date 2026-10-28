"""Prepare only the OCPP telemetry needed for per-phase load control.

The caller has already authorized a new charge. Never reboot a station, clear
existing measurands, or treat an accepted write as proof it took effect.
"""
from ocpp.v16 import call


KEYS=['MeterValuesSampledData','MeterValueSampleInterval','MeterValuesSampledDataMaxLength']
REQUIRED=('Energy.Active.Import.Register','Power.Active.Import','Current.Import')


async def prepare_metering(station):
    async def read():
        response=await station.call(call.GetConfiguration(key=KEYS))
        return {row['key']:row for row in response.configuration_key or []}

    def interval(rows):
        try:return int(rows['MeterValueSampleInterval'].get('value',''))
        except (KeyError,ValueError,TypeError):return 0

    def measurands(rows):
        return [v.strip() for v in rows.get('MeterValuesSampledData',{}).get('value','').split(',') if v.strip()]

    rows=await read()
    values=measurands(rows)
    desired=list(dict.fromkeys([*values,*REQUIRED]))
    changes={}
    if not set(REQUIRED).issubset(values):changes['MeterValuesSampledData']=','.join(desired)
    if not 1<=interval(rows)<=10:changes['MeterValueSampleInterval']='10'
    try:maximum=int(rows.get('MeterValuesSampledDataMaxLength',{}).get('value','0'))
    except (ValueError,TypeError):maximum=0
    if maximum and len(desired)>maximum:return 'Télémétrie OCPP : capacité de mesures insuffisante'
    if any(key not in rows or rows[key].get('readonly',True) for key in changes):
        return 'Télémétrie OCPP : courant ou intervalle non configurables'
    for key,value in changes.items():
        result=await station.call(call.ChangeConfiguration(key=key,value=value))
        if result.status!='Accepted':
            return ('Télémétrie OCPP : redémarrage de la borne requis' if result.status=='RebootRequired'
                    else 'Télémétrie OCPP : réglage des mesures refusé')
    if changes:rows=await read()
    if not set(REQUIRED).issubset(measurands(rows)) or not 1<=interval(rows)<=10:
        return 'Télémétrie OCPP : réglages des mesures non confirmés'
    return None
