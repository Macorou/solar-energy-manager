"""Historical start SOC needs its own frozen reference, not the current SOC."""
import math


def valid_soc(value):
    return isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=100


def recover_start(session):
    """Repair pre-fix runtime records only from a proven zero-energy anchor.

    EVCC's initial_soc is immutable after sampling (unlike prev_soc/current SOC).
    A positive initial_energy means the first reference arrived during charging.
    Never extrapolate backwards from the final value or copy it into the start.
    """
    if session.get('history_soc_start_source') in ('captured','estimator','unavailable','pending'):
        return
    session['history_soc_start']=None
    session['history_soc_start_source']='unavailable'
    if (session.get('history_base',{}).get('energy_wh',0)>0
        or session.get('meter_partial') or session.get('history_meter_partial')):
        return
    state=session.get('evcc_soc') or {}
    initial=state.get('initial_soc')
    if (state.get('version')==1 and state.get('sampled') is True
        and state.get('initial_energy')==0 and valid_soc(initial)):
        session['history_soc_start']=initial
        session['history_soc_start_source']='estimator'


def capture_start(session):
    if session.get('history_soc_start_source')!='pending':
        return
    if session['energy_wh']>0 or session.get('meter_partial') or session.get('history_meter_partial'):
        session['history_soc_start_source']='unavailable'
    elif session.get('soc_usable') and valid_soc(session.get('soc')):
        session['history_soc_start']=session['soc']
        session['history_soc_start_source']='captured'
