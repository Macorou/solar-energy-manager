"""Meter ordering/local freshness adapted from EVCC connector_core.go (MIT).

Copyright (c) evcc.io (andig, naltatis, premultiply).
Full notice: docs/third-party/evcc-MIT.txt.
"""
from dataclasses import replace
from datetime import datetime
import math
from app.domain.measurements import Sample,utcnow


def apply_readings(registry,config,state,meters):
    now=utcnow()
    cache=registry.meter_cache.setdefault(config.id,{})
    for meter in meters:
        try:
            stamp=datetime.fromisoformat(meter['timestamp'].replace('Z','+00:00'))
            if not stamp.tzinfo:continue
            stamp=min(stamp,now)  # a station clock ahead of SEM's: dated at its reception
        except (ValueError,TypeError,KeyError,AttributeError):continue
        for sample in meter.get('sampled_value',[]):
            try:
                value=float(sample['value'])
                if not math.isfinite(value) or value<0:continue
                measurand=sample.get('measurand','Energy.Active.Import.Register')
                unit=sample.get('unit','Wh')
                units={'Energy.Active.Import.Register':{'Wh':1,'kWh':1000},
                       'Power.Active.Import':{'W':1,'kW':1000},
                       'Current.Import':{'A':1,'mA':.001},'Current.Offered':{'A':1,'mA':.001}}
                if measurand not in units or unit not in units[measurand]:continue
                value*=units[measurand][unit]
                if not math.isfinite(value):continue
                phase=sample.get('phase','')
                if phase.endswith('-N'):phase=phase[:-2]
                if phase not in ('','L1','L2','L3'):continue
                if measurand=='Current.Import' and not phase:
                    if config.phases!=1:continue
                    phase='L1'
                priority=0 if sample.get('context') in ('Transaction.Begin','Transaction.End') else 1
                key=(measurand,phase);previous=cache.get(key)
                if previous and (stamp<previous[1] or stamp==previous[1] and priority<previous[2]):continue
                cache[key]=(value,stamp,priority,now)
            except (ValueError,TypeError,KeyError,AttributeError):continue

    def total(measurand,complete=False):
        aggregate=cache.get((measurand,''))
        phases={p:cache[(measurand,p)] for p in ('L1','L2','L3') if (measurand,p) in cache}
        enough=bool(phases) and (not complete or len(phases)==3 or config.phases==1 and set(phases)=={'L1'})
        if enough:
            stamp=min(item[1] for item in phases.values())
            if not aggregate or stamp>aggregate[1]:
                return (sum(item[0] for item in phases.values()),stamp,1,min(item[3] for item in phases.values()))
        return aggregate

    energy=total('Energy.Active.Import.Register',True)
    if energy and (state.energy_measured_at is None or energy[1]>=state.energy_measured_at):
        state=replace(state,energy_wh=energy[0],energy_measured_at=energy[1],energy_terminal=False)
    power=total('Power.Active.Import')
    if power and (not state.observed_power or power[1]>=state.observed_power.measured_at):
        state=replace(state,observed_power=Sample(power[0],'W','OCPP '+config.id,power[1],power[3],checked_at=power[3]),
            measured_at=power[1])
    currents=dict(state.currents)
    for phase in ('L1','L2','L3'):
        item=cache.get(('Current.Import',phase))
        if item and (phase not in currents or item[1]>=currents[phase].measured_at):
            currents[phase]=Sample(item[0],'A','OCPP '+config.id,item[1],item[3],checked_at=item[3])
    offered=cache.get(('Current.Offered',''))
    if not offered:
        values=[cache[('Current.Offered',p)] for p in ('L1','L2','L3') if ('Current.Offered',p) in cache]
        if values:offered=max(values,key=lambda item:item[0])
    return replace(state,connected=True,currents=currents,
        offered_current=Sample(offered[0],'A','OCPP Current.Offered',offered[1],offered[3],checked_at=offered[3])
            if offered else state.offered_current)
